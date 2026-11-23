"""
FraudGuard AI - Free-Tier Hosting Configuration Test Suite (Day 5, Task 1).

Validates:
1. Render Blueprint (render.yaml) free web service specification and absence of paid resources.
2. External environment variable wiring for Neon PostgreSQL (DATABASE_URL) and Upstash Redis (REDIS_URL).
3. Secret generation (SECRET_KEY) and external password prompt (ADMIN_PASSWORD).
4. Gunicorn start command and /api/health telemetry endpoint.
5. Reverse proxy (ProxyFix) and production security environment variables.
6. Build command optimization (no redundant ML retraining; reuses committed pipeline artifacts).
7. Free-tier concurrency optimization (WEB_CONCURRENCY=2, GUNICORN_THREADS=2).
8. ML artifact availability and MLService initialization without retraining.
9. Neon and Upstash connection URL normalization.
10. Server-side two-hour demo expiration enforcement without relying on physical cron cleanup.
"""

import os
from datetime import datetime, timedelta, timezone
import pytest
from flask import Flask
from config import normalize_database_url, normalize_redis_url


def test_render_yaml_free_web_service():
    """Test 1: render.yaml declares free-tier Python web service."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'services:' in content
    assert 'type: web' in content
    assert 'name: fraudguard-ai' in content
    assert 'env: python' in content
    assert 'plan: free' in content


def test_render_yaml_no_paid_render_databases():
    """Test 2: render.yaml does NOT declare paid Render-managed PostgreSQL databases."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'databases:' not in content
    assert 'fraudguard-db' not in content
    assert 'fromDatabase:' not in content


def test_render_yaml_no_paid_render_redis():
    """Test 3: render.yaml does NOT declare paid Render-managed Redis services."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'type: redis' not in content
    assert 'fraudguard-redis' not in content
    assert 'fromService:' not in content


def test_render_yaml_external_database_url():
    """Test 4: DATABASE_URL is wired as an externally supplied environment variable (sync: false)."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'key: DATABASE_URL' in content
    # In Render Blueprints, sync: false prompts user for external Neon PostgreSQL URL
    assert 'sync: false' in content


def test_render_yaml_external_redis_url():
    """Test 5: REDIS_URL is wired as an externally supplied environment variable (sync: false)."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'key: REDIS_URL' in content
    # In Render Blueprints, sync: false prompts user for external Upstash Redis URL
    assert 'sync: false' in content


def test_render_yaml_secret_key_auto_generation():
    """Test 6: SECRET_KEY uses generateValue: true for cryptographic randomness."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'key: SECRET_KEY' in content
    assert 'generateValue: true' in content


def test_render_yaml_admin_password_sync_false():
    """Test 7: ADMIN_PASSWORD is marked sync: false to prevent credential exposure in git."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'key: ADMIN_PASSWORD' in content
    assert 'sync: false' in content


def test_render_yaml_gunicorn_startup_command():
    """Test 8: startCommand specifies production Gunicorn with gunicorn.conf.py and run:app."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'startCommand: "gunicorn -c gunicorn.conf.py run:app"' in content


def test_render_yaml_healthcheck_endpoint():
    """Test 9: healthCheckPath points to /api/health telemetry route."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'healthCheckPath: /api/health' in content


def test_render_yaml_proxy_fix_and_production_security():
    """Test 10: USE_PROXY_FIX and production environment settings are enabled."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'key: FLASK_ENV' in content
    assert 'value: production' in content
    assert 'key: USE_PROXY_FIX' in content
    assert 'value: "true"' in content
    assert 'key: NUM_PROXIES' in content
    assert 'value: "1"' in content


def test_render_yaml_build_optimization_no_retraining():
    """Test 11: buildCommand does NOT trigger model retraining or synthetic data generation."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'train_model.py' not in content
    assert 'generate_synthetic_data.py' not in content
    assert 'pip install -r requirements.txt' in content
    assert 'python scripts/seed_demo_data.py' in content


def test_render_yaml_free_tier_concurrency():
    """Test 12: render.yaml declares WEB_CONCURRENCY=2 and GUNICORN_THREADS=2 for 512MB RAM optimization."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'key: WEB_CONCURRENCY' in content
    assert 'value: "2"' in content
    assert 'key: GUNICORN_THREADS' in content
    assert 'value: "2"' in content


def test_gunicorn_free_tier_worker_defaults():
    """Test 13: gunicorn.conf.py defaults to 2 workers and 2 threads for free-tier memory safety."""
    conf_vars = {}
    with open('gunicorn.conf.py', 'r', encoding='utf-8') as f:
        code = f.read()
    exec(compile(code, 'gunicorn.conf.py', 'exec'), conf_vars)

    assert conf_vars['workers'] == 2
    assert conf_vars['threads'] == 2
    assert conf_vars['worker_class'] == 'gthread'


def test_ml_artifacts_committed_and_loadable():
    """Test 14: ML model artifacts exist in ml/artifacts/ and MLService initializes successfully."""
    from app.services.ml_service import MLService

    artifacts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ml', 'artifacts')
    assert os.path.exists(os.path.join(artifacts_dir, 'pipeline.joblib'))
    assert os.path.exists(os.path.join(artifacts_dir, 'model_metadata.json'))
    assert os.path.exists(os.path.join(artifacts_dir, 'feature_importance.json'))

    ml = MLService.get_instance()
    assert ml.is_ready() is True
    assert ml.get_metadata() is not None
    assert 'thresholds' in ml.get_metadata()


def test_neon_postgresql_url_normalization():
    """Test 15: normalize_database_url handles Neon postgres:// and preserves sslmode."""
    neon_url = "postgres://alex:secret123@ep-cool-fog-123456.us-east-2.aws.neon.tech/fraudguard?sslmode=require"
    normalized = normalize_database_url(neon_url)

    assert normalized.startswith("postgresql://")
    assert "sslmode=require" in normalized
    assert "secret123" in normalized


def test_upstash_redis_url_normalization():
    """Test 16: normalize_redis_url handles Upstash rediss:// TLS connection strings."""
    upstash_url = "rediss://default:upstash_token_abc@cool-fly-12345.upstash.io:6379"
    normalized = normalize_redis_url(upstash_url)

    assert normalized.startswith("rediss://")
    assert "upstash_token_abc" in normalized
    assert normalized == upstash_url


def test_ephemeral_demo_active_expiration_without_cron(monkeypatch):
    """Test 17: User.is_expired immediately rejects expired demo accounts even if cron cleanup hasn't run."""
    from app.models import User

    # 1. Permanent analyst never expires
    analyst = User(name="Alex Analyst", email="analyst@bank.com", is_ephemeral=False)
    analyst.created_at = datetime.now(timezone.utc) - timedelta(days=30)
    assert analyst.is_expired is False

    # 2. Fresh ephemeral user within 2-hour window does not expire
    fresh_ephemeral = User(name="Recruiter Demo", email="recruiter_123@demo.fraudguard.ai", is_ephemeral=True)
    fresh_ephemeral.created_at = datetime.now(timezone.utc) - timedelta(minutes=45)
    assert fresh_ephemeral.is_expired is False

    # 3. Expired ephemeral user (older than 2 hours) is immediately marked expired
    expired_ephemeral = User(name="Recruiter Demo", email="recruiter_456@demo.fraudguard.ai", is_ephemeral=True)
    expired_ephemeral.created_at = datetime.now(timezone.utc) - timedelta(hours=2, minutes=5)
    assert expired_ephemeral.is_expired is True
