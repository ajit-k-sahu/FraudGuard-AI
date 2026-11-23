import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def normalize_database_url(url):
    """
    Normalizes database connection URLs for SQLAlchemy compatibility.
    - Trims whitespace.
    - Converts legacy Heroku/Render 'postgres://' scheme to standard 'postgresql://'.
    - Preserves explicit driver specifications like 'postgresql+psycopg2://'.
    """
    if not url:
        return ''
    url = str(url).strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def normalize_redis_url(url):
    """
    Normalizes Redis connection URLs for Flask-Limiter and limits compatibility.
    - Trims whitespace.
    - Preserves standard redis://, rediss:// (TLS), and unix:// schemes.
    - Returns empty string for empty or None values.
    """
    if not url:
        return ''
    url = str(url).strip()
    return url


def redact_secret_url(url):
    """
    Redacts credentials (passwords, tokens, and secret strings) from connection URLs for safe logging.
    Example: 'postgresql://user:secret123@host:5432/db' -> 'postgresql://user:***@host:5432/db'
    Example: 'redis://:mypassword@host:6379/0' -> 'redis://:***@host:6379/0'
    """
    if not url:
        return ''
    url_str = str(url).strip()
    try:
        from urllib.parse import urlsplit, urlunsplit
        import re
        parts = urlsplit(url_str)
        if parts.password:
            redacted_netloc = re.sub(r':([^@]+)@', r':***@', parts.netloc)
            return urlunsplit((parts.scheme, redacted_netloc, parts.path, parts.query, parts.fragment))
        return url_str
    except Exception:
        import re
        return re.sub(r':([^@]+)@', r':***@', url_str)


class Config:
    """Base configuration settings."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'fraudguard-ai-dev-secret-key-38491024-change-in-prod')
    
    # SQLAlchemy Configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.environ.get(
            'DATABASE_URL',
            f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'fraudguard.db')}"
        )
    )

    # Database Connection Pooling & Health Options
    # pool_pre_ping=True tests connections prior to use, preventing stale/dropped connection errors (e.g. Postgres / RDS / Render)
    # pool_recycle=1800 recycles connections after 30 minutes to prevent server-side timeout disconnects
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
    }

    # Session & Cookie Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    
    # ML & Fraud Detection Thresholds
    RISK_THRESHOLD_LOW = float(os.environ.get('RISK_THRESHOLD_LOW', 0.30))
    RISK_THRESHOLD_HIGH = float(os.environ.get('RISK_THRESHOLD_HIGH', 0.70))
    
    # Model Artifact Paths
    MODEL_ARTIFACTS_DIR = os.path.join(BASE_DIR, 'ml', 'artifacts')
    
    # Batch Upload Limits
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload limit
    ALLOWED_EXTENSIONS = {'csv'}
    
    # Demo Data & Shared Account Configuration
    DEMO_MODE = os.environ.get('DEMO_MODE', 'True').lower() in ('true', '1', 't')
    DEMO_USER_EMAIL = os.environ.get('DEMO_USER_EMAIL', 'analyst@bank.com').lower().strip()
    DEMO_ACCOUNTS = {
        e.lower().strip() for e in os.environ.get('DEMO_ACCOUNTS', 'analyst@bank.com').split(',') if e.strip()
    }
    DEMO_SESSION_LIFETIME_HOURS = int(os.environ.get('DEMO_SESSION_LIFETIME_HOURS', 2))
    DEMO_SESSION_TTL_SECONDS = DEMO_SESSION_LIFETIME_HOURS * 3600

    # Rate Limiting & Abuse Prevention Configuration
    # NOTE: 'memory://' is suitable for local development and single-worker testing only.
    # In production multi-worker environments (e.g. Gunicorn/Waitress across processes/instances),
    # RATELIMIT_STORAGE_URI must be configured with a shared persistent backend like Redis:
    # e.g., 'redis://:password@host:port/0' or 'rediss://...' for TLS.
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'True').lower() in ('true', '1', 't')
    RATELIMIT_STORAGE_URI = normalize_redis_url(os.environ.get('REDIS_URL')) or os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    RATELIMIT_STRATEGY = 'fixed-window'
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_SWALLOW_ERRORS = False
    RATELIMIT_STORAGE_OPTIONS = {
        'socket_timeout': 2.0,
        'socket_connect_timeout': 2.0,
        'retry_on_timeout': True,
    }
    RATELIMIT_DEFAULT = []  # No blanket global limits that disrupt normal web browsing

    # Specific Endpoint Rate Limits (configurable via environment variables)
    RATELIMIT_LOGIN = os.environ.get('RATELIMIT_LOGIN', '5/minute')
    RATELIMIT_REGISTER = os.environ.get('RATELIMIT_REGISTER', '5/hour')
    RATELIMIT_DEMO_LOGIN = os.environ.get('RATELIMIT_DEMO_LOGIN', '10/minute')
    RATELIMIT_PREDICT_ANON = os.environ.get('RATELIMIT_PREDICT_ANON', '10/minute')
    RATELIMIT_PREDICT_AUTH = os.environ.get('RATELIMIT_PREDICT_AUTH', '60/minute')
    RATELIMIT_BATCH_ANON = os.environ.get('RATELIMIT_BATCH_ANON', '5/minute')
    RATELIMIT_BATCH_AUTH = os.environ.get('RATELIMIT_BATCH_AUTH', '20/minute')

class DevelopmentConfig(Config):
    """Development configuration: preserves memory:// or local Redis if REDIS_URL is provided."""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    RATELIMIT_STORAGE_URI = normalize_redis_url(os.environ.get('REDIS_URL')) or os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

class TestingConfig(Config):
    """Testing configuration with in-memory or dedicated test database and isolated memory limiter."""
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'test_fraudguard.db')}"
    SESSION_COOKIE_SECURE = False
    RATELIMIT_STORAGE_URI = 'memory://'

class ProductionConfig(Config):
    """Production configuration: requires external PostgreSQL DATABASE_URL and Redis REDIS_URL."""
    ENV = 'production'
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    # In production, SECRET_KEY must be provided via external environment variable
    SECRET_KEY = os.environ.get('SECRET_KEY')
    # In production, DATABASE_URL must be provided externally (no fallback to development SQLite)
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.environ.get('DATABASE_URL', ''))
    # In production, REDIS_URL must be provided externally for shared multi-worker rate limiting (no fallback to memory://)
    RATELIMIT_STORAGE_URI = normalize_redis_url(os.environ.get('REDIS_URL', ''))

config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
