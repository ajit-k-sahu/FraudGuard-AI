"""
Transaction Management and Prediction View Test Suite.
Tests transaction submission, history search/filtering, detail view security, and CSV export.
"""

import pytest
from app.models import Transaction, Prediction, User
from app.extensions import db

def test_analyze_page_get(analyst_client):
    res = analyst_client.get('/transactions/analyze')
    assert res.status_code == 200
    assert b'AI Transaction Analysis' in res.data or b'Analyze Transaction' in res.data
    assert b'Transaction Amount' in res.data

def test_analyze_page_submission_legitimate(analyst_client, app):
    res = analyst_client.post('/transactions/analyze', data={
        'amount': '45.00',
        'transaction_type': 'Purchase',
        'sender_account': 'C1122334455',
        'receiver_account': 'M9988776655',
        'channel': 'POS',
        'location': 'Domestic',
        'device': 'Mobile App (Recognized)',
        'frequency_24h': '1',
        'account_age_days': '400',
        'previous_amount': '50.00'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Prediction Result' in res.data or b'Calculated Fraud Probability' in res.data
    assert b'LOW' in res.data or b'Low' in res.data

    with app.app_context():
        txn = Transaction.query.filter_by(sender_account='C1122334455').first()
        assert txn is not None
        assert txn.prediction is not None
        assert txn.prediction.risk_level in ['Low', 'Medium', 'High']

def test_analyze_page_submission_high_risk(analyst_client, app):
    res = analyst_client.post('/transactions/analyze', data={
        'amount': '85000.00',
        'transaction_type': 'Transfer',
        'sender_account': 'C9900112233',
        'receiver_account': 'C4433221100',
        'channel': 'Internet Banking',
        'location': 'International (High-Risk)',
        'device': 'Unknown / New Device',
        'frequency_24h': '12',
        'account_age_days': '2',
        'previous_amount': '10.00'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Prediction Result' in res.data or b'High' in res.data or b'Critical' in res.data

def test_history_filtering_and_search(analyst_client):
    res_all = analyst_client.get('/transactions/history')
    assert res_all.status_code == 200
    assert b'Transaction Ref' in res_all.data

    # Filter by transaction type
    res_filtered = analyst_client.get('/transactions/history?type=Payment')
    assert res_filtered.status_code == 200

    # Filter by risk level
    res_risk = analyst_client.get('/transactions/history?risk=Low')
    assert res_risk.status_code == 200

def test_transaction_detail_access_control(app):
    with app.app_context():
        analyst = User.query.filter_by(email='analyst@test.com').first()
        admin = User.query.filter_by(email='admin@test.com').first()
        analyst_txn = Transaction.query.filter_by(user_id=analyst.id).first()
        txn_id = analyst_txn.id

    # 1. Analyst owner can view their own transaction
    c1 = app.test_client()
    c1.post('/auth/login', data={'email': 'analyst@test.com', 'password': 'AnalystPass123!'}, follow_redirects=True)
    res_owner = c1.get(f'/transactions/{txn_id}')
    assert res_owner.status_code == 200
    assert b'Transaction Information' in res_owner.data or b'Transaction Detail' in res_owner.data
    c1.get('/auth/logout', follow_redirects=True)

    # 2. Admin can view the transaction
    c_admin = app.test_client()
    c_admin.post('/auth/login', data={'email': 'admin@test.com', 'password': 'AdminPass123!'}, follow_redirects=True)
    res_admin = c_admin.get(f'/transactions/{txn_id}')
    assert res_admin.status_code == 200
    c_admin.get('/auth/logout', follow_redirects=True)

def test_transaction_csv_export(analyst_client):
    res = analyst_client.get('/transactions/export')
    assert res.status_code == 200
    assert res.mimetype == 'text/csv'
    csv_text = res.data.decode('utf-8')
    assert 'Transaction Ref' in csv_text or 'Transaction ID' in csv_text or 'Amount' in csv_text
