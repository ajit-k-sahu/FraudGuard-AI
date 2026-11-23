"""
Audit Verification Test Suite.
Validates Flask app factory, SQLAlchemy models, password security,
ML pipeline loading, risk classification, and API endpoints.
"""

import pytest
from app import create_app
from app.extensions import db
from app.models import User, Transaction, Prediction, FraudAlert, AuditLog
from app.services.ml_service import MLService
from app.services.prediction_service import PredictionService

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_app_initialization(app):
    assert app is not None
    assert app.config['TESTING'] is True
    assert 'dashboard' in app.blueprints
    assert 'auth' in app.blueprints
    assert 'transactions' in app.blueprints
    assert 'api' in app.blueprints

def test_user_authentication_and_password_security(app):
    with app.app_context():
        user = User(name='Security Test', email='sec@fraudguard.ai', role='user')
        user.set_password('StrongPassword2026!')
        db.session.add(user)
        db.session.commit()

        # Check password hashing
        assert user.password_hash != 'StrongPassword2026!'
        assert user.check_password('StrongPassword2026!') is True
        assert user.check_password('WrongPassword') is False
        assert user.is_active is True
        assert user.is_admin is False

def test_ml_service_and_artifacts(app):
    ml = MLService.get_instance()
    assert ml.is_ready() is True
    metadata = ml.get_metadata()
    assert metadata is not None
    assert 'selected_model' in metadata
    assert metadata['selected_model'] in ['Random Forest', 'Logistic Regression', 'Gradient Boosting']

def test_prediction_engine_low_and_high_risk(app):
    with app.app_context():
        # High risk transaction
        high_risk_data = {
            'amount': 45000.0,
            'transaction_type': 'Transfer',
            'channel': 'Internet Banking',
            'location': 'Cross-Border (Unusual)',
            'device': 'New / Unrecognized Device',
            'frequency_24h': 16,
            'account_age_days': 8,
            'previous_amount': 50.0
        }
        txn_h, pred_h, alert_h = PredictionService.predict_transaction(high_risk_data, auto_commit=True)
        assert pred_h.fraud_probability > 0.50
        assert pred_h.risk_level == 'High'
        assert pred_h.is_fraud_predicted is True
        assert alert_h is not None
        assert alert_h.severity in ['High', 'Critical']

        # Low risk transaction
        low_risk_data = {
            'amount': 40.0,
            'transaction_type': 'Payment',
            'channel': 'Mobile Banking',
            'location': 'Domestic',
            'device': 'Mobile App (Recognized)',
            'frequency_24h': 1,
            'account_age_days': 500,
            'previous_amount': 45.0
        }
        txn_l, pred_l, alert_l = PredictionService.predict_transaction(low_risk_data, auto_commit=True)
        assert pred_l.fraud_probability < 0.30
        assert pred_l.risk_level == 'Low'
        assert pred_l.is_fraud_predicted is False

def test_api_health_endpoint(client):
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'healthy'
    assert data['database'] == 'connected'
    assert data['ml_model'] == 'loaded'

def test_api_predict_endpoint(client):
    payload = {
        'amount': 38000.0,
        'transaction_type': 'Transfer',
        'channel': 'Internet Banking',
        'location': 'Cross-Border (Unusual)',
        'device': 'New / Unrecognized Device',
        'frequency_24h': 14,
        'account_age_days': 5,
        'previous_amount': 30.0
    }
    res = client.post('/api/v1/predict', json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data['success'] is True
    assert 'prediction' in data['data']
    assert data['data']['prediction']['risk_level'] == 'High'
