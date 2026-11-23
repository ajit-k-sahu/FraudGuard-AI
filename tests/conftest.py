"""
Pytest configuration and shared fixtures for FraudGuard AI test suite.
"""

import pytest
from app import create_app
from app.extensions import db, limiter
from app.models import User, Transaction, Prediction, FraudAlert
from app.services.prediction_service import PredictionService

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Ensures deterministic, isolated rate-limiter state for every test."""
    try:
        limiter.reset()
    except Exception:
        pass
    yield
    try:
        limiter.reset()
    except Exception:
        pass

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Seed test analyst and admin
        analyst = User(name='Alex Analyst', email='analyst@test.com', role='user', is_active_account=True)
        analyst.set_password('AnalystPass123!')

        admin = User(name='Security Admin', email='admin@test.com', role='admin', is_active_account=True)
        admin.set_password('AdminPass123!')

        deactivated = User(name='Blocked User', email='blocked@test.com', role='user', is_active_account=False)
        deactivated.set_password('BlockedPass123!')

        db.session.add_all([analyst, admin, deactivated])
        db.session.commit()

        # Seed a sample baseline transaction for analyst
        txn, pred, alert = PredictionService.predict_transaction({
            'amount': 150.0,
            'transaction_type': 'Payment',
            'channel': 'Mobile Banking',
            'location': 'Domestic',
            'device': 'Mobile App (Recognized)',
            'frequency_24h': 1,
            'account_age_days': 500,
            'previous_amount': 120.0,
            'old_balance_orig': 1500.0,
            'new_balance_orig': 1350.0
        }, user_id=analyst.id, auto_commit=True)

        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def analyst_client(app):
    c = app.test_client()
    c.post('/auth/login', data={'email': 'analyst@test.com', 'password': 'AnalystPass123!'}, follow_redirects=True)
    return c

@pytest.fixture
def admin_client(app):
    c = app.test_client()
    c.post('/auth/login', data={'email': 'admin@test.com', 'password': 'AdminPass123!'}, follow_redirects=True)
    return c
