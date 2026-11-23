"""
Frontend Views and Route Test Suite for FraudGuard AI.
Tests every user-facing template, form submission, and administrator restriction.
"""

import pytest
from app import create_app
from app.extensions import db
from app.models import User, Transaction, Prediction, FraudAlert, AuditLog
from app.services.prediction_service import PredictionService

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.drop_all()
        db.create_all()
        # Seed test analyst and admin
        analyst = User(name='Alex Analyst', email='analyst@test.com', role='user')
        analyst.set_password('AnalystPass123!')
        admin = User(name='Security Admin', email='admin@test.com', role='admin')
        admin.set_password('AdminPass123!')
        db.session.add_all([analyst, admin])
        db.session.commit()

        # Seed sample transaction
        txn, pred, alert = PredictionService.predict_transaction({
            'amount': 150.0,
            'transaction_type': 'Payment',
            'channel': 'Mobile Banking',
            'location': 'Domestic',
            'device': 'Mobile App (Recognized)',
            'frequency_24h': 1,
            'account_age_days': 500,
            'previous_amount': 120.0
        }, user_id=analyst.id, auto_commit=True)

        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_public_pages(client):
    assert client.get('/').status_code == 200
    assert client.get('/auth/login').status_code == 200
    assert client.get('/auth/register').status_code == 200
    assert client.get('/api/health').status_code == 200

def test_login_and_logout_flow(client):
    # Login
    res = client.post('/auth/login', data={'email': 'analyst@test.com', 'password': 'AnalystPass123!'}, follow_redirects=True)
    assert res.status_code == 200
    assert b'Alex Analyst' in res.data or b'Dashboard' in res.data

    # Logout
    res_logout = client.get('/auth/logout', follow_redirects=True)
    assert res_logout.status_code == 200
    assert b'Sign In' in res_logout.data

def test_transaction_views(client, app):
    with client:
        client.post('/auth/login', data={'email': 'analyst@test.com', 'password': 'AnalystPass123!'}, follow_redirects=True)

        # 1. Analyze page GET and POST
        res_analyze = client.get('/transactions/analyze')
        assert res_analyze.status_code == 200

        res_post = client.post('/transactions/analyze', data={
            'amount': '350.00',
            'transaction_type': 'Transfer',
            'sender_account': 'C1092834',
            'receiver_account': 'C9928172',
            'channel': 'Mobile Banking',
            'location': 'Domestic',
            'device': 'Mobile App (Recognized)',
            'frequency_24h': '2',
            'account_age_days': '300',
            'previous_amount': '300.00'
        }, follow_redirects=True)
        assert res_post.status_code == 200
        assert b'Prediction Result' in res_post.data or b'Calculated Fraud Probability' in res_post.data

        # 2. History view
        res_history = client.get('/transactions/history')
        assert res_history.status_code == 200

        # 3. Detail view
        with app.app_context():
            txn = Transaction.query.first()
        res_detail = client.get(f'/transactions/{txn.id}')
        assert res_detail.status_code == 200

        # 4. Batch page and sample download
        assert client.get('/transactions/batch').status_code == 200
        res_sample = client.get('/transactions/batch/sample')
        assert res_sample.status_code == 200
        assert res_sample.mimetype == 'text/csv'

        # 5. Export CSV
        res_export = client.get('/transactions/export')
        assert res_export.status_code == 200
        assert res_export.mimetype == 'text/csv'

def test_alerts_and_analytics_views(client):
    with client:
        client.post('/auth/login', data={'email': 'analyst@test.com', 'password': 'AnalystPass123!'}, follow_redirects=True)
        assert client.get('/alerts').status_code == 200
        assert client.get('/analytics').status_code == 200
        assert client.get('/analytics/data').status_code == 200
        assert client.get('/profile').status_code == 200

def test_rbac_admin_security(app):
    # 1. Ordinary analyst user is blocked from admin console (403 Forbidden)
    analyst_client = app.test_client()
    analyst_client.post('/auth/login', data={'email': 'analyst@test.com', 'password': 'AnalystPass123!'}, follow_redirects=True)
    res_blocked = analyst_client.get('/admin')
    assert res_blocked.status_code == 403
    analyst_client.get('/auth/logout', follow_redirects=True)

    # 2. Administrator is granted access to admin console (200 OK)
    admin_client = app.test_client()
    res_login = admin_client.post('/auth/login', data={'email': 'admin@test.com', 'password': 'AdminPass123!'}, follow_redirects=True)
    assert res_login.status_code == 200
    res_admin = admin_client.get('/admin')
    assert res_admin.status_code == 200
    assert admin_client.get('/admin/audit-logs').status_code == 200
    assert admin_client.get('/admin/model-diagnostics').status_code == 200
