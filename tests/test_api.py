"""
REST API Endpoint Test Suite.
Validates health monitoring, API authentication, real-time prediction,
batch predictions, model diagnostics, and critical authentication/data exposure protections.
"""

import json
import pytest
from app.extensions import db
from app.models import User, Transaction, Prediction, FraudAlert
from app.services.prediction_service import PredictionService


def test_api_health_endpoint(client):
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'healthy'
    assert data['database'] == 'connected'
    assert data['ml_model'] == 'loaded'


def test_api_auth_login(client):
    # Valid credentials
    res_valid = client.post('/api/v1/auth/login', json={
        'email': 'analyst@test.com',
        'password': 'AnalystPass123!'
    })
    assert res_valid.status_code == 200
    data_valid = res_valid.get_json()
    assert data_valid['success'] is True
    assert data_valid['user']['email'] == 'analyst@test.com'

    # Invalid credentials
    res_invalid = client.post('/api/v1/auth/login', json={
        'email': 'analyst@test.com',
        'password': 'WrongPassword!'
    })
    assert res_invalid.status_code == 401
    assert res_invalid.get_json()['success'] is False


def test_api_predict_endpoint_valid_demo(client, app):
    """
    Unauthenticated caller receives real-time ML prediction in demo mode,
    with zero database pollution (transaction count remains unchanged).
    """
    with app.app_context():
        count_before = Transaction.query.count()

    payload = {
        'amount': 350.00,
        'transaction_type': 'Transfer',
        'sender_account': 'C_API_SENDER',
        'receiver_account': 'C_API_RECEIVER',
        'channel': 'Mobile Banking',
        'location': 'Domestic',
        'device': 'Mobile App (Recognized)',
        'frequency_24h': 2,
        'account_age_days': 400,
        'previous_amount': 300.00
    }
    res = client.post('/api/v1/predict', json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data['success'] is True
    assert 'data' in data
    assert data['data']['is_demo'] is True
    assert 'prediction' in data['data']
    assert 0.0 <= data['data']['prediction']['fraud_probability'] <= 1.0
    assert data['data']['prediction']['risk_level'] in ['Low', 'Medium', 'High']

    # Verify zero database pollution
    with app.app_context():
        count_after = Transaction.query.count()
        assert count_after == count_before


def test_api_predict_endpoint_authenticated(analyst_client, app):
    """
    Authenticated Analyst prediction is saved and linked to analyst user ID.
    """
    with app.app_context():
        analyst = User.query.filter_by(email='analyst@test.com').first()
        count_before = Transaction.query.filter_by(user_id=analyst.id).count()

    payload = {
        'amount': 5200.00,
        'transaction_type': 'Transfer',
        'sender_account': 'C_AUTH_SENDER',
        'receiver_account': 'C_AUTH_RECEIVER',
        'channel': 'Internet Banking',
        'location': 'Cross-Border (Unusual)',
        'device': 'New / Unrecognized Device',
        'frequency_24h': 10,
        'account_age_days': 20,
        'previous_amount': 50.00
    }
    res = analyst_client.post('/api/v1/predict', json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data['success'] is True
    assert data['data']['is_demo'] is False

    with app.app_context():
        count_after = Transaction.query.filter_by(user_id=analyst.id).count()
        assert count_after == count_before + 1
        new_txn = Transaction.query.filter_by(transaction_ref=data['data']['transaction_ref']).first()
        assert new_txn is not None
        assert new_txn.user_id == analyst.id


def test_api_predict_missing_amount_error(client):
    res = client.post('/api/v1/predict', json={
        'transaction_type': 'Payment'
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data['success'] is False
    assert "'amount'" in data['error']


def test_api_predict_batch_endpoint_demo(client, app):
    """Unauthenticated batch prediction <= 10 items works in demo mode with zero DB pollution."""
    with app.app_context():
        count_before = Transaction.query.count()

    payload = {
        'transactions': [
            {'amount': 25.00, 'transaction_type': 'Payment', 'frequency_24h': 1},
            {'amount': 85000.00, 'transaction_type': 'Transfer', 'frequency_24h': 15, 'account_age_days': 2}
        ]
    }
    res = client.post('/api/v1/predict/batch', json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['total'] == 2
    assert data['is_demo'] is True
    assert len(data['results']) == 2
    assert data['results'][0]['status'] == 'success'
    assert data['results'][1]['status'] == 'success'

    with app.app_context():
        count_after = Transaction.query.count()
        assert count_after == count_before


def test_api_predict_batch_endpoint_demo_limit(client):
    """Unauthenticated batch prediction > 10 items is rejected to protect against DoS."""
    payload = {
        'transactions': [{'amount': 10.0, 'transaction_type': 'Payment'}] * 11
    }
    res = client.post('/api/v1/predict/batch', json=payload)
    assert res.status_code == 401
    data = res.get_json()
    assert data['success'] is False
    assert 'limited to 10 transactions' in data['error']


def test_api_predict_batch_endpoint_authenticated(analyst_client, app):
    """Authenticated batch prediction commits records to DB tied to the user."""
    with app.app_context():
        analyst = User.query.filter_by(email='analyst@test.com').first()
        count_before = Transaction.query.filter_by(user_id=analyst.id).count()

    payload = {
        'transactions': [
            {'amount': 150.00, 'transaction_type': 'Payment', 'frequency_24h': 1},
            {'amount': 300.00, 'transaction_type': 'Transfer', 'frequency_24h': 2}
        ]
    }
    res = analyst_client.post('/api/v1/predict/batch', json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['is_demo'] is False
    assert data['total'] == 2

    with app.app_context():
        count_after = Transaction.query.filter_by(user_id=analyst.id).count()
        assert count_after == count_before + 2


# ============================================================================
# CRITICAL SECURITY AUTHENTICATION & DATA EXPOSURE PROTECTION TESTS
# ============================================================================

def test_api_anonymous_transactions_denied(client):
    """Unauthenticated access to transaction listing is strictly blocked with 401."""
    res = client.get('/api/v1/transactions')
    assert res.status_code == 401
    data = res.get_json()
    assert data['success'] is False
    assert 'Authentication required' in data['error']


def test_api_anonymous_transaction_detail_denied(client):
    """Unauthenticated access to transaction details is strictly blocked with 401."""
    res = client.get('/api/v1/transactions/1')
    assert res.status_code == 401
    data = res.get_json()
    assert data['success'] is False
    assert 'Authentication required' in data['error']


def test_api_anonymous_alerts_denied(client):
    """Unauthenticated access to fraud alerts is strictly blocked with 401."""
    res = client.get('/api/v1/alerts')
    assert res.status_code == 401
    data = res.get_json()
    assert data['success'] is False
    assert 'Authentication required' in data['error']


def test_api_anonymous_stats_and_analytics_denied(client):
    """Unauthenticated access to stats and analytics telemetry is blocked with 401."""
    res_stats = client.get('/api/v1/stats')
    assert res_stats.status_code == 401
    assert res_stats.get_json()['success'] is False

    res_analytics = client.get('/api/v1/analytics')
    assert res_analytics.status_code == 401
    assert res_analytics.get_json()['success'] is False


def test_api_analyst_transactions_and_isolation(app, analyst_client):
    """Analyst can only view their own transactions; admin records are never leaked."""
    with app.app_context():
        admin = User.query.filter_by(email='admin@test.com').first()
        analyst = User.query.filter_by(email='analyst@test.com').first()

        # Seed an admin-only transaction
        admin_txn, _, _ = PredictionService.predict_transaction({
            'amount': 9999.00,
            'transaction_type': 'Transfer',
            'sender_account': 'ACC-ADMIN-ONLY',
            'receiver_account': 'ACC-DEST-SECURE'
        }, user_id=admin.id, auto_commit=True)
        admin_ref = admin_txn.transaction_ref

    res = analyst_client.get('/api/v1/transactions')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'transactions' in data

    # Verify that analyst only gets their own transactions, never the admin's transaction
    refs = [t['transaction_ref'] for t in data['transactions']]
    assert admin_ref not in refs
    for t in data['transactions']:
        # In to_dict(), user_id is not included, but transaction_ref must match analyst's
        assert t['transaction_ref'] != admin_ref


def test_api_transaction_detail_access_control(app, analyst_client, admin_client):
    """
    Tests IDOR protection:
    - Analyst can view their own transaction details.
    - Analyst requesting another user's transaction gets 404 (does not disclose existence).
    - Administrator can view any transaction.
    - Non-existent transaction returns 404.
    """
    with app.app_context():
        admin = User.query.filter_by(email='admin@test.com').first()
        analyst = User.query.filter_by(email='analyst@test.com').first()

        analyst_txn = Transaction.query.filter_by(user_id=analyst.id).first()
        analyst_txn_id = analyst_txn.id

        admin_txn, _, _ = PredictionService.predict_transaction({
            'amount': 12000.00,
            'transaction_type': 'Transfer',
            'sender_account': 'ACC-ADMIN-SECRET'
        }, user_id=admin.id, auto_commit=True)
        admin_txn_id = admin_txn.id

    # 1. Analyst views own transaction -> 200 OK
    res_owner = analyst_client.get(f'/api/v1/transactions/{analyst_txn_id}')
    assert res_owner.status_code == 200
    assert res_owner.get_json()['success'] is True
    assert res_owner.get_json()['transaction']['id'] == analyst_txn_id

    # 2. Analyst attempts to view admin's transaction -> 404 Not Found (Zero information leakage)
    res_unauth = analyst_client.get(f'/api/v1/transactions/{admin_txn_id}')
    assert res_unauth.status_code == 404
    assert res_unauth.get_json()['success'] is False
    assert res_unauth.get_json()['error'] == 'Transaction not found.'

    # 3. Administrator views analyst's transaction -> 200 OK
    res_admin = admin_client.get(f'/api/v1/transactions/{analyst_txn_id}')
    assert res_admin.status_code == 200
    assert res_admin.get_json()['success'] is True

    # 4. Non-existent transaction -> 404 Not Found
    res_404 = analyst_client.get('/api/v1/transactions/999999')
    assert res_404.status_code == 404
    assert res_404.get_json()['error'] == 'Transaction not found.'


def test_api_alerts_access_control(app):
    """
    Validates alert scoping:
    - Analyst only receives alerts generated for their own transactions.
    - Administrator receives all system alerts.
    """
    with app.app_context():
        admin = User.query.filter_by(email='admin@test.com').first()
        analyst = User.query.filter_by(email='analyst@test.com').first()

        # Seed high-risk transaction for admin to generate an admin alert
        admin_txn, _, admin_alert = PredictionService.predict_transaction({
            'amount': 95000.00,
            'transaction_type': 'Transfer',
            'location': 'Cross-Border (Unusual)',
            'device': 'New / Unrecognized Device',
            'frequency_24h': 20,
            'account_age_days': 2
        }, user_id=admin.id, auto_commit=True)
        assert admin_alert is not None
        admin_alert_id = admin_alert.id
        db.session.remove()

    # Analyst alerts query
    c_analyst = app.test_client()
    c_analyst.post('/auth/login', data={'email': 'analyst@test.com', 'password': 'AnalystPass123!'}, follow_redirects=True)
    res_analyst = c_analyst.get('/api/v1/alerts')
    assert res_analyst.status_code == 200
    analyst_alerts = res_analyst.get_json()['alerts']
    analyst_alert_ids = [a['id'] for a in analyst_alerts]
    # Admin alert must NOT be visible to analyst
    assert admin_alert_id not in analyst_alert_ids
    c_analyst.get('/auth/logout', follow_redirects=True)

    # Admin alerts query
    c_admin = app.test_client()
    c_admin.post('/auth/login', data={'email': 'admin@test.com', 'password': 'AdminPass123!'}, follow_redirects=True)
    res_admin = c_admin.get('/api/v1/alerts')
    assert res_admin.status_code == 200
    admin_alerts = res_admin.get_json()['alerts']
    admin_alert_ids = [a['id'] for a in admin_alerts]
    assert admin_alert_id in admin_alert_ids
    c_admin.get('/auth/logout', follow_redirects=True)


def test_api_stats_and_analytics_authenticated(analyst_client, admin_client):
    """Authenticated analyst and admin can access stats and analytics."""
    res_stats = analyst_client.get('/api/v1/stats')
    assert res_stats.status_code == 200
    assert res_stats.get_json()['success'] is True

    res_analytics = analyst_client.get('/api/v1/analytics')
    assert res_analytics.status_code == 200
    assert res_analytics.get_json()['success'] is True

    res_admin_stats = admin_client.get('/api/v1/stats')
    assert res_admin_stats.status_code == 200
    assert res_admin_stats.get_json()['success'] is True


def test_api_model_info_diagnostics(client):
    res = client.get('/api/v1/model-info')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['model_status'] == 'ready'
    assert 'metadata' in data
    assert 'top_feature_importance' in data
