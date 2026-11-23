"""
Automated Test Suite for Safe Automatic Cleanup of Expired Recruiter Demo Accounts (Phase B, Task 1.5).

Verifies:
1. Expired ephemeral accounts are deleted correctly.
2. Active (non-expired) ephemeral accounts are preserved.
3. Permanent analyst accounts are strictly preserved.
4. Administrator accounts are strictly preserved.
5. Permanent baseline demo account and records are strictly preserved.
6. Associated records (transactions, predictions, alerts, audit logs) are deleted safely.
7. Historical permanent-user records remain completely intact.
8. Running cleanup twice is safe and idempotent.
9. Cleanup rollback works atomically on failure without partial deletion.
10. Flask CLI cleanup command (`flask cleanup-demo-sessions`) executes correctly with exit code 0.
11. Flask CLI cleanup command respects custom `--max-age-hours` parameter.
12. Flask CLI cleanup command respects `--quiet` flag.
13. Flask CLI cleanup command returns exit code 1 on execution failure.
14. Cleanup execution does not disrupt or log out active recruiter sessions.
15. Cleanup logs record summary counts and UTC timestamps without exposing sensitive data.
16. Standalone scheduled cleanup script (`scripts/cleanup_demo_sessions.py`) executes safely.
"""

import os
import re
from datetime import timedelta
import logging
from flask import g
import pytest

from app.extensions import db
from app.models import User, Transaction, Prediction, FraudAlert, AuditLog, utc_now
from app.services.prediction_service import PredictionService
from app.services.demo_service import DemoService
from scripts.cleanup_demo_sessions import run_cleanup


@pytest.fixture
def baseline_demo_data(app):
    """Seeds approved baseline demo data on the permanent analyst account in the test database."""
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


def test_expired_ephemeral_account_is_deleted(app, baseline_demo_data):
    """Test 1: Expired ephemeral account older than cutoff is deleted by cleanup."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_id = user.id

        # Age account past 2-hour window
        user.created_at = utc_now() - timedelta(hours=3)
        db.session.commit()

        deleted = DemoService.cleanup_expired_demo_sessions(max_age_hours=2)
        assert deleted >= 1

        assert db.session.get(User, user_id) is None


def test_active_ephemeral_account_is_preserved(app, baseline_demo_data):
    """Test 2: Active ephemeral account within retention window is preserved."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_id = user.id

        # Account created 15 minutes ago (well within 2-hour window)
        user.created_at = utc_now() - timedelta(minutes=15)
        db.session.commit()

        deleted = DemoService.cleanup_expired_demo_sessions(max_age_hours=2)
        assert deleted == 0

        preserved_user = db.session.get(User, user_id)
        assert preserved_user is not None
        assert preserved_user.is_ephemeral is True


def test_permanent_analyst_is_preserved(app, baseline_demo_data):
    """Test 3: Permanent analyst account is never deleted, regardless of age."""
    with app.app_context():
        analyst = User.query.filter_by(email='analyst@test.com').first()
        if not analyst:
            analyst = User(name='Alex Analyst', email='analyst@test.com', role='user', is_active_account=True, is_ephemeral=False)
            analyst.set_password('Pass123!')
            db.session.add(analyst)
            db.session.commit()

        analyst_id = analyst.id
        # Artificially age analyst account by 180 days
        analyst.created_at = utc_now() - timedelta(days=180)
        db.session.commit()

        DemoService.cleanup_expired_demo_sessions(max_age_hours=2)

        preserved_analyst = db.session.get(User, analyst_id)
        assert preserved_analyst is not None
        assert preserved_analyst.email == 'analyst@test.com'
        assert preserved_analyst.is_ephemeral is False


def test_administrator_is_preserved(app, baseline_demo_data):
    """Test 4: Administrator account is never deleted, regardless of age."""
    with app.app_context():
        admin = User.query.filter_by(role='admin').first()
        admin_id = admin.id
        admin.created_at = utc_now() - timedelta(days=365)
        db.session.commit()

        DemoService.cleanup_expired_demo_sessions(max_age_hours=2)

        preserved_admin = db.session.get(User, admin_id)
        assert preserved_admin is not None
        assert preserved_admin.role == 'admin'


def test_permanent_baseline_demo_account_is_preserved(app, baseline_demo_data):
    """Test 5: Permanent baseline demo account (analyst@bank.com) and its records are preserved."""
    with app.app_context():
        baseline_user = db.session.get(User, baseline_demo_data.id)
        baseline_txns_before = baseline_user.transactions.count()
        assert baseline_txns_before > 0

        # Artificially age baseline demo analyst
        baseline_user.created_at = utc_now() - timedelta(days=60)
        db.session.commit()

        DemoService.cleanup_expired_demo_sessions(max_age_hours=2)

        baseline_user_after = db.session.get(User, baseline_demo_data.id)
        assert baseline_user_after is not None
        assert baseline_user_after.transactions.count() == baseline_txns_before


def test_associated_records_are_deleted_correctly(app, baseline_demo_data):
    """Test 6: Cloned transactions, predictions, fraud alerts, and audit logs are deleted safely."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_id = user.id

        txn_ids = [t.id for t in user.transactions.all()]
        alert_ids = [a.id for a in user.alerts.all()]
        assert len(txn_ids) > 0

        # Add an audit log record for this ephemeral user
        log = AuditLog(user_id=user_id, action='DEMO_LOGIN_SUCCESS', details='Session started')
        db.session.add(log)
        db.session.commit()
        log_id = log.id

        # Age past cutoff
        user.created_at = utc_now() - timedelta(hours=3)
        db.session.commit()

        deleted = DemoService.cleanup_expired_demo_sessions(max_age_hours=2)
        assert deleted >= 1

        # Check all child records are removed
        assert db.session.get(User, user_id) is None
        assert Transaction.query.filter(Transaction.id.in_(txn_ids)).count() == 0
        assert Prediction.query.filter(Prediction.transaction_id.in_(txn_ids)).count() == 0
        assert FraudAlert.query.filter(FraudAlert.id.in_(alert_ids)).count() == 0
        assert db.session.get(AuditLog, log_id) is None


def test_historical_permanent_user_records_remain_intact(app, baseline_demo_data):
    """Test 7: Historical permanent user records (txns, predictions, alerts, audit logs) remain untouched."""
    with app.app_context():
        analyst = User.query.filter_by(email='analyst@test.com').first()
        log_permanent = AuditLog(user_id=analyst.id, action='USER_LOGIN', details='Permanent login')
        db.session.add(log_permanent)
        db.session.commit()
        log_permanent_id = log_permanent.id

        analyst_txns_before = analyst.transactions.count()
        analyst_alerts_before = analyst.alerts.count()

        # Create and age an ephemeral account
        ephemeral = DemoService.create_ephemeral_demo_user()
        ephemeral.created_at = utc_now() - timedelta(hours=3)
        db.session.commit()

        # Run cleanup
        DemoService.cleanup_expired_demo_sessions(max_age_hours=2)

        # Permanent records must remain intact
        assert db.session.get(AuditLog, log_permanent_id) is not None
        assert analyst.transactions.count() == analyst_txns_before
        assert analyst.alerts.count() == analyst_alerts_before


def test_running_cleanup_twice_is_safe_and_idempotent(app, baseline_demo_data):
    """Test 8: Running cleanup twice in immediate succession is completely safe and idempotent."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user.created_at = utc_now() - timedelta(hours=4)
        db.session.commit()

        # First pass deletes 1 expired user
        count_first = DemoService.cleanup_expired_demo_sessions(max_age_hours=2)
        assert count_first >= 1

        # Second pass finds 0 eligible users and exits cleanly
        count_second = DemoService.cleanup_expired_demo_sessions(max_age_hours=2)
        assert count_second == 0


def test_cleanup_rollback_works_on_failure(app, baseline_demo_data, monkeypatch):
    """Test 9: Cleanup rolls back atomically on database failure without partial state."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_id = user.id
        user.created_at = utc_now() - timedelta(hours=3)
        db.session.commit()

        def mock_commit():
            raise RuntimeError("Simulated database failure during commit")

        monkeypatch.setattr(db.session, 'commit', mock_commit)

        with pytest.raises(RuntimeError, match="Simulated database failure during commit"):
            DemoService.cleanup_expired_demo_sessions(max_age_hours=2)

        # Rollback verified: account was not deleted in partial transaction
        assert db.session.get(User, user_id) is not None


def test_flask_cli_cleanup_command_executes_correctly(app, baseline_demo_data):
    """Test 10: Flask CLI command `flask cleanup-demo-sessions` executes with exit code 0."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_id = user.id
        user.created_at = utc_now() - timedelta(hours=3)
        db.session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(args=['cleanup-demo-sessions'])

    assert result.exit_code == 0
    assert "[DemoCleanup] Successfully purged" in result.output

    with app.app_context():
        assert db.session.get(User, user_id) is None


def test_flask_cli_cleanup_command_custom_max_age_option(app, baseline_demo_data):
    """Test 11: Flask CLI command respects custom `--max-age-hours` parameter."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_id = user.id
        # User is 3.5 hours old
        user.created_at = utc_now() - timedelta(hours=3.5)
        db.session.commit()

    runner = app.test_cli_runner()

    # Pass max-age-hours=5 -> user is NOT expired under 5h threshold
    res_5h = runner.invoke(args=['cleanup-demo-sessions', '--max-age-hours', '5'])
    assert res_5h.exit_code == 0
    assert "Successfully purged 0" in res_5h.output

    with app.app_context():
        assert db.session.get(User, user_id) is not None

    # Pass max-age-hours=2 -> user IS expired under 2h threshold
    res_2h = runner.invoke(args=['cleanup-demo-sessions', '--max-age-hours', '2'])
    assert res_2h.exit_code == 0
    assert "Successfully purged 1" in res_2h.output

    with app.app_context():
        assert db.session.get(User, user_id) is None


def test_flask_cli_cleanup_command_quiet_option(app, baseline_demo_data):
    """Test 12: Flask CLI command `--quiet` suppresses stdout messages."""
    runner = app.test_cli_runner()
    result = runner.invoke(args=['cleanup-demo-sessions', '--quiet'])

    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_flask_cli_cleanup_command_failure_returns_exit_code_1(app, monkeypatch):
    """Test 13: Flask CLI command exits with code 1 when an exception occurs."""
    def mock_failure(max_age_hours=None):
        raise RuntimeError("Database connection timed out during cleanup")

    monkeypatch.setattr(DemoService, 'cleanup_expired_demo_sessions', mock_failure)

    runner = app.test_cli_runner()
    result = runner.invoke(args=['cleanup-demo-sessions'])

    assert result.exit_code == 1
    assert "[DemoCleanup ERROR]" in result.output


def test_cleanup_does_not_affect_active_recruiter_sessions(app, baseline_demo_data):
    """Test 14: Cleanup does not affect active recruiter sessions or interrupt browsing."""
    client = app.test_client()

    # Active recruiter logs in via one-click demo login
    res_login = client.post('/auth/demo-login', follow_redirects=True)
    assert res_login.status_code == 200

    with app.app_context():
        active_user = User.query.filter_by(is_ephemeral=True).order_by(User.id.desc()).first()
        active_id = active_user.id

        # Another recruiter session that expired 3 hours ago
        expired_user = DemoService.create_ephemeral_demo_user()
        expired_id = expired_user.id
        expired_user.created_at = utc_now() - timedelta(hours=3)
        db.session.commit()

    # Clear application-context cached user before cleanup
    g.pop('_login_user', None)

    # Run cleanup
    deleted = DemoService.cleanup_expired_demo_sessions(max_age_hours=2)
    assert deleted >= 1

    with app.app_context():
        # Expired user was purged
        assert db.session.get(User, expired_id) is None
        # Active user remains
        assert db.session.get(User, active_id) is not None

    # Clear context cache and verify active client can continue accessing dashboard
    g.pop('_login_user', None)
    res_dash = client.get('/dashboard', follow_redirects=False)
    assert res_dash.status_code == 200


def test_cleanup_logging_without_sensitive_information(app, baseline_demo_data, caplog):
    """Test 15: Cleanup logging contains summary counts and UTC timestamps, never passwords or tokens."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user.created_at = utc_now() - timedelta(hours=3)
        db.session.commit()

        with caplog.at_level(logging.INFO):
            DemoService.cleanup_expired_demo_sessions(max_age_hours=2)

        log_text = caplog.text
        assert "[DemoCleanup] Successfully purged" in log_text
        assert "retention window: 2h" in log_text

        # Ensure no sensitive tokens, hashes, or passwords leak in logs
        assert "password" not in log_text.lower()
        assert "secret" not in log_text.lower()
        assert "token" not in log_text.lower()
        assert user.email not in log_text


def test_standalone_script_executes_successfully(app, baseline_demo_data):
    """Test 16: Standalone scheduled script `scripts/cleanup_demo_sessions.py` executes safely."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_id = user.id
        user.created_at = utc_now() - timedelta(hours=3)
        db.session.commit()

    exit_code = run_cleanup(app=app, max_age_hours=2, quiet=True)
    assert exit_code == 0

    with app.app_context():
        assert db.session.get(User, user_id) is None
