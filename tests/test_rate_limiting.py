"""
Rate Limiting & Abuse Prevention Test Suite for FraudGuard -AI.
Verifies rate limits across web authentication, API authentication,
real-time ML prediction, and batch inference.
"""

import pytest
from app.extensions import limiter
from app.models import User


def test_web_login_rate_limiting(client):
    """Verifies that 5 failed web login attempts are allowed, and 6th is throttled with 429."""
    limiter.reset()
    for i in range(5):
        res = client.post('/auth/login', data={
            'email': f'attacker{i}@test.com',
            'password': 'WrongPassword123!'
        })
        assert res.status_code == 200, f"Attempt {i+1} should return 200 form with error"

    # 6th attempt within the same minute should be rate limited
    res6 = client.post('/auth/login', data={
        'email': 'attacker6@test.com',
        'password': 'WrongPassword123!'
    })
    assert res6.status_code == 429
    assert b'429' in res6.data
    assert b'Too Many Requests' in res6.data

    # Verify GET requests to login page are NOT restricted
    res_get = client.get('/auth/login')
    assert res_get.status_code == 200


def test_api_login_rate_limiting(client):
    """Verifies that API login is rate-limited after 5 attempts and returns JSON 429."""
    limiter.reset()
    for i in range(5):
        res = client.post('/api/v1/auth/login', json={
            'email': 'bad_user@test.com',
            'password': 'WrongPassword!'
        })
        assert res.status_code == 401

    res6 = client.post('/api/v1/auth/login', json={
        'email': 'bad_user@test.com',
        'password': 'WrongPassword!'
    })
    assert res6.status_code == 429
    data = res6.get_json()
    assert data['success'] is False
    assert data['status'] == 429
    assert 'Rate limit exceeded' in data['error']


def test_web_registration_rate_limiting(client):
    """Verifies that public registration is limited to 5 attempts per IP."""
    limiter.reset()
    for i in range(5):
        res = client.post('/auth/register', data={
            'name': f'Test User {i}',
            'email': f'testuser{i}@example.com',
            'password': 'SecurePassword2026!',
            'confirm_password': 'SecurePassword2026!'
        })
        assert res.status_code == 302, f"Attempt {i+1} should register and redirect"

    # 6th attempt should be blocked
    res6 = client.post('/auth/register', data={
        'name': 'Test User 6',
        'email': 'testuser6@example.com',
        'password': 'SecurePassword2026!',
        'confirm_password': 'SecurePassword2026!'
    })
    assert res6.status_code == 429
    assert b'429' in res6.data
    assert b'Too Many Requests' in res6.data

    # Verify GET request to register page is NOT restricted
    res_get = client.get('/auth/register')
    assert res_get.status_code == 200


def test_anonymous_prediction_rate_limiting(client):
    """Verifies that anonymous /api/v1/predict allows 10 demo evaluations then throttles on the 11th."""
    limiter.reset()
    payload = {
        'amount': 100.0,
        'transaction_type': 'Transfer',
        'sender_account': 'DEMO-SENDER',
        'receiver_account': 'DEMO-RECEIVER'
    }

    for i in range(10):
        res = client.post('/api/v1/predict', json=payload)
        assert res.status_code == 201, f"Demo prediction {i+1} should succeed"

    # 11th attempt should trigger 429
    res11 = client.post('/api/v1/predict', json=payload)
    assert res11.status_code == 429
    data = res11.get_json()
    assert data['success'] is False
    assert data['status'] == 429
    assert 'Rate limit exceeded' in data['error']


def test_authenticated_prediction_higher_limit(app):
    """
    Verifies that authenticated analysts have higher limits (60/min)
    and use server-side user ID key rather than IP, remaining isolated from anonymous limits.
    """
    limiter.reset()
    c = app.test_client()
    # Log in as analyst
    c.post('/auth/login', data={'email': 'analyst@test.com', 'password': 'AnalystPass123!'}, follow_redirects=True)

    payload = {
        'amount': 250.0,
        'transaction_type': 'Payment'
    }

    # Verify authenticated analyst can execute > 10 predictions (which would exceed the anon 10/min limit)
    for i in range(15):
        res = c.post('/api/v1/predict', json=payload)
        assert res.status_code == 201, f"Authenticated prediction {i+1} should succeed under 60/min quota"


def test_anonymous_batch_rate_limiting(client):
    """Verifies that anonymous batch prediction is limited to 5 requests per minute."""
    limiter.reset()
    payload = {
        'transactions': [
            {'amount': 50.0, 'transaction_type': 'Payment'},
            {'amount': 75.0, 'transaction_type': 'Transfer'}
        ]
    }

    for i in range(5):
        res = client.post('/api/v1/predict/batch', json=payload)
        assert res.status_code == 200, f"Batch request {i+1} should succeed"

    res6 = client.post('/api/v1/predict/batch', json=payload)
    assert res6.status_code == 429
    data = res6.get_json()
    assert data['success'] is False
    assert data['status'] == 429


def test_batch_row_limits_enforced_with_rate_limiting(client, app):
    """Verifies that 10-item demo batch and 100-item auth limits remain strictly enforced."""
    limiter.reset()
    # Anonymous with 11 items -> 401
    eleven_items = [{'amount': float(i + 10)} for i in range(11)]
    res_demo = client.post('/api/v1/predict/batch', json={'transactions': eleven_items})
    assert res_demo.status_code == 401
    assert 'limited to 10 transactions' in res_demo.get_json()['error']

    # Authenticated with 101 items -> 400
    c_auth = app.test_client()
    c_auth.post('/auth/login', data={'email': 'analyst@test.com', 'password': 'AnalystPass123!'}, follow_redirects=True)
    over_limit_items = [{'amount': float(i + 10)} for i in range(101)]
    res_auth = c_auth.post('/api/v1/predict/batch', json={'transactions': over_limit_items})
    assert res_auth.status_code == 400
    assert 'exceeds maximum limit of 100 items' in res_auth.get_json()['error']


def test_normal_requests_under_limit_succeed(client):
    """Verifies that normal requests below rate limits operate without restriction."""
    limiter.reset()
    res_health = client.get('/api/health')
    assert res_health.status_code == 200

    res_login_get = client.get('/auth/login')
    assert res_login_get.status_code == 200

    res_reg_get = client.get('/auth/register')
    assert res_reg_get.status_code == 200


def test_rate_limit_error_format_consistency(client):
    """Verifies consistent, non-revealing error payloads for both API and Web."""
    limiter.reset()
    # Exhaust API login limit
    for _ in range(5):
        client.post('/api/v1/auth/login', json={'email': 'x@x.com', 'password': 'p'})
    res_api = client.post('/api/v1/auth/login', json={'email': 'x@x.com', 'password': 'p'})
    assert res_api.status_code == 429
    assert res_api.is_json
    json_body = res_api.get_json()
    assert json_body['status'] == 429
    assert json_body['success'] is False
    # Error message must NOT reveal email existence or internal server traces
    assert 'email' not in json_body['error'].lower()
    assert 'Traceback' not in str(res_api.data)
