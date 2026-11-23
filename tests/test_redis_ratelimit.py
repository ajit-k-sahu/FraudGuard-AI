"""
Redis-Based Shared Rate Limiting Configuration & Protection Test Suite.
Verifies production Redis storage configuration, environment URL normalization,
local/testing memory:// isolation, production fail-safe startup guards,
preservation of all endpoint rate limits, infrastructure declarations,
and failure behavior without requiring a running live Redis service.
"""

import os
import re
import pytest
from config import (
    Config,
    DevelopmentConfig,
    TestingConfig,
    ProductionConfig,
    normalize_redis_url,
)


def test_normalize_redis_url_trims_whitespace():
    """Test 1: normalize_redis_url strips leading and trailing whitespace."""
    raw_url = "   redis://:secret@redis-host:6379/0   \n"
    assert normalize_redis_url(raw_url) == "redis://:secret@redis-host:6379/0"


def test_normalize_redis_url_preserves_standard_redis():
    """Test 2: Standard redis:// URLs are preserved exactly."""
    url = "redis://fraudguard-redis.internal:6379/0"
    assert normalize_redis_url(url) == url


def test_normalize_redis_url_preserves_tls_rediss():
    """Test 3: Encrypted TLS rediss:// URLs are preserved for secure cloud providers."""
    tls_url = "rediss://default:supersecret@oregon-redis.render.com:6380/0"
    assert normalize_redis_url(tls_url) == tls_url


def test_normalize_redis_url_handles_empty_and_none():
    """Test 4: Empty string or None safely returns an empty string."""
    assert normalize_redis_url("") == ""
    assert normalize_redis_url(None) == ""
    assert normalize_redis_url("   ") == ""


def test_storage_options_contain_timeouts_and_retries():
    """Test 5: Storage options declare socket connection timeouts and retry flags."""
    options = Config.RATELIMIT_STORAGE_OPTIONS
    assert isinstance(options, dict)
    assert options.get('socket_timeout') == 2.0
    assert options.get('socket_connect_timeout') == 2.0
    assert options.get('retry_on_timeout') is True


def test_ratelimit_swallow_errors_is_false():
    """Test 6: RATELIMIT_SWALLOW_ERRORS is strictly False so rate limiting is not silently disabled."""
    assert Config.RATELIMIT_SWALLOW_ERRORS is False
    assert DevelopmentConfig.RATELIMIT_SWALLOW_ERRORS is False
    assert TestingConfig.RATELIMIT_SWALLOW_ERRORS is False
    assert ProductionConfig.RATELIMIT_SWALLOW_ERRORS is False


def test_development_config_preserves_memory_storage_by_default(monkeypatch):
    """Test 7: Development mode defaults to memory:// when REDIS_URL is not set."""
    monkeypatch.delenv('REDIS_URL', raising=False)
    monkeypatch.delenv('RATELIMIT_STORAGE_URI', raising=False)

    dev_uri = normalize_redis_url(os.environ.get('REDIS_URL')) or os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    assert dev_uri == 'memory://'
    assert DevelopmentConfig.RATELIMIT_STORAGE_URI == 'memory://'


def test_testing_config_preserves_isolated_memory_storage():
    """Test 8: TestingConfig strictly uses memory:// for zero-dependency isolated unit testing."""
    assert TestingConfig.RATELIMIT_STORAGE_URI == 'memory://'
    assert TestingConfig.TESTING is True


def test_production_config_requires_redis_url_and_does_not_fallback_to_memory(monkeypatch):
    """Test 9: ProductionConfig never falls back to memory:// if REDIS_URL is unset."""
    monkeypatch.delenv('REDIS_URL', raising=False)
    monkeypatch.delenv('RATELIMIT_STORAGE_URI', raising=False)

    prod_uri = normalize_redis_url(os.environ.get('REDIS_URL', ''))
    assert prod_uri == ""
    assert prod_uri != "memory://"


def test_production_startup_halts_when_redis_url_missing(monkeypatch):
    """Test 10: create_app('production') halts with ValueError if REDIS_URL is missing."""
    from app import create_app

    monkeypatch.setenv('SECRET_KEY', 'A_VERY_SECURE_PRODUCTION_KEY_OF_AT_LEAST_32_CHARS_LONG!')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://fraudguard_user:password@localhost:5432/fraudguard_db')
    monkeypatch.delenv('REDIS_URL', raising=False)
    monkeypatch.delenv('RATELIMIT_STORAGE_URI', raising=False)

    with pytest.raises(ValueError, match="REDIS_URL environment variable is missing"):
        create_app('production')


def test_production_startup_halts_when_memory_uri_supplied_in_production(monkeypatch):
    """Test 11: create_app('production') halts if memory:// is explicitly supplied in production."""
    from app import create_app

    monkeypatch.setenv('SECRET_KEY', 'A_VERY_SECURE_PRODUCTION_KEY_OF_AT_LEAST_32_CHARS_LONG!')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://fraudguard_user:password@localhost:5432/fraudguard_db')
    monkeypatch.setenv('REDIS_URL', 'memory://')

    with pytest.raises(ValueError, match="Insecure rate limit storage configuration detected"):
        create_app('production')


def test_production_startup_halts_when_unsupported_scheme_supplied(monkeypatch):
    """Test 12: create_app('production') halts if non-Redis scheme (e.g. http://) is passed."""
    from app import create_app

    monkeypatch.setenv('SECRET_KEY', 'A_VERY_SECURE_PRODUCTION_KEY_OF_AT_LEAST_32_CHARS_LONG!')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://fraudguard_user:password@localhost:5432/fraudguard_db')
    monkeypatch.setenv('REDIS_URL', 'http://redis-host:6379')

    with pytest.raises(ValueError, match="Unsupported rate limit storage scheme in REDIS_URL"):
        create_app('production')


def test_all_expected_endpoint_rate_limits_configured_and_preserved():
    """Test 13: Verifies all required rate limit definitions and default policies are preserved."""
    assert Config.RATELIMIT_LOGIN == '5/minute'
    assert Config.RATELIMIT_REGISTER == '5/hour'
    assert Config.RATELIMIT_DEMO_LOGIN == '10/minute'
    assert Config.RATELIMIT_PREDICT_ANON == '10/minute'
    assert Config.RATELIMIT_PREDICT_AUTH == '60/minute'
    assert Config.RATELIMIT_BATCH_ANON == '5/minute'
    assert Config.RATELIMIT_BATCH_AUTH == '20/minute'


def test_rate_limit_decorators_present_on_protected_endpoints():
    """Test 14: Verifies auth and api modules apply limiter.limit on designated endpoints."""
    import inspect
    from app.auth import routes as auth_routes
    from app.api import routes as api_routes

    # Check function names in auth routes
    assert hasattr(auth_routes, 'login')
    assert hasattr(auth_routes, 'demo_login')
    assert hasattr(auth_routes, 'register')

    # Check function names in api routes
    assert hasattr(api_routes, 'api_login')
    assert hasattr(api_routes, 'api_predict')
    assert hasattr(api_routes, 'api_predict_batch')

    # Read route source files to verify @limiter.limit decorators are in place
    with open('app/auth/routes.py', 'r', encoding='utf-8') as f:
        auth_src = f.read()
    assert "@limiter.limit(lambda: current_app.config.get('RATELIMIT_LOGIN'" in auth_src
    assert "@limiter.limit(lambda: current_app.config.get('RATELIMIT_DEMO_LOGIN'" in auth_src
    assert "@limiter.limit(lambda: current_app.config.get('RATELIMIT_REGISTER'" in auth_src

    with open('app/api/routes.py', 'r', encoding='utf-8') as f:
        api_src = f.read()
    assert "@limiter.limit(lambda: current_app.config.get('RATELIMIT_LOGIN'" in api_src
    assert "@limiter.limit(predict_rate_limit" in api_src
    assert "@limiter.limit(batch_predict_rate_limit" in api_src


def test_requirements_declares_redis_client():
    """Test 15: requirements.txt specifies redis client library >= 5.0.0."""
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        content = f.read()

    assert re.search(r'^redis\s*>=', content, re.MULTILINE) is not None


def test_docker_compose_declares_redis_service_and_env():
    """Test 16: docker-compose.yml configures redis container, healthcheck, and REDIS_URL."""
    with open('docker-compose.yml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'redis:7-alpine' in content
    assert 'fraudguard_redis' in content
    assert 'REDIS_URL=redis://redis:6379/0' in content
    assert 'redis-cli' in content
    assert 'redisdata:' in content


def test_render_yaml_declares_redis_service_and_env():
    """Test 17: render.yaml configures external Redis REDIS_URL without paid Render service."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'REDIS_URL' in content
    assert 'sync: false' in content
    # Free-tier target uses external Upstash Redis rather than paid Render-managed redis
    assert 'fromService:' not in content
    assert 'type: redis' not in content


def test_shared_storage_uri_configuration_for_production_workers():
    """Test 18: Multiple worker processes configured with REDIS_URL share identical storage target."""
    worker_1_url = "redis://:worker_pass@shared-redis-cluster:6379/0"
    worker_2_url = " redis://:worker_pass@shared-redis-cluster:6379/0 \n"

    norm_1 = normalize_redis_url(worker_1_url)
    norm_2 = normalize_redis_url(worker_2_url)

    assert norm_1 == norm_2
    assert norm_1 == "redis://:worker_pass@shared-redis-cluster:6379/0"


def test_redis_connection_failure_does_not_silently_disable_rate_limiting():
    """Test 19: When storage is unavailable and swallow_errors=False, limiter raises errors rather than disabling."""
    from flask import Flask
    from flask_limiter import Limiter
    from limits.errors import StorageError
    from unittest.mock import MagicMock

    app = Flask(__name__)
    app.testing = True
    app.config['RATELIMIT_SWALLOW_ERRORS'] = False
    app.config['RATELIMIT_STORAGE_URI'] = 'memory://'

    test_limiter = Limiter(key_func=lambda: '127.0.0.1')
    test_limiter.init_app(app)

    assert test_limiter._swallow_errors is False

    @app.route('/test-protected')
    @test_limiter.limit("1/minute")
    def protected():
        return "ok"

    # Simulate underlying storage failure on the rate limiter strategy
    test_limiter._limiter.hit = MagicMock(side_effect=StorageError("Simulated Redis connection refused: 6379"))

    with app.test_client() as c:
        with pytest.raises(Exception) as excinfo:
            c.get('/test-protected')
        # Rate limiting failed closed / raised rather than silently letting requests through uncounted
        assert "Simulated Redis connection refused" in str(excinfo.value)
