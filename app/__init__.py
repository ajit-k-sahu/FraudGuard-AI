import os
from flask import Flask, render_template, request, jsonify
from config import config_by_name
from app.extensions import db, login_manager, csrf, limiter
from app.models import User, FraudAlert, AuditLog

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, config_by_name['default']))

    # Allow dynamic runtime environment variable to override static config attribute
    runtime_secret = os.environ.get('SECRET_KEY')
    if runtime_secret is not None:
        app.config['SECRET_KEY'] = runtime_secret

    runtime_db_url = os.environ.get('DATABASE_URL')
    if runtime_db_url is not None:
        from config import normalize_database_url
        app.config['SQLALCHEMY_DATABASE_URI'] = normalize_database_url(runtime_db_url)

    runtime_redis_url = os.environ.get('REDIS_URL') or os.environ.get('RATELIMIT_STORAGE_URI')
    if runtime_redis_url is not None:
        from config import normalize_redis_url
        app.config['RATELIMIT_STORAGE_URI'] = normalize_redis_url(runtime_redis_url)

    # Production Secret Validation Guard
    is_production = (config_name == 'production' or app.config.get('ENV') == 'production')
    if is_production and not app.config.get('TESTING', False):
        INSECURE_SECRETS = {
            'fraudguard-ai-dev-secret-key-38491024-change-in-prod',
            'change-this-secret-key-in-production-use-a-strong-random-hex',
            'change-this-in-production',
            'replace-with-a-very-strong-secret-key',
            'secret', 'changeme', 'password', '123456', 'default', 'test', 'dev'
        }
        secret_key = app.config.get('SECRET_KEY')
        if not secret_key or not str(secret_key).strip():
            raise ValueError(
                "Production startup halted: SECRET_KEY environment variable is missing. "
                "A strong, externally supplied secret key is required in production."
            )
        secret_key_clean = str(secret_key).strip()
        if secret_key_clean.lower() in {s.lower() for s in INSECURE_SECRETS} or len(secret_key_clean) < 24:
            raise ValueError(
                "Production startup halted: Insecure or weak SECRET_KEY detected. "
                "Provide a cryptographically random secret key of at least 24 characters."
            )

        # Production Database Configuration Guard
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        raw_db = os.environ.get('DATABASE_URL')
        if not db_uri or not raw_db or not str(raw_db).strip():
            raise ValueError(
                "Production startup halted: DATABASE_URL environment variable is missing. "
                "A production PostgreSQL database connection URL is required."
            )
        # Verify SQLite is not accidentally used in production
        if 'sqlite:///' in db_uri.lower():
            raise ValueError(
                "Production startup halted: Insecure database configuration detected. "
                "SQLite cannot be used in production. Please configure a production PostgreSQL DATABASE_URL."
            )
        # Verify valid PostgreSQL URI scheme
        if not (db_uri.startswith('postgresql://') or db_uri.startswith('postgresql+')):
            scheme = db_uri.split('://')[0] if '://' in db_uri else 'unknown'
            raise ValueError(
                f"Production startup halted: Unsupported production database scheme in DATABASE_URL. "
                f"Expected 'postgresql://' connection URI, got '{scheme}://...'."
            )

        # Production Redis Rate Limiter Storage Guard
        redis_uri = app.config.get('RATELIMIT_STORAGE_URI', '')
        raw_redis = os.environ.get('REDIS_URL') or os.environ.get('RATELIMIT_STORAGE_URI')
        if not redis_uri or not raw_redis or not str(raw_redis).strip():
            raise ValueError(
                "Production startup halted: REDIS_URL environment variable is missing. "
                "A production Redis connection URL is required for distributed rate limiting."
            )
        # Verify memory:// is not silently or accidentally used in production
        if 'memory://' in redis_uri.lower():
            raise ValueError(
                "Production startup halted: Insecure rate limit storage configuration detected. "
                "'memory://' cannot be used in production. Please configure a production Redis REDIS_URL."
            )
        # Verify valid Redis URI scheme (redis://, rediss://, or unix://)
        valid_schemes = ('redis://', 'rediss://', 'unix://')
        if not any(redis_uri.startswith(s) for s in valid_schemes):
            scheme = redis_uri.split('://')[0] if '://' in redis_uri else 'unknown'
            raise ValueError(
                f"Production startup halted: Unsupported rate limit storage scheme in REDIS_URL. "
                f"Expected 'redis://' or 'rediss://' connection URI, got '{scheme}://...'."
            )

    # Initialize extensions
    try:
        db.init_app(app)
    except ModuleNotFoundError as e:
        if 'psycopg2' in str(e):
            app.logger.warning(
                "PostgreSQL driver 'psycopg2' is not available in current environment. "
                "Database initialization deferred (driver available in production container)."
            )
        else:
            raise
    login_manager.init_app(app)
    csrf.init_app(app)
    try:
        limiter.init_app(app)
    except Exception as e:
        if 'redis' in str(e).lower() and ('prerequisite' in str(e).lower() or 'not available' in str(e).lower()):
            app.logger.warning(
                "Redis client library is not available in current environment. "
                "Rate limiter storage initialization deferred (redis driver available in production container)."
            )
        else:
            raise

    # Reverse proxy support (behind Render, Cloudflare, AWS ALB, Nginx)
    # Only enabled when USE_PROXY_FIX is true to avoid trusting unverified spoofed client headers
    if os.environ.get('USE_PROXY_FIX', 'False').lower() in ('true', '1', 't'):
        from werkzeug.middleware.proxy_fix import ProxyFix
        num_proxies = int(os.environ.get('NUM_PROXIES', 1))
        x_for = int(os.environ.get('PROXY_FIX_X_FOR', num_proxies))
        x_proto = int(os.environ.get('PROXY_FIX_X_PROTO', num_proxies))
        x_host = int(os.environ.get('PROXY_FIX_X_HOST', num_proxies))
        x_prefix = int(os.environ.get('PROXY_FIX_X_PREFIX', num_proxies))
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=x_for,
            x_proto=x_proto,
            x_host=x_host,
            x_prefix=x_prefix
        )

    # Exclude REST API blueprint from Flask-WTF form-based CSRF
    # (API endpoints are guarded against CSRF at the API routing layer via api_auth_and_csrf_guard)
    from app.api import api_bp
    csrf.exempt(api_bp)

    # Register Blueprints
    from app.auth import auth_bp
    from app.dashboard import dashboard_bp
    from app.transactions import transactions_bp
    from app.alerts import alerts_bp
    from app.analytics import analytics_bp
    from app.admin import admin_bp
    from app.profile import profile_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(transactions_bp, url_prefix='/transactions')
    app.register_blueprint(alerts_bp, url_prefix='/alerts')
    app.register_blueprint(analytics_bp, url_prefix='/analytics')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(profile_bp, url_prefix='/profile')
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    # Ensure database schema is migrated and up-to-date with additive columns
    try:
        with app.app_context():
            from app.utils.migrations import run_migrations
            run_migrations(app=app)
            db.create_all()
    except Exception as db_err:
        app.logger.warning(f"Database schema initialization deferred: {db_err}")

    # Register Health Check Endpoint for Deployment (Render, AWS, GCP, etc.)
    @app.route('/api/health')
    @app.route('/health')
    def health_check():
        from app.services.ml_service import MLService
        ml_ready = MLService.get_instance().is_ready()
        db_ready = True
        try:
            db.session.execute(db.text('SELECT 1'))
        except Exception:
            db_ready = False

        status = 'healthy' if (ml_ready and db_ready) else 'degraded'
        code = 200 if status == 'healthy' else 503
        return jsonify({
            'status': status,
            'database': 'connected' if db_ready else 'disconnected',
            'ml_model': 'loaded' if ml_ready else 'missing',
            'version': '1.0.0'
        }), code

    # Custom Jinja2 Filters
    @app.template_filter('number_format')
    def number_format_filter(val):
        try:
            return f"{int(val):,}"
        except (ValueError, TypeError):
            return str(val) if val is not None else '0'

    @app.template_filter('currency')
    def currency_filter(val):
        try:
            return f"${float(val):,.2f}"
        except (ValueError, TypeError):
            return str(val) if val is not None else '$0.00'

    @app.template_filter('pct')
    def pct_filter(val):
        try:
            return f"{float(val):.1%}"
        except (ValueError, TypeError):
            return str(val) if val is not None else '0.0%'

    @app.template_filter('format_ist')
    def format_ist_filter(val, fmt=None):
        from app.utils.timezone import format_ist, DEFAULT_IST_FORMAT
        return format_ist(val, fmt or DEFAULT_IST_FORMAT)

    @app.template_filter('to_ist')
    def to_ist_filter(val):
        from app.utils.timezone import to_ist
        return to_ist(val)

    # Context processors for templates
    @app.context_processor
    def inject_global_data():
        from flask_login import current_user
        unread_count = 0
        if current_user.is_authenticated:
            try:
                unread_count = FraudAlert.query.filter_by(
                    user_id=current_user.id, is_read=False
                ).count()
            except Exception:
                unread_count = 0
        return {
            'unread_alerts_count': unread_count,
            'current_year': 2026,
            'app_name': 'FraudGuard AI'
        }

    # Error Handlers
    @app.errorhandler(429)
    def ratelimit_error(error):
        is_api = (
            request.path.startswith('/api/') or 
            request.is_json or 
            request.accept_mimetypes.best == 'application/json'
        )
        if is_api:
            return jsonify({
                'success': False,
                'error': 'Too many requests. Rate limit exceeded. Please wait before retrying.',
                'status': 429
            }), 429
        return render_template('errors/429.html'), 429

    @app.errorhandler(413)
    def request_entity_too_large(error):
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({
                'success': False,
                'error': 'Payload or file upload exceeds maximum allowable size of 16 MB.',
                'status': 413
            }), 413
        from flask import flash, redirect, url_for
        flash("The uploaded file exceeds the maximum allowable limit of 16 MB. Please upload a smaller file.", "danger")
        return redirect(url_for('transactions.batch'))

    @app.errorhandler(403)
    def forbidden_error(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Forbidden: You do not have permission to access this resource.'}), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Resource not found.'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        if request.path.startswith('/api/'):
            return jsonify({'error': 'An internal server error occurred.'}), 500
        return render_template('errors/500.html'), 500

    # HTTP Security Headers & Content Security Policy (CSP)
    @app.after_request
    def apply_security_headers(response):
        # Prevent MIME-type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # Clickjacking defense
        response.headers['X-Frame-Options'] = 'DENY'

        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions Policy (restrict sensitive hardware / browser APIs)
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'

        # Content Security Policy (CSP)
        # Permitting Bootstrap 5 & Chart.js from cdn.jsdelivr.net, self, and inline scripts/styles for dynamic charts
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net data:; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        # Strict-Transport-Security (HSTS)
        # ONLY apply when in production AND HTTPS is enabled (never in local HTTP development)
        # request.is_secure handles HTTPS natively when direct or when behind a trusted ProxyFix
        is_https = request.is_secure
        is_prod_config = (app.config.get('ENV') == 'production' or app.config.get('SESSION_COOKIE_SECURE', False))
        if is_https and is_prod_config and not app.config.get('DEBUG', False) and not app.config.get('TESTING', False):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        elif app.config.get('TESTING_HSTS', False):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        return response

    # Register CLI commands
    from app.cli import register_cli_commands
    register_cli_commands(app)

    return app

def log_audit_event(action, user_id=None, details=None):
    """Utility to record security and user audit trail records."""
    try:
        ip = request.remote_addr if request else '127.0.0.1'
        log = AuditLog(
            user_id=user_id,
            action=action,
            ip_address=ip,
            details=details
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[AuditLog] Failed to record audit event: {e}")
