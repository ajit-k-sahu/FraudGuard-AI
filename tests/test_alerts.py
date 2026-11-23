"""
Fraud Alert Generation and Life-Cycle Test Suite.
Validates alert triggering on high-risk inferences, alert status transitions, and bulk actions.
"""

import pytest
from app.models import FraudAlert, User
from app.services.prediction_service import PredictionService
from app.extensions import db

def test_alert_generation_and_list_view(app):
    with app.app_context():
        analyst = User.query.filter_by(email='analyst@test.com').first()
        # Create high-risk transaction that triggers an alert
        PredictionService.predict_transaction({
            'amount': 99000.0,
            'transaction_type': 'Transfer',
            'sender_account': 'C_ALERT_TEST_1',
            'receiver_account': 'C_ALERT_DEST_1',
            'channel': 'Internet Banking',
            'location': 'International (High-Risk)',
            'device': 'Unknown / New Device',
            'frequency_24h': 18,
            'account_age_days': 1,
            'previous_amount': 5.0,
            'old_balance_orig': 99000.0,
            'new_balance_orig': 0.0
        }, user_id=analyst.id, auto_commit=True)

        alert = FraudAlert.query.filter_by(user_id=analyst.id, is_read=False).first()
        assert alert is not None
        assert alert.severity in ['High', 'Critical']
        alert_id = alert.id

    client = app.test_client()
    client.post('/auth/login', data={'email': 'analyst@test.com', 'password': 'AnalystPass123!'}, follow_redirects=True)
    
    # 1. View alerts page
    res_list = client.get('/alerts')
    assert res_list.status_code == 200
    assert b'Fraud Alerts' in res_list.data or b'Security Alerts' in res_list.data
    assert b'High' in res_list.data or b'HIGH' in res_list.data

    # 2. Mark single alert as read
    res_read = client.post(f'/alerts/{alert_id}/read', follow_redirects=True)
    assert res_read.status_code == 200

    with app.app_context():
        updated_alert = FraudAlert.query.get(alert_id)
        assert updated_alert.is_read is True

    # 3. Mark all as read
    res_all_read = client.post('/alerts/read-all', follow_redirects=True)
    assert res_all_read.status_code == 200

    with app.app_context():
        unread_count = FraudAlert.query.filter_by(user_id=analyst.id, is_read=False).count()
        assert unread_count == 0
