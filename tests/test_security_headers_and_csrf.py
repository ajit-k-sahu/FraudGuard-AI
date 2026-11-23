"""
Security Headers, CSRF Protection & Production Secret Hardening Test Suite.
Verifies HTTP security headers (nosniff, DENY, strict-origin, CSP, conditional HSTS),
Cross-Site Request Forgery defenses (browser forms and API endpoints),
Bearer token programmatic authentication, and production secret enforcement.
"""

import os
import pytest
from flask_wtf.csrf import generate_csrf
from app import create_app
from app.extensions import db
from app.models import User, Transaction


def test_http_security_headers_present_on_responses(client):
    """Verifies that nosniff, DENY, Referrer-Policy, and Permissions-Policy are present on all responses."""
    res = client.get('/api/health')
    assert res.status_code == 200
    assert res.headers.get('X-Content-Type-Options') == 'nosniff'
    assert res.headers.get('X-Frame-Options') == 'DENY'
    assert res.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'
    assert 'camera=()' in res.headers.get('Permissions-Policy', '')


def test_content_security_policy_compatibility(client):
    """Verifies that Content-Security-Policy allows required CDNs (cdn.jsdelivr.net) and inline chart scripts."""
    res = client.get('/')
    assert res.status_code == 200
    csp = res.headers.get('Content-Security-Policy', '')
    assert "default-src 'self'" in csp
    assert "https://cdn.jsdelivr.net" in csp
    assert "'unsafe-inline'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "form-action 'self'" in csp


def test_hsts_omitted_in_local_http_development(client):
    """Verifies that HSTS is strictly omitted in local development over HTTP."""
    res = client.get('/api/health')
    assert 'Strict-Transport-Security' not in res.headers


def test_hsts_enabled_in_https_production_config():
    """Verifies that HSTS is attached when production mode and HTTPS are configured."""
    orig_key = os.environ.get('SECRET_KEY')
    orig_db = os.environ.get('DATABASE_URL')
    orig_redis = os.environ.get('REDIS_URL')
    os.environ['SECRET_KEY'] = 'a-very-strong-cryptographically-random-secret-key-32chars!'
    os.environ['DATABASE_URL'] = 'postgresql://postgres_user:postgres_pass@localhost:5432/fraudguard'
    os.environ['REDIS_URL'] = 'redis://redis_user:redis_pass@localhost:6379/0'
    try:
        prod_app = create_app('production')
        prod_app.config['TESTING_HSTS'] = True
        with prod_app.test_client() as c:
            res = c.get('/api/health')
            assert res.headers.get('Strict-Transport-Security') == 'max-age=31536000; includeSubDomains'
    finally:
        if orig_key:
            os.environ['SECRET_KEY'] = orig_key
        else:
            os.environ.pop('SECRET_KEY', None)
        if orig_db:
            os.environ['DATABASE_URL'] = orig_db
        else:
            os.environ.pop('DATABASE_URL', None)
        if orig_redis:
            os.environ['REDIS_URL'] = orig_redis
        else:
            os.environ.pop('REDIS_URL', None)


def test_production_startup_fails_without_secret_key():
    """Verifies that starting the app in production without SECRET_KEY raises a ValueError."""
    orig_key = os.environ.get('SECRET_KEY')
    if 'SECRET_KEY' in os.environ:
        del os.environ['SECRET_KEY']
    try:
        with pytest.raises(ValueError) as excinfo:
            create_app('production')
        assert "SECRET_KEY environment variable is missing" in str(excinfo.value)
    finally:
        if orig_key:
            os.environ['SECRET_KEY'] = orig_key


def test_production_startup_fails_with_insecure_secret_key():
    """Verifies that starting the app in production with an insecure or short key fails safely."""
    orig_key = os.environ.get('SECRET_KEY')
    os.environ['SECRET_KEY'] = 'short-key'
    try:
        with pytest.raises(ValueError) as excinfo:
            create_app('production')
        assert "insecure or weak" in str(excinfo.value).lower() or "too short" in str(excinfo.value).lower()
    finally:
        if orig_key:
            os.environ['SECRET_KEY'] = orig_key


def test_production_startup_succeeds_with_strong_secret_key():
    """Verifies that production initialization succeeds with a cryptographically strong secret."""
    orig_key = os.environ.get('SECRET_KEY')
    orig_db = os.environ.get('DATABASE_URL')
    orig_redis = os.environ.get('REDIS_URL')
    os.environ['SECRET_KEY'] = 'production-grade-cryptographic-random-secret-key-9992384'
    os.environ['DATABASE_URL'] = 'postgresql://postgres_user:postgres_pass@localhost:5432/fraudguard'
    os.environ['REDIS_URL'] = 'redis://redis_user:redis_pass@localhost:6379/0'
    try:
        app = create_app('production')
        assert app is not None
        assert app.config['SESSION_COOKIE_SECURE'] is True
        assert app.config['REMEMBER_COOKIE_SECURE'] is True
        assert app.config['SESSION_COOKIE_HTTPONLY'] is True
        assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'
    finally:
        if orig_key:
            os.environ['SECRET_KEY'] = orig_key
        else:
            os.environ.pop('SECRET_KEY', None)
        if orig_db:
            os.environ['DATABASE_URL'] = orig_db
        else:
            os.environ.pop('DATABASE_URL', None)
        if orig_redis:
            os.environ['REDIS_URL'] = orig_redis
        else:
            os.environ.pop('REDIS_URL', None)


def test_browser_form_csrf_protection_when_enabled(app):
    """Verifies that HTML forms reject submissions lacking CSRF token when WTF_CSRF_ENABLED=True."""
    import re
    app.config['WTF_CSRF_ENABLED'] = True
    c = app.test_client()

    # 1. Submission without CSRF token is rejected with 400
    res_no_csrf = c.post('/auth/login', data={
        'email': 'analyst@test.com',
        'password': 'AnalystPass123!'
    })
    assert res_no_csrf.status_code == 400
    assert b'CSRF' in res_no_csrf.data or b'Bad Request' in res_no_csrf.data

    # 2. Extract token from rendered login page and submit
    res_get = c.get('/auth/login')
    html = res_get.get_data(as_text=True)
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html) or re.search(r'value="([^"]+)"[^>]*name="csrf_token"', html)
    assert match is not None, "CSRF token input field must be present in rendered form"
    token = match.group(1)

    res_with_csrf = c.post('/auth/login', data={
        'email': 'analyst@test.com',
        'password': 'AnalystPass123!',
        'csrf_token': token
    }, follow_redirects=True)
    assert res_with_csrf.status_code == 200
    assert b'Alex Analyst' in res_with_csrf.data or b'Dashboard' in res_with_csrf.data

    # Restore default test setting
    app.config['WTF_CSRF_ENABLED'] = False


def test_cookie_authenticated_api_csrf_blocks_cross_origin(app):
    """
    Verifies that a cross-origin state-changing request (Origin: http://evil.com or Sec-Fetch-Site: cross-site)
    from a session-authenticated user is blocked with HTTP 403 Forbidden.
    """
    c = app.test_client()
    # Log in to establish session cookie
    c.post('/auth/login', data={'email': 'analyst@test.com', 'password': 'AnalystPass123!'}, follow_redirects=True)

    payload = {
        'amount': 500.0,
        'transaction_type': 'Transfer'
    }

    # Cross-origin attack with malicious Origin
    res_evil_origin = c.post(
        '/api/v1/predict',
        json=payload,
        headers={'Origin': 'http://evil-attacker-site.com'}
    )
    assert res_evil_origin.status_code == 403
    data = res_evil_origin.get_json()
    assert data['success'] is False
    assert 'Cross-origin' in data['error']

    # Cross-origin attack with Sec-Fetch-Site: cross-site
    res_cross_site = c.post(
        '/api/v1/predict',
        json=payload,
        headers={'Sec-Fetch-Site': 'cross-site'}
    )
    assert res_cross_site.status_code == 403
    assert 'Cross-origin' in res_cross_site.get_json()['error']


def test_cookie_authenticated_api_csrf_token_validation(app):
    """
    Verifies that when X-CSRFToken header is supplied on cookie-authenticated requests,
    invalid tokens are rejected (HTTP 400), while valid tokens are accepted.
    """
    c = app.test_client()
    login_res = c.post('/api/v1/auth/login', json={'email': 'analyst@test.com', 'password': 'AnalystPass123!'})
    assert login_res.status_code == 200
    valid_token = login_res.get_json()['csrf_token']

    payload = {'amount': 150.0, 'transaction_type': 'Payment'}

    # 1. Invalid CSRF token
    res_invalid = c.post(
        '/api/v1/predict',
        json=payload,
        headers={'X-CSRFToken': 'tampered-csrf-token-xyz'}
    )
    assert res_invalid.status_code == 400
    assert 'Invalid or expired CSRF token' in res_invalid.get_json()['error']

    # 2. Valid CSRF token
    res_valid = c.post(
        '/api/v1/predict',
        json=payload,
        headers={'X-CSRFToken': valid_token}
    )
    assert res_valid.status_code == 201
    assert res_valid.get_json()['success'] is True


def test_programmatic_api_bearer_token_authentication(client, app):
    """
    Verifies that API clients can authenticate via Authorization: Bearer <token>
    without ambient cookies, successfully executing predictions and persisting transactions.
    """
    # 1. Authenticate via /api/v1/auth/login and obtain Bearer token
    login_res = client.post('/api/v1/auth/login', json={
        'email': 'analyst@test.com',
        'password': 'AnalystPass123!'
    })
    assert login_res.status_code == 200
    login_data = login_res.get_json()
    assert 'token' in login_data
    bearer_token = login_data['token']

    # 2. Use a clean client with NO cookies to submit a prediction with Bearer token
    clean_client = app.test_client()
    with app.app_context():
        analyst = User.query.filter_by(email='analyst@test.com').first()
        count_before = Transaction.query.filter_by(user_id=analyst.id).count()

    predict_res = clean_client.post(
        '/api/v1/predict',
        json={'amount': 880.0, 'transaction_type': 'Purchase'},
        headers={'Authorization': f'Bearer {bearer_token}'}
    )
    assert predict_res.status_code == 201
    pred_data = predict_res.get_json()
    assert pred_data['success'] is True
    assert pred_data['data']['is_demo'] is False

    with app.app_context():
        count_after = Transaction.query.filter_by(user_id=analyst.id).count()
        assert count_after == count_before + 1


def test_recruiter_demo_prediction_without_csrf_or_cookies(client, app):
    """
    Verifies that unauthenticated recruiter demo users can execute predictions
    without needing a CSRF token or session cookie, with zero DB persistence.
    """
    with app.app_context():
        count_before = Transaction.query.count()

    res = client.post('/api/v1/predict', json={
        'amount': 42.0,
        'transaction_type': 'Payment'
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data['success'] is True
    assert data['data']['is_demo'] is True

    with app.app_context():
        count_after = Transaction.query.count()
        assert count_after == count_before
