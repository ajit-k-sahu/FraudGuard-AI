"""
Machine Learning Model Service and Prediction Engine Test Suite.
Validates model artifact integrity, column transformers, probability calibration, and explainability.
"""

import pytest
import os
from app.services.ml_service import MLService
from app.services.prediction_service import PredictionService

def test_ml_service_singleton_and_artifacts(app):
    ml1 = MLService.get_instance()
    ml2 = MLService.get_instance()
    assert ml1 is ml2
    assert ml1.is_ready() is True

    metadata = ml1.get_metadata()
    assert metadata is not None
    assert 'selected_model' in metadata
    assert 'all_models_evaluation' in metadata
    assert metadata['all_models_evaluation']['Random Forest']['roc_auc'] > 0.80

    features = ml1.get_feature_importances()
    assert isinstance(features, dict)
    assert len(features) > 0

def test_prediction_low_risk_retail_transaction(app):
    with app.app_context():
        low_risk_data = {
            'amount': 25.50,
            'transaction_type': 'Purchase',
            'sender_account': 'C1000000001',
            'receiver_account': 'M2000000001',
            'channel': 'POS',
            'location': 'Domestic',
            'device': 'Mobile App (Recognized)',
            'frequency_24h': 1,
            'account_age_days': 650,
            'previous_amount': 28.00,
            'old_balance_orig': 5000.0,
            'new_balance_orig': 4974.50
        }
        txn, pred, alert = PredictionService.predict_transaction(low_risk_data, auto_commit=False)
        assert txn is not None
        assert pred is not None
        assert pred.fraud_probability < 0.30
        assert pred.risk_level == 'Low'
        assert pred.is_fraud_predicted is False
        assert alert is None

def test_prediction_high_risk_account_takeover(app):
    with app.app_context():
        high_risk_data = {
            'amount': 95000.00,
            'transaction_type': 'Transfer',
            'sender_account': 'C9999999999',
            'receiver_account': 'C8888888888',
            'channel': 'Internet Banking',
            'location': 'International (High-Risk)',
            'device': 'Unknown / New Device',
            'frequency_24h': 15,
            'account_age_days': 2,
            'previous_amount': 15.00,
            'old_balance_orig': 95000.0,
            'new_balance_orig': 0.0
        }
        txn, pred, alert = PredictionService.predict_transaction(high_risk_data, auto_commit=False)
        assert txn is not None
        assert pred is not None
        assert pred.fraud_probability >= 0.70
        assert pred.risk_level == 'High'
        assert pred.is_fraud_predicted is True
        assert alert is not None
        assert alert.severity in ['High', 'Critical']

def test_explainability_and_recommended_actions(app):
    with app.app_context():
        suspicious_data = {
            'amount': 12000.00,
            'transaction_type': 'Transfer',
            'sender_account': 'C5555555555',
            'receiver_account': 'C6666666666',
            'channel': 'Mobile Banking',
            'location': 'International (High-Risk)',
            'device': 'Unknown / New Device',
            'frequency_24h': 8,
            'account_age_days': 15,
            'previous_amount': 200.00
        }
        txn, pred, _ = PredictionService.predict_transaction(suspicious_data, auto_commit=False)
        explanations = pred.get_explanations()
        assert isinstance(explanations, list)
        assert len(explanations) > 0
        assert pred.recommended_action != ''
