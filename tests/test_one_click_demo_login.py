"""
Automated Test Suite for Secure One-Click Recruiter Demo Login (Phase B, Task 1.4).

Verifies:
1. Successful one-click demo login provisions account, sets session, and redirects to /dashboard.
2. New unique ephemeral user is created for each visitor.
3. Separate users receive isolated transactions and alerts with disjoint IDs.
4. Existing baseline data on permanent analyst account remains unchanged.
5. User receives analyst-level permissions only (role='user', is_admin=False).
6. Administrator routes remain inaccessible (HTTP 403 Forbidden).
7. CSRF protection rejects invalid requests without CSRF token when enabled.
8. GET requests cannot create demo accounts (HTTP 405 Method Not Allowed).
9. Rate limiting blocks excessive provisioning attempts (HTTP 429 Too Many Requests).
10. Failed provisioning rolls back user and cloned records atomically without orphan rows.
11. Expired demo sessions are rejected immediately by active expiration checks.
12. Permanent analyst and administrator login continue working normally via standard login.
13. Existing public registration and login flows remain fully functional.
14. Demo login does not expose passwords or sensitive credentials in rendered pages.
15. Safe redirect behavior prevents open redirect attacks.
"""

import os
import re
import uuid
from datetime import timedelta
from flask import g
import pytest

from app.extensions import db, limiter
from app.models import User, Transaction, Prediction, FraudAlert, utc_now
from app.services.prediction_service import PredictionService
from app.services.demo_service import DemoService


@pytest.fixture
def baseline_demo_data(app):
    """Seeds approved baseline demo data on the permanent analyst account in the test database."""
    with app.app_context():
        demo_analyst = User.query.filter_by(email='analyst@bank.com').first()
        if not demo_analyst:
            demo_analyst = User(
                name='Alex Mercer (Fraud Analyst)',
                email='analyst@bank.com',
                role='user',
                is_active_account=True,
                is_ephemeral=False
            )
            demo_analyst.set_password('AnalystPass123!')
            db.session.add(demo_analyst)
            db.session.commit()

        scenarios = [
            {
                'amount': 45.0,
                'transaction_type': 'Purchase',
                'sender_account': 'C1092834',
                'receiver_account': 'M8371920',
                'channel': 'POS',
                'location': 'Domestic',
                'device': 'POS Terminal',
                'frequency_24h': 1,
                'account_age_days': 450,
                'previous_amount': 40.0
            },
            {
                'amount': 3800.0,
                'transaction_type': 'Transfer',
                'sender_account': 'C4918273',
                'receiver_account': 'C8172635',
                'channel': 'Internet Banking',
                'location': 'High-Risk Domestic',
                'device': 'New / Unrecognized Device',
                'frequency_24h': 5,
                'account_age_days': 45,
                'previous_amount': 600.0
            },
            {
                'amount': 48500.0,
                'transaction_type': 'Transfer',
                'sender_account': 'C6928104',
                'receiver_account': 'C1029384',
                'channel': 'Internet Banking',
                'location': 'Cross-Border (Unusual)',
                'device': 'New / Unrecognized Device',
                'frequency_24h': 12,
                'account_age_days': 10,
                'previous_amount': 25000.0
            }
        ]

        for sc in scenarios:
            PredictionService.predict_transaction(
                txn_data=sc,
                user_id=demo_analyst.id,
                is_demo=True,
                auto_commit=True
            )

        yield demo_analyst


def test_successful_one_click_demo_login(app, baseline_demo_data):
    """Test 1: Successful one-click demo login provisions account and redirects to dashboard."""
    client = app.test_client()
    res = client.post('/auth/demo-login', follow_redirects=True)
    assert res.status_code == 200

    html = res.get_data(as_text=True)
    assert "Welcome to your isolated demonstration workspace" in html
    assert "Dashboard" in html

    # Verify user exists in database and is authenticated
    with app.app_context():
        user = User.query.filter_by(is_ephemeral=True).order_by(User.id.desc()).first()
        assert user is not None
        assert user.is_ephemeral is True
        assert user.is_demo_account is True
        assert user.transactions.count() > 0


def test_unique_ephemeral_user_created_for_each_visitor(app, baseline_demo_data):
    """Test 2: Each visitor receives a new unique ephemeral user."""
    client1 = app.test_client()
    res1 = client1.post('/auth/demo-login', follow_redirects=True)
    assert res1.status_code == 200

    # Clear application context user cache between simulated distinct visitor clients
    g.pop('_login_user', None)

    client2 = app.test_client()
    res2 = client2.post('/auth/demo-login', follow_redirects=True)
    assert res2.status_code == 200

    with app.app_context():
        ephemeral_users = User.query.filter_by(is_ephemeral=True).all()
        assert len(ephemeral_users) >= 2
        u1, u2 = ephemeral_users[-2], ephemeral_users[-1]
        assert u1.id != u2.id
        assert u1.email != u2.email
        assert u1.email.startswith("recruiter_")
        assert u2.email.startswith("recruiter_")


def test_separate_users_receive_isolated_transactions_and_alerts(app, baseline_demo_data):
    """Test 3: Separate users receive isolated transactions and alerts with disjoint IDs."""
    client1 = app.test_client()
    client1.post('/auth/demo-login', follow_redirects=True)

    # Clear application context user cache between simulated distinct visitor clients
    g.pop('_login_user', None)

    client2 = app.test_client()
    client2.post('/auth/demo-login', follow_redirects=True)

    with app.app_context():
        u1, u2 = User.query.filter_by(is_ephemeral=True).order_by(User.id.desc()).limit(2).all()
        txns1 = {t.id for t in u1.transactions.all()}
        txns2 = {t.id for t in u2.transactions.all()}
        assert len(txns1) > 0
        assert len(txns2) > 0
        assert txns1.isdisjoint(txns2)

        alerts1 = {a.id for a in u1.alerts.all()}
        alerts2 = {a.id for a in u2.alerts.all()}
        assert alerts1.isdisjoint(alerts2)


def test_existing_baseline_data_remains_unchanged(app, baseline_demo_data):
    """Test 4: Existing baseline data on permanent analyst account remains unchanged."""
    with app.app_context():
        initial_baseline_count = Transaction.query.filter_by(user_id=baseline_demo_data.id).count()

    client = app.test_client()
    client.post('/auth/demo-login', follow_redirects=True)

    with app.app_context():
        after_count = Transaction.query.filter_by(user_id=baseline_demo_data.id).count()
        assert after_count == initial_baseline_count


def test_user_receives_analyst_permissions_only(app, baseline_demo_data):
    """Test 5: Ephemeral demo user receives role='user' and is_admin=False."""
    client = app.test_client()
    client.post('/auth/demo-login', follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(is_ephemeral=True).order_by(User.id.desc()).first()
        assert user.role == 'user'
        assert user.is_admin is False


def test_admin_routes_remain_inaccessible(app, baseline_demo_data):
    """Test 6: Administrator routes remain inaccessible to ephemeral demo user (HTTP 403)."""
    client = app.test_client()
    client.post('/auth/demo-login', follow_redirects=True)

    for route in ['/admin/', '/admin/audit-logs', '/admin/model-diagnostics']:
        res = client.get(route)
        assert res.status_code == 403


def test_csrf_protection_rejects_invalid_requests(app, baseline_demo_data):
    """Test 7: CSRF protection rejects requests lacking CSRF token when enabled."""
    app.config['WTF_CSRF_ENABLED'] = True
    c = app.test_client()

    # Request without token is rejected with 400
    res_no_token = c.post('/auth/demo-login')
    assert res_no_token.status_code == 400

    # Request with valid CSRF token extracted from login page succeeds
    res_login_page = c.get('/auth/login')
    html = res_login_page.get_data(as_text=True)
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html) or re.search(r'value="([^"]+)"[^>]*name="csrf_token"', html)
    assert match is not None
    token = match.group(1)

    res_with_token = c.post('/auth/demo-login', data={'csrf_token': token}, follow_redirects=False)
    assert res_with_token.status_code == 302
    assert '/dashboard' in res_with_token.headers['Location']

    app.config['WTF_CSRF_ENABLED'] = False


def test_get_requests_cannot_create_demo_accounts(app):
    """Test 8: GET requests cannot create demo accounts (HTTP 405 Method Not Allowed)."""
    client = app.test_client()
    res = client.get('/auth/demo-login')
    assert res.status_code == 405


def test_rate_limiting_blocks_excessive_provisioning(app):
    """Test 9: Rate limiting blocks excessive demo provisioning requests (HTTP 429)."""
    limiter.reset()
    client = app.test_client()

    # Limit is 10/minute
    for i in range(10):
        client.post('/auth/demo-login')

    # 11th request must be rate limited
    res11 = client.post('/auth/demo-login')
    assert res11.status_code == 429
    assert b'429' in res11.data or b'Too Many Requests' in res11.data


def test_failed_provisioning_rolls_back_user_and_cloned_records(app, monkeypatch):
    """Test 10: Failed provisioning rolls back user and cloned records atomically without orphan rows."""
    def mock_clone(user_id):
        raise RuntimeError("Simulated failure during transaction cloning")

    monkeypatch.setattr(DemoService, 'clone_baseline_data_for_user', mock_clone)

    with app.app_context():
        initial_user_count = User.query.count()

    client = app.test_client()
    res = client.post('/auth/demo-login', follow_redirects=True)
    assert res.status_code == 200

    # User is redirected to login with error flash
    html = res.get_data(as_text=True)
    assert "Unable to provision live demonstration workspace" in html

    # Zero orphan user rows created
    with app.app_context():
        assert User.query.count() == initial_user_count
        assert User.query.filter_by(is_ephemeral=True).count() == 0


def test_expired_demo_sessions_rejected(app, baseline_demo_data):
    """Test 11: Expired demo sessions are rejected immediately by active expiration checks."""
    client = app.test_client()
    client.post('/auth/demo-login', follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(is_ephemeral=True).order_by(User.id.desc()).first()
        # Age account past 2 hours
        user.created_at = utc_now() - timedelta(hours=3)
        db.session.commit()

    # Clear request context user cache so Flask-Login user_loader loads from session
    g.pop('_login_user', None)

    # Next request rejected
    res = client.get('/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/auth/login' in res.headers['Location']


def test_permanent_analyst_and_administrator_login_continue_working(app, baseline_demo_data):
    """Test 12: Permanent analyst and administrator login continue working via standard login."""
    client = app.test_client()

    # Analyst login
    res_analyst = client.post('/auth/login', data={
        'email': 'analyst@bank.com',
        'password': 'AnalystPass123!'
    }, follow_redirects=True)
    assert res_analyst.status_code == 200
    assert "Alex Mercer" in res_analyst.get_data(as_text=True)

    client.get('/auth/logout', follow_redirects=True)
    g.pop('_login_user', None)

    # Administrator login
    res_admin = client.post('/auth/login', data={
        'email': 'admin@test.com',
        'password': 'AdminPass123!'
    }, follow_redirects=True)
    assert res_admin.status_code == 200
    assert "Security Admin" in res_admin.get_data(as_text=True)


def test_existing_registration_and_login_flows_remain_functional(app):
    """Test 13: Existing public registration and login flows remain functional."""
    client = app.test_client()
    reg_email = f"new_registered_{uuid.uuid4().hex[:6]}@bank.com"

    # Register
    res_reg = client.post('/auth/register', data={
        'name': 'New Registered User',
        'email': reg_email,
        'password': 'StrongPassword123!',
        'confirm_password': 'StrongPassword123!'
    }, follow_redirects=True)
    assert res_reg.status_code == 200

    # Clear g._login_user if any
    g.pop('_login_user', None)

    # Log in
    res_login = client.post('/auth/login', data={
        'email': reg_email,
        'password': 'StrongPassword123!'
    }, follow_redirects=True)
    assert res_login.status_code == 200
    assert "New Registered User" in res_login.get_data(as_text=True)

    with app.app_context():
        u = User.query.filter_by(email=reg_email).first()
        assert u is not None
        assert u.is_ephemeral is False
        assert u.role == 'user'


def test_demo_login_does_not_expose_passwords_or_credentials(app):
    """Test 14: Demo login forms do not expose plaintext passwords or credentials."""
    client = app.test_client()

    for path in ['/', '/auth/login']:
        res = client.get(path)
        content = res.get_data(as_text=True)
        assert 'AdminPass123!' not in content
        assert 'AdminSecurePassword' not in content
        assert 'AnalystPass123!' not in content
        assert 'Launch Instant Recruiter Demo' in content or 'Try Live Demo' in content


def test_safe_redirect_behavior(app, baseline_demo_data):
    """Test 15: Safe redirect behavior prevents open redirect attacks."""
    client = app.test_client()

    # Attempt to redirect to external attacker URL
    res = client.post('/auth/demo-login?next=https://evil.com', follow_redirects=False)
    assert res.status_code == 302
    # Must redirect safely to internal dashboard
    assert res.headers['Location'] == '/dashboard'
    assert 'evil.com' not in res.headers['Location']
