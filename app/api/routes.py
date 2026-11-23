from flask import request, jsonify, current_app
from flask_login import current_user, login_user
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import generate_csrf, validate_csrf
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.api import api_bp
from app.extensions import db, limiter
from app.models import User, Transaction, Prediction, FraudAlert
from app.services.prediction_service import PredictionService
from app.services.analytics_service import AnalyticsService
from app.services.ml_service import MLService
from app.utils.validators import validate_transaction_payload
from app import log_audit_event


def generate_api_token(user_id):
    """Generates a cryptographically signed Bearer API token."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='fg-api-auth')
    return serializer.dumps({'user_id': user_id})


def verify_api_token(token, max_age=86400 * 7):
    """Verifies a signed Bearer API token and returns the corresponding User."""
    try:
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='fg-api-auth')
        data = serializer.loads(token, max_age=max_age)
        user_id = data.get('user_id')
        if not user_id:
            return None
        return User.query.get(user_id)
    except (BadSignature, SignatureExpired, Exception):
        return None


@api_bp.before_request
def api_auth_and_csrf_guard():
    """
    1. Programmatic API Authentication:
       If 'Authorization: Bearer <token>' is provided, authenticates the client
       without ambient browser session cookies (immune to CSRF).
    2. Cookie-Authenticated CSRF Protection:
       Protects state-changing requests against Cross-Site Request Forgery:
       - Rejects cross-origin state changes (Origin mismatch or Sec-Fetch-Site: cross-site).
       - Validates X-CSRFToken / csrf_token if provided.
    """
    # 1. Bearer Token Auth (for programmatic API consumers)
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:].strip()
        user = verify_api_token(token)
        if user and user.is_active:
            login_user(user, remember=False)
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired API token.',
                'status': 401
            }), 401

    # 2. State-changing methods CSRF protection
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        # API login endpoint validates credentials in body; does not need prior CSRF token
        if request.endpoint == 'api.api_login':
            return None

        # Check for cross-origin indicators
        origin = request.headers.get('Origin')
        sec_fetch_site = request.headers.get('Sec-Fetch-Site')

        is_cross_site = (sec_fetch_site == 'cross-site')
        if origin:
            from urllib.parse import urlparse
            origin_host = urlparse(origin).netloc
            if origin_host and origin_host != request.host:
                is_cross_site = True

        # Block cross-site state-changing requests
        if is_cross_site:
            log_audit_event(
                'CSRF_ATTACK_BLOCKED',
                current_user.id if current_user.is_authenticated else None,
                f"Blocked cross-origin {request.method} to {request.path} from Origin: {origin}"
            )
            return jsonify({
                'success': False,
                'error': 'Cross-origin request forbidden by CSRF security policy.',
                'status': 403
            }), 403

        # If a CSRF token header is provided, validate it
        csrf_token = request.headers.get('X-CSRFToken') or request.headers.get('X-CSRF-Token')
        if csrf_token:
            try:
                validate_csrf(csrf_token)
            except Exception:
                return jsonify({
                    'success': False,
                    'error': 'Invalid or expired CSRF token.',
                    'status': 400
                }), 400


def get_rate_limit_key():
    """
    Determines rate-limit client identity.
    Authenticated users are identified by server-side user ID (user:<id>).
    Anonymous visitors are identified by client IP address (ip:<remote_addr>).
    Never trusts client-supplied headers or request body parameters.
    """
    if current_user and current_user.is_authenticated:
        return f"user:{current_user.id}"
    return f"ip:{get_remote_address()}"


def predict_rate_limit():
    """Returns dynamic limit string for single transaction prediction."""
    if current_user and current_user.is_authenticated:
        return current_app.config.get('RATELIMIT_PREDICT_AUTH', '60/minute')
    return current_app.config.get('RATELIMIT_PREDICT_ANON', '10/minute')


def batch_predict_rate_limit():
    """Returns dynamic limit string for batch prediction requests."""
    if current_user and current_user.is_authenticated:
        return current_app.config.get('RATELIMIT_BATCH_AUTH', '20/minute')
    return current_app.config.get('RATELIMIT_BATCH_ANON', '5/minute')


@api_bp.route('/auth/login', methods=['POST'])
@limiter.limit(lambda: current_app.config.get('RATELIMIT_LOGIN', '5/minute'))
def api_login():
    """Authenticates API client and returns user details and status."""
    data = request.get_json(silent=True)
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({
            'success': False,
            'error': 'Missing required fields: email and password are required.'
        }), 400

    user = User.query.filter_by(email=data['email'].lower().strip()).first()
    if not user or not user.check_password(data['password']):
        log_audit_event('API_AUTH_FAILED', None, f"Failed API login attempt for: {data.get('email')}")
        return jsonify({
            'success': False,
            'error': 'Invalid credentials.'
        }), 401

    if not user.is_active_account:
        log_audit_event('API_AUTH_BLOCKED', user.id, f"Blocked API login for deactivated user: {user.email}")
        return jsonify({
            'success': False,
            'error': 'Account has been deactivated.'
        }), 403

    login_user(user)
    token = generate_api_token(user.id)
    csrf_token = generate_csrf()
    log_audit_event('API_AUTH_SUCCESS', user.id, f"API login for {user.email}")
    return jsonify({
        'success': True,
        'message': 'Authentication successful.',
        'token': token,
        'csrf_token': csrf_token,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role
        }
    }), 200


@api_bp.route('/predict', methods=['POST'])
@limiter.limit(predict_rate_limit, key_func=get_rate_limit_key)
def api_predict():
    """
    Submits transaction for real-time AI fraud prediction and risk scoring.
    Supports authenticated analysts/administrators (persisted to database)
    and restricted recruiter demo predictions (ephemeral evaluation, zero DB pollution).
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            'success': False,
            'error': 'Invalid JSON body. Please provide a valid JSON transaction payload.'
        }), 400

    txn_data, err = validate_transaction_payload(data)
    if err:
        return jsonify({
            'success': False,
            'error': err
        }), 400

    is_auth = current_user.is_authenticated
    user_id = current_user.id if is_auth else None

    try:
        if is_auth:
            # Authenticated Analyst / Admin: Persist transaction and log audit trail
            transaction, prediction, alert = PredictionService.predict_transaction(
                txn_data=txn_data,
                user_id=user_id,
                is_demo=False,
                auto_commit=True
            )
            is_demo_mode = False
            log_audit_event(
                'API_TRANSACTION_PREDICTED',
                user_id,
                f"API evaluation for {transaction.transaction_ref}: Amount=${transaction.amount:,.2f}, Risk={prediction.risk_level}"
            )
        else:
            # Recruiter Demo / Unauthenticated Mode:
            # Execute genuine ML inference and compute explainability factors,
            # but rollback to prevent anonymous database pollution and storage exhaustion.
            transaction, prediction, alert = PredictionService.predict_transaction(
                txn_data=txn_data,
                user_id=None,
                is_demo=True,
                auto_commit=False
            )
            is_demo_mode = True

        prediction_payload = {
            'is_fraud_predicted': prediction.is_fraud_predicted,
            'fraud_probability': round(prediction.fraud_probability, 4),
            'fraud_probability_pct': round(prediction.fraud_probability * 100, 2),
            'risk_level': prediction.risk_level,
            'recommended_action': prediction.recommended_action,
            'explanations': prediction.get_explanations(),
            'model_name': prediction.model_name,
            'model_version': prediction.model_version
        }

        response_data = {
            'transaction_ref': transaction.transaction_ref,
            'amount': transaction.amount,
            'transaction_type': transaction.transaction_type,
            'is_demo': is_demo_mode,
            'prediction': prediction_payload,
            'alert_generated': bool(alert)
        }

        if not is_auth:
            # Rollback unauthenticated demo transaction to protect database integrity
            db.session.rollback()

        return jsonify({
            'success': True,
            'data': response_data
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f"Inference execution failed: {str(e)}"
        }), 500


@api_bp.route('/predict/batch', methods=['POST'])
@limiter.limit(batch_predict_rate_limit, key_func=get_rate_limit_key)
def api_predict_batch():
    """
    Executes batch predictions on an array of transaction objects.
    Authenticated users can process up to 100 items (persisted to database).
    Unauthenticated callers are restricted to a maximum of 10 items in demo mode (ephemeral).
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get('transactions'), list):
        return jsonify({
            'success': False,
            'error': "Invalid request format. Expected JSON object with 'transactions' array."
        }), 400

    transactions_list = data['transactions']
    is_auth = current_user.is_authenticated

    # Enforce batch size limits
    if not is_auth and len(transactions_list) > 10:
        return jsonify({
            'success': False,
            'error': 'Unauthenticated demo batch size is limited to 10 transactions. Please authenticate for larger batches.'
        }), 401

    if len(transactions_list) > 100:
        return jsonify({
            'success': False,
            'error': 'Batch size exceeds maximum limit of 100 items per API request.'
        }), 400

    results = []
    user_id = current_user.id if is_auth else None

    for idx, item in enumerate(transactions_list):
        if not isinstance(item, dict):
            results.append({'index': idx, 'status': 'error', 'error': 'Each transaction item must be a JSON object.'})
            continue

        txn_data, err = validate_transaction_payload(item)
        if err:
            results.append({'index': idx, 'status': 'error', 'error': err})
            continue

        try:
            txn, pred, alert = PredictionService.predict_transaction(
                txn_data=txn_data,
                user_id=user_id,
                is_demo=(not is_auth),
                auto_commit=False
            )

            results.append({
                'index': idx,
                'status': 'success',
                'transaction_ref': txn.transaction_ref,
                'amount': txn.amount,
                'is_fraud_predicted': pred.is_fraud_predicted,
                'fraud_probability': round(pred.fraud_probability, 4),
                'risk_level': pred.risk_level
            })
        except Exception as e:
            results.append({'index': idx, 'status': 'error', 'error': str(e)})

    has_errors = any(r.get('status') == 'error' for r in results)
    if is_auth and not has_errors:
        db.session.commit()
        log_audit_event(
            'API_BATCH_PREDICTION',
            user_id,
            f"API Batch processed {len(transactions_list)} items"
        )
    else:
        db.session.rollback()

    return jsonify({
        'success': not has_errors,
        'total': len(transactions_list),
        'is_demo': not is_auth,
        'results': results
    }), 200


@api_bp.route('/transactions', methods=['GET'])
def api_transactions():
    """
    Retrieves paginated transaction records.
    Strictly requires authentication:
    - Normal users/analysts can ONLY view their own transactions.
    - Administrators can view all transactions.
    """
    if not current_user.is_authenticated:
        return jsonify({
            'success': False,
            'error': 'Authentication required. Please sign in to view transaction history.'
        }), 401

    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 20, type=int), 100)

    query = Transaction.query
    if not current_user.is_admin:
        query = query.filter(Transaction.user_id == current_user.id)
    else:
        # Administrators may optionally filter by specific user_id
        target_user = request.args.get('user_id', type=int)
        if target_user:
            query = query.filter(Transaction.user_id == target_user)

    pagination = query.order_by(Transaction.created_at.desc()).paginate(page=page, per_page=limit, error_out=False)

    return jsonify({
        'success': True,
        'page': page,
        'total_pages': pagination.pages,
        'total_items': pagination.total,
        'transactions': [t.to_dict() for t in pagination.items]
    }), 200


@api_bp.route('/transactions/<int:txn_id>', methods=['GET'])
def api_transaction_detail(txn_id):
    """
    Retrieves detail for a specific transaction.
    Strictly requires authentication:
    - Normal users can ONLY view transactions they own.
    - If transaction does not exist or belongs to another user, returns 404 to prevent ID enumeration.
    - Administrators can view any transaction.
    """
    if not current_user.is_authenticated:
        return jsonify({
            'success': False,
            'error': 'Authentication required. Please sign in to view transaction details.'
        }), 401

    txn = Transaction.query.get(txn_id)
    if not txn:
        return jsonify({'success': False, 'error': 'Transaction not found.'}), 404

    if not current_user.is_admin and txn.user_id != current_user.id:
        log_audit_event(
            'UNAUTHORIZED_API_ACCESS',
            current_user.id,
            f"User {current_user.email} attempted unauthorized API access to transaction #{txn_id}"
        )
        return jsonify({'success': False, 'error': 'Transaction not found.'}), 404

    return jsonify({
        'success': True,
        'transaction': txn.to_dict()
    }), 200


@api_bp.route('/stats', methods=['GET'])
def api_stats():
    """
    Retrieves high-level dashboard metrics for the authenticated user/administrator.
    Requires authentication to prevent scraping of financial portfolio metrics.
    """
    if not current_user.is_authenticated:
        return jsonify({
            'success': False,
            'error': 'Authentication required. Please sign in to access telemetry statistics.'
        }), 401

    summary = AnalyticsService.get_dashboard_summary(
        user_id=current_user.id,
        is_admin=current_user.is_admin
    )
    return jsonify({
        'success': True,
        'statistics': summary
    }), 200


@api_bp.route('/analytics', methods=['GET'])
def api_analytics():
    """
    Retrieves visual chart distributions for the authenticated user/administrator.
    Requires authentication.
    """
    if not current_user.is_authenticated:
        return jsonify({
            'success': False,
            'error': 'Authentication required. Please sign in to access analytics data.'
        }), 401

    charts = AnalyticsService.get_chart_data(
        user_id=current_user.id,
        is_admin=current_user.is_admin
    )
    return jsonify({
        'success': True,
        'chart_data': charts
    }), 200


@api_bp.route('/alerts', methods=['GET'])
def api_alerts():
    """
    Retrieves recent fraud alerts.
    Strictly requires authentication:
    - Normal users can ONLY view alerts for their own transactions.
    - Administrators can view all system alerts.
    """
    if not current_user.is_authenticated:
        return jsonify({
            'success': False,
            'error': 'Authentication required. Please sign in to view fraud alerts.'
        }), 401

    query = FraudAlert.query
    if not current_user.is_admin:
        query = query.filter(FraudAlert.user_id == current_user.id)

    alerts = query.order_by(FraudAlert.created_at.desc()).limit(50).all()
    return jsonify({
        'success': True,
        'alerts': [a.to_dict() for a in alerts]
    }), 200


@api_bp.route('/model-info', methods=['GET'])
def api_model_info():
    """Retrieves machine learning model diagnostics and evaluation report (public telemetry)."""
    ml = MLService.get_instance()
    return jsonify({
        'success': True,
        'model_status': 'ready' if ml.is_ready() else 'unloaded',
        'metadata': ml.get_metadata(),
        'top_feature_importance': ml.get_feature_importances()
    }), 200
