"""
Demonstration Data Seeding Script for FraudGuard AI.
Creates demo administrator and analyst accounts, and seeds sample financial transactions
with genuine predictions from the trained machine learning pipeline.
All seeded records are clearly identified with is_demo=True.
"""

import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import User, Transaction, Prediction, FraudAlert
from app.services.prediction_service import PredictionService

def seed_database():
    app = create_app('development')
    with app.app_context():
        print("=== Seeding FraudGuard AI Demonstration Data ===")
        db.create_all()

        # 1. Seed or update Admin User
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@fraudguard.ai').lower().strip()
        admin = User.query.filter_by(email=admin_email).first()
        admin_password = os.environ.get('ADMIN_PASSWORD')
        env_mode = os.environ.get('FLASK_ENV', 'development').lower()

        if not admin:
            if env_mode == 'production' and not admin_password:
                print("PRODUCTION SECURITY NOTICE: ADMIN_PASSWORD environment variable not set. Administrator account creation skipped to prevent default credentials in production.")
            else:
                effective_password = admin_password or 'AdminDevPassword2026!'
                admin = User(
                    name="Security Administrator",
                    email=admin_email,
                    role="admin",
                    is_active_account=True
                )
                admin.set_password(effective_password)
                db.session.add(admin)
                print(f"Created Admin account: {admin.email}")
        else:
            print(f"Admin account already exists: {admin.email}")

        # 2. Seed Analyst User
        analyst_email = "analyst@bank.com"
        analyst = User.query.filter_by(email=analyst_email).first()
        if not analyst:
            analyst = User(
                name="Alex Mercer (Fraud Analyst)",
                email=analyst_email,
                role="user",
                is_active_account=True
            )
            analyst.set_password("AnalystPass123!")
            db.session.add(analyst)
            print(f"Created Analyst account: {analyst.email}")
        else:
            print(f"Analyst account already exists: {analyst.email}")

        db.session.commit()

        # 3. Sample Financial Scenarios
        scenarios = [
            # Legitimate Retail
            {
                'amount': 45.00,
                'transaction_type': 'Purchase',
                'sender_account': 'C1092834',
                'receiver_account': 'M8371920',
                'channel': 'POS',
                'location': 'Domestic',
                'device': 'POS Terminal',
                'frequency_24h': 1,
                'account_age_days': 450,
                'previous_amount': 40.00
            },
            {
                'amount': 120.00,
                'transaction_type': 'Payment',
                'sender_account': 'C2938471',
                'receiver_account': 'M9928172',
                'channel': 'Mobile Banking',
                'location': 'Domestic',
                'device': 'Mobile App (Recognized)',
                'frequency_24h': 2,
                'account_age_days': 680,
                'previous_amount': 110.00
            },
            {
                'amount': 550.00,
                'transaction_type': 'Transfer',
                'sender_account': 'C3847192',
                'receiver_account': 'C9182734',
                'channel': 'Internet Banking',
                'location': 'Domestic',
                'device': 'Web Browser (Recognized)',
                'frequency_24h': 3,
                'account_age_days': 820,
                'previous_amount': 480.00
            },
            # Suspicious / Medium Risk
            {
                'amount': 3800.00,
                'transaction_type': 'Transfer',
                'sender_account': 'C4918273',
                'receiver_account': 'C8172635',
                'channel': 'Internet Banking',
                'location': 'High-Risk Domestic',
                'device': 'New / Unrecognized Device',
                'frequency_24h': 5,
                'account_age_days': 45,
                'previous_amount': 600.00
            },
            {
                'amount': 2200.00,
                'transaction_type': 'Payment',
                'sender_account': 'C5829103',
                'receiver_account': 'M3847192',
                'channel': 'UPI',
                'location': 'Domestic',
                'device': 'New / Unrecognized Device',
                'frequency_24h': 7,
                'account_age_days': 120,
                'previous_amount': 350.00
            },
            # Critical / High-Risk Attacks
            {
                'amount': 48500.00,
                'transaction_type': 'Transfer',
                'sender_account': 'C6928104',
                'receiver_account': 'C1029384',
                'channel': 'Internet Banking',
                'location': 'Cross-Border (Unusual)',
                'device': 'New / Unrecognized Device',
                'frequency_24h': 16,
                'account_age_days': 14,
                'previous_amount': 80.00
            },
            {
                'amount': 28000.00,
                'transaction_type': 'Cash Withdrawal',
                'sender_account': 'C7819203',
                'receiver_account': 'C5591827',
                'channel': 'Internet Banking',
                'location': 'Cross-Border (Unusual)',
                'device': 'New / Unrecognized Device',
                'frequency_24h': 11,
                'account_age_days': 90,
                'previous_amount': 150.00
            },
            {
                'amount': 950.00,
                'transaction_type': 'Transfer',
                'sender_account': 'C8829102',
                'receiver_account': 'C9938172',
                'channel': 'UPI',
                'location': 'High-Risk Domestic',
                'device': 'New / Unrecognized Device',
                'frequency_24h': 36,  # Extreme velocity
                'account_age_days': 60,
                'previous_amount': 50.00
            }
        ]

        print(f"Ingesting {len(scenarios)} demonstration scenarios through the ML pipeline...")
        for sc in scenarios:
            # Check if ref already exists
            txn, pred, alert = PredictionService.predict_transaction(
                txn_data=sc,
                user_id=analyst.id,
                is_demo=True,
                auto_commit=True
            )
            print(f"  [{pred.risk_level.upper()}] {txn.transaction_ref}: ${txn.amount:,.2f} ({pred.fraud_probability:.1%})")

        print("=== Seeding Complete! Demo data ready for inspection. ===")

if __name__ == '__main__':
    seed_database()
