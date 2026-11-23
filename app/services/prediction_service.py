"""
Prediction Service for FraudGuard AI.
Processes incoming transaction records, executes model inference, derives risk classification,
generates explainability factors, and triggers automated fraud alerts.
"""

import json
import uuid
from datetime import datetime
import pandas as pd
from flask import current_app
from app.extensions import db
from app.models import Transaction, Prediction, FraudAlert
from app.services.ml_service import MLService

class PredictionService:
    @staticmethod
    def generate_explanations(data, prob, risk_level):
        """Generates domain-grounded explainability factors based on feature contributions and behavioral anomalies."""
        explanations = []

        amount = float(data.get('amount', 0.0))
        prev_amount = float(data.get('previous_amount', 0.0))
        freq = int(data.get('frequency_24h', 1))
        age = int(data.get('account_age_days', 365))
        device = str(data.get('device', ''))
        location = str(data.get('location', ''))
        t_type = str(data.get('transaction_type', ''))
        old_balance = float(data.get('old_balance_orig', amount * 1.5))
        new_balance = float(data.get('new_balance_orig', max(0.0, old_balance - amount)))

        # 1. Device and Location Risk
        if 'New / Unrecognized' in device:
            explanations.append("Session originated from an unrecognized hardware profile / unregistered device.")
        if 'Cross-Border (Unusual)' in location:
            explanations.append("Cross-border transaction detected from an unverified high-risk jurisdiction.")
        elif 'High-Risk' in location:
            explanations.append("Transaction originates from a newly observed regional geolocation.")

        # 2. Velocity and Account Longevity
        if freq >= 15:
            explanations.append(f"Extreme velocity spike: {freq} transactions recorded within the preceding 24-hour window.")
        elif freq >= 8:
            explanations.append(f"Elevated velocity: {freq} transactions in 24 hours deviates from typical baseline.")

        if age <= 14 and amount >= 3000:
            explanations.append(f"High-exposure new account: Account age is only {age} days old with significant capital movement.")

        # 3. Spending Deviations
        ratio = amount / (prev_amount + 1.0)
        if ratio >= 15.0 and amount >= 2000:
            explanations.append(f"Severe spending outlier: Amount (${amount:,.2f}) is {ratio:.1f}x higher than previous transaction average.")
        elif ratio >= 5.0 and amount >= 1500:
            explanations.append(f"Notable deviation: Transaction size is {ratio:.1f}x greater than recent transaction volume.")

        # 4. Balance Depletion Pattern
        if old_balance > 0 and (amount / old_balance >= 0.90) and t_type in ['Transfer', 'Cash Withdrawal']:
            explanations.append("Account takeover indicator: Originating balance was near-totally drained (>90% balance depletion).")

        # 5. Low Risk Confirmation
        if risk_level == 'Low' and not explanations:
            explanations.append("Transaction amount is well within established historical limits.")
            explanations.append("Originates from an authenticated registered device and known domestic location.")
            explanations.append("Account tenure and transaction frequency match legitimate retail behavioral baselines.")

        return explanations

    @staticmethod
    def get_recommended_action(risk_level, prob):
        if risk_level == 'High':
            return "Immediate Transaction Block. Freeze account outbound channels and escalate to Fraud Operations."
        elif risk_level == 'Medium':
            return "Step-Up Authentication Required. Prompt for Multi-Factor Biometric / OTP Challenge and place on hold."
        else:
            return "Approve Transaction. Proceed through automated clearing with standard continuous telemetry."

    @classmethod
    def predict_transaction(cls, txn_data, user_id=None, is_demo=False, auto_commit=True):
        """
        Executes prediction on single transaction data dictionary.
        Returns (Transaction, Prediction, FraudAlert or None).
        """
        ml = MLService.get_instance()
        if not ml.is_ready():
            raise RuntimeError("Machine Learning inference engine is not ready or models are missing.")

        # Strict input validation & sanitization defense-in-depth
        from app.utils.validators import validate_transaction_payload
        cleaned_data, val_err = validate_transaction_payload(txn_data)
        if val_err:
            raise ValueError(f"Invalid transaction data: {val_err}")
        txn_data = cleaned_data

        # Extract config thresholds
        low_thresh = current_app.config.get('RISK_THRESHOLD_LOW', 0.30) if current_app else 0.30
        high_thresh = current_app.config.get('RISK_THRESHOLD_HIGH', 0.70) if current_app else 0.70

        # Construct single-row DataFrame for pipeline
        df_input = pd.DataFrame([{
            'amount': float(txn_data.get('amount', 0.0)),
            'transaction_type': str(txn_data.get('transaction_type', 'Transfer')),
            'channel': str(txn_data.get('channel', 'Mobile Banking')),
            'location': str(txn_data.get('location', 'Domestic')),
            'device': str(txn_data.get('device', 'Mobile App (Recognized)')),
            'frequency_24h': int(txn_data.get('frequency_24h', 1)),
            'account_age_days': int(txn_data.get('account_age_days', 365)),
            'previous_amount': float(txn_data.get('previous_amount', 0.0)),
            'old_balance_orig': float(txn_data.get('old_balance_orig', float(txn_data.get('amount', 0.0)) * 1.5)),
            'new_balance_orig': float(txn_data.get('new_balance_orig', 0.0))
        }])

        # Predict probability
        pipeline = ml.pipeline
        prob = float(pipeline.predict_proba(df_input)[0, 1])
        is_fraud = bool(prob >= 0.50)

        # Stratify Risk
        if prob >= high_thresh:
            risk_level = 'High'
        elif prob >= low_thresh:
            risk_level = 'Medium'
        else:
            risk_level = 'Low'

        # Generate explainability & actions
        explanations = cls.generate_explanations(txn_data, prob, risk_level)
        recommended_action = cls.get_recommended_action(risk_level, prob)

        # Generate Transaction Record
        ref = txn_data.get('transaction_ref') or f"TXN-{uuid.uuid4().hex[:10].upper()}"
        
        transaction = Transaction(
            transaction_ref=ref,
            user_id=user_id,
            amount=float(txn_data.get('amount', 0.0)),
            transaction_type=str(txn_data.get('transaction_type', 'Transfer')),
            sender_account=str(txn_data.get('sender_account', 'ACC-SENDER')),
            receiver_account=str(txn_data.get('receiver_account', 'ACC-RECEIVER')),
            channel=str(txn_data.get('channel', 'Mobile Banking')),
            location=str(txn_data.get('location', 'Domestic')),
            device=str(txn_data.get('device', 'Mobile App (Recognized)')),
            frequency_24h=int(txn_data.get('frequency_24h', 1)),
            account_age_days=int(txn_data.get('account_age_days', 365)),
            previous_amount=float(txn_data.get('previous_amount', 0.0)),
            old_balance_orig=float(txn_data.get('old_balance_orig', float(txn_data.get('amount', 0.0)) * 1.5)),
            new_balance_orig=float(txn_data.get('new_balance_orig', 0.0)),
            old_balance_dest=float(txn_data.get('old_balance_dest', 0.0)),
            new_balance_dest=float(txn_data.get('new_balance_dest', 0.0)),
            is_demo=is_demo
        )

        db.session.add(transaction)
        db.session.flush()  # obtain transaction.id

        # Prediction Record
        prediction = Prediction(
            transaction_id=transaction.id,
            model_name=ml.metadata.get('selected_model', 'Random Forest'),
            model_version=ml.metadata.get('model_version', '1.0.0'),
            fraud_probability=prob,
            is_fraud_predicted=is_fraud,
            risk_level=risk_level,
            explanation_summary=json.dumps(explanations),
            recommended_action=recommended_action
        )
        db.session.add(prediction)

        # Trigger Automated Alert if Medium or High risk
        alert = None
        if risk_level in ['Medium', 'High']:
            severity = 'Critical' if risk_level == 'High' else 'Medium'
            alert_title = f"{severity.upper()} RISK: Suspicious {transaction.transaction_type} of ${transaction.amount:,.2f}"
            alert_message = f"Transaction {transaction.transaction_ref} flagged with {prob:.1%} fraud probability. Factors: " + "; ".join(explanations[:2])
            
            alert = FraudAlert(
                transaction_id=transaction.id,
                user_id=user_id,
                severity=severity,
                title=alert_title,
                message=alert_message,
                is_read=False
            )
            db.session.add(alert)

        if auto_commit:
            db.session.commit()

        return transaction, prediction, alert
