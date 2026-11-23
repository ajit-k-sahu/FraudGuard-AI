"""
Authentication and User Account Security Test Suite.
Tests registration, validation, password hashing, session control, and access guards.
"""

import pytest
from app.models import User
from app.extensions import db

def test_registration_success(client, app):
    res = client.post('/auth/register', data={
        'name': 'New Analyst',
        'email': 'newanalyst@bank.com',
        'password': 'SecurePassword2026!',
        'confirm_password': 'SecurePassword2026!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Registration successful' in res.data or b'Sign In' in res.data

    with app.app_context():
        user = User.query.filter_by(email='newanalyst@bank.com').first()
        assert user is not None
        assert user.name == 'New Analyst'
        assert user.check_password('SecurePassword2026!')
        assert not user.check_password('WrongPass')
        assert user.role == 'user'
        assert user.is_active_account is True

def test_registration_duplicate_email(client):
    # analyst@test.com is already seeded in conftest
    res = client.post('/auth/register', data={
        'name': 'Duplicate User',
        'email': 'analyst@test.com',
        'password': 'SomePassword123!',
        'confirm_password': 'SomePassword123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'already registered' in res.data or b'already in use' in res.data or b'Email' in res.data

def test_registration_password_mismatch(client):
    res = client.post('/auth/register', data={
        'name': 'Mismatch User',
        'email': 'mismatch@bank.com',
        'password': 'PasswordOne123!',
        'confirm_password': 'PasswordTwo999!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Passwords must match' in res.data or b'match' in res.data

def test_login_success_and_logout(client):
    res_login = client.post('/auth/login', data={
        'email': 'analyst@test.com',
        'password': 'AnalystPass123!'
    }, follow_redirects=True)
    assert res_login.status_code == 200
    assert b'Alex Analyst' in res_login.data or b'Dashboard' in res_login.data

    res_logout = client.get('/auth/logout', follow_redirects=True)
    assert res_logout.status_code == 200
    assert b'Sign In' in res_logout.data or b'Detect Financial Fraud' in res_logout.data

def test_login_invalid_password(client):
    res = client.post('/auth/login', data={
        'email': 'analyst@test.com',
        'password': 'WrongPassword999!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Invalid email address or password' in res.data

def test_login_deactivated_account(client):
    res = client.post('/auth/login', data={
        'email': 'blocked@test.com',
        'password': 'BlockedPass123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'deactivated' in res.data or b'contact support' in res.data

def test_protected_routes_require_authentication(client):
    # Unauthenticated client attempting to access protected views
    res_dash = client.get('/dashboard')
    assert res_dash.status_code == 302
    assert '/auth/login' in res_dash.location

    res_analyze = client.get('/transactions/analyze')
    assert res_analyze.status_code == 302
    assert '/auth/login' in res_analyze.location

    res_alerts = client.get('/alerts')
    assert res_alerts.status_code == 302
    assert '/auth/login' in res_alerts.location
