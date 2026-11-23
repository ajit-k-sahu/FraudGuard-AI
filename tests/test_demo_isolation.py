"""
Automated Test Suite for Ephemeral Recruiter Demo Isolation (Phase B, Task 1.3).

Verifies:
1. Two ephemeral users receive different IDs and emails.
2. Both accounts have role='user' and is_ephemeral=True.
3. Each user receives their own baseline transactions.
4. Prediction records are correctly associated.
5. Fraud alerts are correctly associated.
6. No primary keys are duplicated.
7. Failure during cloning rolls back partial account creation.
8. Expired ephemeral users are eligible for cleanup.
9. Non-expired ephemeral users are preserved.
10. Permanent analyst and administrator accounts are never deleted.
11. Cleanup removes all associated records.
12. Ephemeral accounts cannot modify their password or identity.
13. Existing authentication and authorization behavior remains intact.
"""

import uuid
from datetime import datetime, timedelta
import pytest

from app.extensions import db
from app.models import User, Transaction, Prediction, FraudAlert
from app.services.prediction_service import PredictionService
from app.services.demo_service import DemoService


@pytest.fixture
def baseline_demo_data(app):
    """Seeds baseline demo data for the permanent demo analyst account in the test database."""
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

        # Seed 3 representative baseline scenarios: Low, Medium, and High risk
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
                'frequency_24h': 16,
                'account_age_days': 14,
                'previous_amount': 80.0
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


def test_ephemeral_users_have_unique_identities(app, baseline_demo_data):
    """Test 1: Two ephemeral users receive different IDs and emails."""
    with app.app_context():
        u1 = DemoService.create_ephemeral_demo_user()
        u2 = DemoService.create_ephemeral_demo_user()

        assert u1.id is not None
        assert u2.id is not None
        assert u1.id != u2.id
        assert u1.email != u2.email
        assert u1.email.startswith('recruiter_')
        assert u2.email.startswith('recruiter_')
        assert u1.email.endswith('@demo.local')
        assert u2.email.endswith('@demo.local')


def test_ephemeral_accounts_roles_and_flags(app, baseline_demo_data):
    """Test 2: Both accounts have role='user' and is_ephemeral=True."""
    with app.app_context():
        u = DemoService.create_ephemeral_demo_user()

        assert u.role == 'user'
        assert u.is_admin is False
        assert u.is_ephemeral is True
        assert u.is_demo_account is True
        assert u.is_active is True


def test_each_user_receives_independent_baseline_transactions(app, baseline_demo_data):
    """Test 3: Each user receives their own baseline transactions."""
    with app.app_context():
        u1 = DemoService.create_ephemeral_demo_user()
        u2 = DemoService.create_ephemeral_demo_user()

        txns1 = u1.transactions.all()
        txns2 = u2.transactions.all()

        assert len(txns1) == 3
        assert len(txns2) == 3

        # Transaction IDs and refs must be distinct
        ids1 = {t.id for t in txns1}
        ids2 = {t.id for t in txns2}
        assert ids1.isdisjoint(ids2)

        refs1 = {t.transaction_ref for t in txns1}
        refs2 = {t.transaction_ref for t in txns2}
        assert refs1.isdisjoint(refs2)

        # Ownership must match exactly
        for t in txns1:
            assert t.user_id == u1.id
            assert t.is_demo is True
        for t in txns2:
            assert t.user_id == u2.id
            assert t.is_demo is True


def test_prediction_records_correctly_associated(app, baseline_demo_data):
    """Test 4: Prediction records are correctly associated with cloned transactions."""
    with app.app_context():
        u1 = DemoService.create_ephemeral_demo_user()
        u2 = DemoService.create_ephemeral_demo_user()

        for t in u1.transactions.all():
            assert t.prediction is not None
            assert t.prediction.transaction_id == t.id
            assert t.prediction.risk_level in ['Low', 'Medium', 'High']

        for t in u2.transactions.all():
            assert t.prediction is not None
            assert t.prediction.transaction_id == t.id
            assert t.prediction.risk_level in ['Low', 'Medium', 'High']

        preds1 = {t.prediction.id for t in u1.transactions.all()}
        preds2 = {t.prediction.id for t in u2.transactions.all()}
        assert preds1.isdisjoint(preds2)


def test_fraud_alerts_correctly_associated(app, baseline_demo_data):
    """Test 5: Fraud alerts are correctly associated with cloned transactions and user."""
    with app.app_context():
        u1 = DemoService.create_ephemeral_demo_user()
        u2 = DemoService.create_ephemeral_demo_user()

        alerts1 = u1.alerts.all()
        alerts2 = u2.alerts.all()

        # Medium and High risk baseline scenarios generate alerts (2 per user)
        assert len(alerts1) == 2
        assert len(alerts2) == 2

        alert_ids1 = {a.id for a in alerts1}
        alert_ids2 = {a.id for a in alerts2}
        assert alert_ids1.isdisjoint(alert_ids2)

        for a in alerts1:
            assert a.user_id == u1.id
            assert a.transaction.user_id == u1.id

        for a in alerts2:
            assert a.user_id == u2.id
            assert a.transaction.user_id == u2.id


def test_no_primary_keys_duplicated(app, baseline_demo_data):
    """Test 6: No primary keys are duplicated across baseline and cloned entities."""
    with app.app_context():
        u = DemoService.create_ephemeral_demo_user()

        all_txns = Transaction.query.all()
        txn_ids = [t.id for t in all_txns]
        assert len(txn_ids) == len(set(txn_ids))

        all_preds = Prediction.query.all()
        pred_ids = [p.id for p in all_preds]
        assert len(pred_ids) == len(set(pred_ids))

        all_alerts = FraudAlert.query.all()
        alert_ids = [a.id for a in all_alerts]
        assert len(alert_ids) == len(set(alert_ids))


def test_failure_during_cloning_rolls_back_partial_creation(app, monkeypatch):
    """Test 7: Failure during cloning rolls back partial account creation atomically."""
    with app.app_context():
        # Force an error inside clone_baseline_data_for_user
        def mock_clone(user_id):
            raise RuntimeError("Database storage failure during clone")

        monkeypatch.setattr(DemoService, 'clone_baseline_data_for_user', mock_clone)

        initial_user_count = User.query.count()

        with pytest.raises(RuntimeError, match="Database storage failure during clone"):
            DemoService.create_ephemeral_demo_user()

        # Database must be rolled back; no orphan user created
        assert User.query.count() == initial_user_count
        assert User.query.filter_by(is_ephemeral=True).count() == 0


def test_expired_ephemeral_users_eligible_for_cleanup(app, baseline_demo_data):
    """Test 8: Expired ephemeral users are eligible for cleanup."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_id = user.id

        # Artificially age the account past 2 hours
        user.created_at = datetime.utcnow() - timedelta(hours=3)
        db.session.commit()

        deleted = DemoService.cleanup_expired_demo_sessions(max_age_hours=2)
        assert deleted >= 1
        assert User.query.get(user_id) is None


def test_non_expired_ephemeral_users_preserved(app, baseline_demo_data):
    """Test 9: Non-expired ephemeral users are preserved during cleanup."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_id = user.id

        # Account is fresh (created just now)
        deleted = DemoService.cleanup_expired_demo_sessions(max_age_hours=2)
        assert User.query.get(user_id) is not None


def test_permanent_users_never_deleted(app, baseline_demo_data):
    """Test 10: Permanent analyst and administrator accounts are never deleted."""
    with app.app_context():
        admin = User.query.filter_by(email='admin@test.com').first()
        analyst = User.query.filter_by(email='analyst@test.com').first()
        demo_analyst = User.query.filter_by(email='analyst@bank.com').first()

        # Artificially age permanent accounts past 100 days
        ancient_date = datetime.utcnow() - timedelta(days=100)
        admin.created_at = ancient_date
        analyst.created_at = ancient_date
        demo_analyst.created_at = ancient_date
        db.session.commit()

        DemoService.cleanup_expired_demo_sessions(max_age_hours=2)

        # Permanent accounts must still exist
        assert User.query.filter_by(email='admin@test.com').first() is not None
        assert User.query.filter_by(email='analyst@test.com').first() is not None
        assert User.query.filter_by(email='analyst@bank.com').first() is not None


def test_cleanup_removes_all_associated_records(app, baseline_demo_data):
    """Test 11: Cleanup removes all associated transactions, predictions, and alerts via cascade."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_id = user.id
        txn_ids = [t.id for t in user.transactions.all()]
        alert_ids = [a.id for a in user.alerts.all()]

        assert len(txn_ids) > 0
        assert len(alert_ids) > 0

        # Age and cleanup
        user.created_at = datetime.utcnow() - timedelta(hours=4)
        db.session.commit()

        DemoService.cleanup_expired_demo_sessions(max_age_hours=2)

        # Verify full cascade removal
        assert User.query.get(user_id) is None
        assert Transaction.query.filter(Transaction.id.in_(txn_ids)).count() == 0
        assert Prediction.query.filter(Prediction.transaction_id.in_(txn_ids)).count() == 0
        assert FraudAlert.query.filter(FraudAlert.id.in_(alert_ids)).count() == 0


def test_ephemeral_accounts_cannot_modify_password_or_identity(app, baseline_demo_data):
    """Test 12: Ephemeral accounts cannot modify their password or identity via /profile/."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_email = user.email
        user_name = user.name

    client = app.test_client()
    # Log in as ephemeral user
    from flask_login import login_user
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True

    # Attempt to change password
    res = client.post('/profile/', data={
        'name': user_name,
        'current_password': 'any',
        'new_password': 'HackedPassword999!',
        'confirm_new_password': 'HackedPassword999!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert "Password modifications are disabled on public demonstration accounts" in res.get_data(as_text=True)

    # Attempt to change name
    res2 = client.post('/profile/', data={
        'name': 'Defaced Recruiter',
        'current_password': '',
        'new_password': '',
        'confirm_new_password': ''
    }, follow_redirects=True)
    assert res2.status_code == 200
    assert "Profile identity modifications are disabled on public demonstration accounts" in res2.get_data(as_text=True)

    with app.app_context():
        u_check = User.query.get(user.id)
        assert u_check.name == user_name


def test_existing_auth_and_admin_authorization_intact(app, baseline_demo_data):
    """Test 13: Existing authentication and authorization behavior remains intact."""
    with app.app_context():
        e_user = DemoService.create_ephemeral_demo_user()
        e_user_id = e_user.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(e_user_id)
        sess['_fresh'] = True

    # Ephemeral user cannot access /admin/ (HTTP 403 Forbidden)
    assert client.get('/admin/').status_code == 403
    assert client.get('/admin/audit-logs').status_code == 403
    assert client.get('/admin/model-diagnostics').status_code == 403
