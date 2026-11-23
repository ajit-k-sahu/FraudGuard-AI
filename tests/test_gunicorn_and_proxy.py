"""
Gunicorn WSGI Server & Production Reverse-Proxy Security Test Suite.
Verifies Gunicorn dependencies, configuration, entrypoint, worker settings,
Werkzeug ProxyFix behavior (enabled vs disabled), trusted proxy header validation,
HSTS/HTTPS detection, secure cookie behavior, and debug mode suppression in production.
"""

import os
import re
import pytest
from flask import Flask, request


def test_gunicorn_dependency_in_requirements():
    """Test 1: requirements.txt specifies gunicorn WSGI server."""
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        content = f.read()
    assert re.search(r'^gunicorn\s*>=', content, re.MULTILINE) is not None


def test_application_entrypoint_in_run_py():
    """Test 2: run.py exposes Flask application object as 'app'."""
    import run
    assert hasattr(run, 'app')
    assert isinstance(run.app, Flask)


def test_gunicorn_conf_file_exists_and_binds_to_port():
    """Test 3: gunicorn.conf.py defines bind address using $PORT or default 5000."""
    # Load and execute gunicorn.conf.py as a module namespace
    conf_vars = {}
    with open('gunicorn.conf.py', 'r', encoding='utf-8') as f:
        code = f.read()
    exec(compile(code, 'gunicorn.conf.py', 'exec'), conf_vars)

    assert 'bind' in conf_vars
    assert conf_vars['bind'].startswith('0.0.0.0:')
    assert conf_vars['worker_class'] == 'gthread'
    assert conf_vars['threads'] >= 2
    assert conf_vars['timeout'] >= 60
    assert conf_vars['max_requests'] >= 100


def test_procfile_configures_gunicorn_entrypoint():
    """Test 4: Procfile specifies Gunicorn using gunicorn.conf.py and run:app entrypoint."""
    with open('Procfile', 'r', encoding='utf-8') as f:
        content = f.read().strip()
    assert 'gunicorn' in content
    assert 'run:app' in content


def test_dockerfile_configures_gunicorn_entrypoint():
    """Test 5: Dockerfile specifies Gunicorn using gunicorn.conf.py and run:app."""
    with open('Dockerfile', 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'gunicorn' in content
    assert 'run:app' in content
    assert 'gunicorn.conf.py' in content


def test_render_yaml_configures_gunicorn_and_proxy_fix():
    """Test 6: render.yaml declares gunicorn startCommand and enables USE_PROXY_FIX."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'gunicorn' in content
    assert 'run:app' in content
    assert 'USE_PROXY_FIX' in content
    assert 'NUM_PROXIES' in content


def test_proxy_fix_disabled_by_default(monkeypatch):
    """Test 7: When USE_PROXY_FIX is disabled, raw X-Forwarded-Proto is NOT trusted."""
    from app import create_app
    monkeypatch.delenv('USE_PROXY_FIX', raising=False)

    app = create_app('testing')
    with app.test_client() as c:
        # Client sends spoofed X-Forwarded-Proto header directly
        res = c.get('/api/health', headers={'X-Forwarded-Proto': 'https'})
        assert res.status_code == 200
        # Untrusted client header must not enable HSTS or mark scheme as https
        assert 'Strict-Transport-Security' not in res.headers


def test_proxy_fix_enabled_when_env_flag_set(monkeypatch):
    """Test 8: When USE_PROXY_FIX=true, Werkzeug ProxyFix middleware wraps wsgi_app."""
    from werkzeug.middleware.proxy_fix import ProxyFix
    from app import create_app

    monkeypatch.setenv('USE_PROXY_FIX', 'true')
    monkeypatch.setenv('NUM_PROXIES', '1')

    app = create_app('testing')
    assert isinstance(app.wsgi_app, ProxyFix)
    assert app.wsgi_app.x_for == 1
    assert app.wsgi_app.x_proto == 1


def test_proxy_fix_respects_trusted_forwarded_https(monkeypatch):
    """Test 9: When USE_PROXY_FIX=true, trusted proxy X-Forwarded-Proto marks request as secure."""
    from app import create_app

    monkeypatch.setenv('USE_PROXY_FIX', 'true')
    monkeypatch.setenv('NUM_PROXIES', '1')

    app = create_app('testing')

    @app.route('/test-scheme')
    def scheme_check():
        return {'is_secure': request.is_secure, 'scheme': request.scheme}

    with app.test_client() as c:
        res = c.get('/test-scheme', headers={'X-Forwarded-Proto': 'https'})
        data = res.get_json()
        assert data['is_secure'] is True
        assert data['scheme'] == 'https'


def test_proxy_fix_respects_custom_num_proxies(monkeypatch):
    """Test 10: Granular PROXY_FIX_X_FOR and NUM_PROXIES counts are applied to middleware."""
    from app import create_app

    monkeypatch.setenv('USE_PROXY_FIX', 'true')
    monkeypatch.setenv('NUM_PROXIES', '2')
    monkeypatch.setenv('PROXY_FIX_X_FOR', '3')

    app = create_app('testing')
    assert app.wsgi_app.x_for == 3
    assert app.wsgi_app.x_proto == 2
    assert app.wsgi_app.x_host == 2
    assert app.wsgi_app.x_prefix == 2


def test_proxy_fix_rejects_untrusted_client_hops(monkeypatch):
    """Test 11: With NUM_PROXIES=1, only the immediate proxy hop is trusted, ignoring client spoofing."""
    from app import create_app

    monkeypatch.setenv('USE_PROXY_FIX', 'true')
    monkeypatch.setenv('NUM_PROXIES', '1')

    app = create_app('testing')

    @app.route('/test-hop-scheme')
    def hop_scheme():
        return {'is_secure': request.is_secure, 'scheme': request.scheme}

    with app.test_client() as c:
        # Spoofed multiple hops where client sent 'https', but outer proxy forwarded 'http'
        res = c.get('/test-hop-scheme', headers={'X-Forwarded-Proto': 'https, http'})
        data = res.get_json()
        # ProxyFix with num_proxies=1 reads the last hop ('http'), not the spoofed 'https'
        assert data['is_secure'] is False
        assert data['scheme'] == 'http'


def test_hsts_attached_when_proxy_fix_evaluates_https_in_production(monkeypatch):
    """Test 12: In production with USE_PROXY_FIX=true and HTTPS forwarded, HSTS header is attached."""
    from app import create_app

    monkeypatch.setenv('SECRET_KEY', 'a-very-strong-cryptographically-random-secret-key-32chars!')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost:5432/fraudguard')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')
    monkeypatch.setenv('USE_PROXY_FIX', 'true')
    monkeypatch.setenv('NUM_PROXIES', '1')

    prod_app = create_app('production')
    with prod_app.test_client() as c:
        res = c.get('/api/health', headers={'X-Forwarded-Proto': 'https'})
        assert res.headers.get('Strict-Transport-Security') == 'max-age=31536000; includeSubDomains'


def test_hsts_omitted_for_direct_http_in_production(monkeypatch):
    """Test 13: In production without HTTPS (direct HTTP), HSTS header is strictly omitted."""
    from app import create_app

    monkeypatch.setenv('SECRET_KEY', 'a-very-strong-cryptographically-random-secret-key-32chars!')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost:5432/fraudguard')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')
    monkeypatch.delenv('USE_PROXY_FIX', raising=False)

    prod_app = create_app('production')
    with prod_app.test_client() as c:
        res = c.get('/api/health')
        assert 'Strict-Transport-Security' not in res.headers


def test_debug_mode_strictly_disabled_in_production(monkeypatch):
    """Test 14: Flask debug mode is strictly False in production configuration."""
    from app import create_app
    from config import ProductionConfig

    assert ProductionConfig.DEBUG is False

    monkeypatch.setenv('SECRET_KEY', 'a-very-strong-cryptographically-random-secret-key-32chars!')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost:5432/fraudguard')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')

    app = create_app('production')
    assert app.debug is False
    assert app.config['DEBUG'] is False


def test_secure_cookies_configured_in_production():
    """Test 15: Cookie security flags are enforced in production configuration."""
    from config import ProductionConfig
    assert ProductionConfig.SESSION_COOKIE_SECURE is True
    assert ProductionConfig.REMEMBER_COOKIE_SECURE is True
    assert ProductionConfig.SESSION_COOKIE_HTTPONLY is True
    assert ProductionConfig.SESSION_COOKIE_SAMESITE == 'Lax'


def test_http_security_headers_preserved_behind_proxy(monkeypatch):
    """Test 16: nosniff, DENY, Referrer-Policy, and CSP headers are preserved behind proxy."""
    from app import create_app

    monkeypatch.setenv('USE_PROXY_FIX', 'true')
    monkeypatch.setenv('NUM_PROXIES', '1')

    app = create_app('testing')
    with app.test_client() as c:
        res = c.get('/api/health', headers={'X-Forwarded-Proto': 'https'})
        assert res.headers.get('X-Content-Type-Options') == 'nosniff'
        assert res.headers.get('X-Frame-Options') == 'DENY'
        assert res.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'
        assert 'camera=()' in res.headers.get('Permissions-Policy', '')
