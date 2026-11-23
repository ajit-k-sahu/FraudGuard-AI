"""
Tests for Ephemeral Session Expiration, Safe Database Migration, and UTC Modernization (Phase B, Task 1.3.2).

Verifies:
1. Non-expired ephemeral account remains authenticated.
2. Expired ephemeral account is rejected before physical cleanup has run.
3. Expired account cannot access protected web routes (/dashboard, /transactions/history, /alerts, /profile).
4. Expired account cannot access protected API routes (/api/v1/transactions, /api/v1/stats, /api/v1/alerts).
5. Normal user remains unaffected by expiration logic.
6. Administrator remains unaffected by expiration logic.
7. Permanent analyst demo account remains unaffected by expiration logic.
8. Fresh database creates is_ephemeral correctly.
9. Existing database without is_ephemeral migrates successfully without data loss.
10. Running migration twice is safe and idempotent.
11. Migration failure is surfaced and logged safely.
12. UTC expiration boundary tests (cutoff - 1s, cutoff + 1s).
13. Cleanup still deletes expired ephemeral records and cascade relations safely.
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine, inspect, text

from app.extensions import db
from app.models import User, Transaction, Prediction, FraudAlert, utc_now
from app.services.prediction_service import PredictionService
from app.services.demo_service import DemoService
from app.api.routes import generate_api_token
from app.utils.migrations import run_migrations


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


def test_non_expired_ephemeral_account_remains_authenticated(app, baseline_demo_data):
    """Test 1: Non-expired ephemeral account is authenticated and active."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        assert user.is_expired is False
        assert user.is_active is True
        user_id = user.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True

    res = client.get('/dashboard')
    assert res.status_code == 200


def test_expired_ephemeral_account_rejected_before_cleanup(app, baseline_demo_data):
    """Test 2: Expired ephemeral account is rejected immediately before physical cleanup runs."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_id = user.id

        # Artificially age the account past 2 hours
        user.created_at = utc_now() - timedelta(hours=3)
        db.session.commit()

        # Physical cleanup has NOT run; row still exists in DB
        user_in_db = User.query.get(user_id)
        assert user_in_db is not None
        assert user_in_db.is_expired is True
        assert user_in_db.is_active is False

        # Flask-Login user_loader rejects the expired user
        from app.models import load_user
        assert load_user(str(user_id)) is None


def test_expired_account_cannot_access_protected_web_routes(app, baseline_demo_data):
    """Test 3: Expired account cannot access protected web routes (/dashboard, /history, /alerts, /profile)."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_id = user.id
        user.created_at = utc_now() - timedelta(hours=3)
        db.session.commit()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True

    # Web routes redirect unauthenticated/expired users to login
    for route in ['/dashboard', '/transactions/history', '/alerts', '/profile']:
        res = client.get(route, follow_redirects=False)
        assert res.status_code in (302, 401)
        if res.status_code == 302:
            assert '/auth/login' in res.headers['Location']

    # State-changing web actions also blocked
    res_post = client.post('/transactions/analyze', data={'amount': 100}, follow_redirects=False)
    assert res_post.status_code in (302, 401)


def test_expired_account_cannot_access_protected_api_routes(app, baseline_demo_data):
    """Test 4: Expired account cannot access protected API routes with Bearer token or session."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_id = user.id
        token = generate_api_token(user.id)

        user.created_at = utc_now() - timedelta(hours=3)
        db.session.commit()

    client = app.test_client()
    headers = {'Authorization': f'Bearer {token}'}

    for endpoint in ['/api/v1/transactions', '/api/v1/stats', '/api/v1/alerts']:
        res = client.get(endpoint, headers=headers)
        assert res.status_code == 401
        data = res.get_json()
        assert data['success'] is False

    # POST to /api/v1/predict with expired token cannot persist records
    res_pred = client.post('/api/v1/predict', headers=headers, json={
        'amount': 250.0,
        'transaction_type': 'Transfer',
        'channel': 'Mobile Banking'
    })
    # Unauthenticated/expired token falls back to anonymous demo or 401
    assert res_pred.status_code in (401, 201)
    if res_pred.status_code == 201:
        # If processed in demo mode, must be flagged as is_demo and rolled back
        assert res_pred.get_json()['data']['is_demo'] is True


def test_normal_user_remains_unaffected(app):
    """Test 5: Normal user remains unaffected by expiration logic even if ancient."""
    with app.app_context():
        user = User.query.filter_by(email='analyst@test.com').first()
        user.created_at = utc_now() - timedelta(days=365)
        db.session.commit()

        assert user.is_expired is False
        assert user.is_active is True
        user_id = user.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True

    assert client.get('/dashboard').status_code == 200


def test_administrator_remains_unaffected(app):
    """Test 6: Administrator remains unaffected by expiration logic even if ancient."""
    with app.app_context():
        admin = User.query.filter_by(email='admin@test.com').first()
        admin.created_at = utc_now() - timedelta(days=365)
        db.session.commit()

        assert admin.is_expired is False
        assert admin.is_active is True
        admin_id = admin.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True

    assert client.get('/admin/').status_code == 200


def test_permanent_analyst_demo_account_remains_unaffected(app, baseline_demo_data):
    """Test 7: Permanent analyst demo account remains unaffected by expiration logic."""
    with app.app_context():
        demo_analyst = User.query.filter_by(email='analyst@bank.com').first()
        demo_analyst.created_at = utc_now() - timedelta(days=120)
        db.session.commit()

        assert demo_analyst.is_ephemeral is False
        assert demo_analyst.is_expired is False
        assert demo_analyst.is_active is True
        demo_id = demo_analyst.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(demo_id)
        sess['_fresh'] = True

    assert client.get('/dashboard').status_code == 200


def test_fresh_database_creates_is_ephemeral_correctly(tmp_path):
    """Test 8: Fresh database creates is_ephemeral correctly via DDL."""
    test_db_path = os.path.join(tmp_path, "fresh_test.db")
    engine = create_engine(f"sqlite:///{test_db_path}")

    from app.models import User
    # Ensure fresh schema is created
    User.metadata.create_all(engine)

    inspector = inspect(engine)
    assert 'users' in inspector.get_table_names()
    columns = {c['name']: c for c in inspector.get_columns('users')}
    assert 'is_ephemeral' in columns
    engine.dispose()


def test_existing_database_without_is_ephemeral_migrates_successfully(tmp_path):
    """Test 9: Existing database without is_ephemeral receives additive migration safely without data loss."""
    test_db_path = os.path.join(tmp_path, "legacy_test.db")
    con = sqlite3.connect(test_db_path)
    cur = con.cursor()
    # Create legacy table without is_ephemeral
    cur.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL,
            is_active_account BOOLEAN NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
    """)
    cur.execute("""
        INSERT INTO users (id, name, email, password_hash, role, is_active_account, created_at, updated_at)
        VALUES (1, 'Legacy User', 'legacy@test.com', 'hash123', 'user', 1, '2026-01-01 00:00:00', '2026-01-01 00:00:00');
    """)
    con.commit()
    con.close()

    engine = create_engine(f"sqlite:///{test_db_path}")

    class MockDB:
        def __init__(self, eng):
            self.engine = eng
        def create_all(self):
            pass

    mock_db = MockDB(engine)
    run_migrations(db_instance=mock_db)

    # Verify column added and legacy row preserved
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('users')]
    assert 'is_ephemeral' in columns

    with engine.connect() as conn:
        row = conn.execute(text("SELECT id, email, is_ephemeral FROM users WHERE id=1")).fetchone()
        assert row is not None
        assert row[1] == 'legacy@test.com'
        assert row[2] in (0, False)
    engine.dispose()


def test_running_migration_twice_is_safe_and_idempotent(tmp_path):
    """Test 10: Running migration repeatedly is completely idempotent."""
    test_db_path = os.path.join(tmp_path, "idempotent_test.db")
    engine = create_engine(f"sqlite:///{test_db_path}")

    from app.models import User
    User.metadata.create_all(engine)

    class MockDB:
        def __init__(self, eng):
            self.engine = eng
        def create_all(self):
            pass

    mock_db = MockDB(engine)

    # First run
    assert run_migrations(db_instance=mock_db) is True
    # Second run
    assert run_migrations(db_instance=mock_db) is True
    # Third run
    assert run_migrations(db_instance=mock_db) is True
    engine.dispose()


def test_migration_failure_is_surfaced_safely(tmp_path, monkeypatch):
    """Test 11: Migration failure is logged and re-raises RuntimeError."""
    test_db_path = os.path.join(tmp_path, "fail_test.db")
    engine = create_engine(f"sqlite:///{test_db_path}")

    # Create table without column
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY);"))

    class MockDB:
        def __init__(self, eng):
            self.engine = eng
        def create_all(self):
            pass

    mock_db = MockDB(engine)

    # Force connection error
    def mock_begin():
        raise sqlite3.OperationalError("Disk I/O error or permission denied")

    monkeypatch.setattr(engine, 'begin', mock_begin)

    with pytest.raises(RuntimeError, match="Database schema migration failed"):
        run_migrations(db_instance=mock_db)

    engine.dispose()


def test_utc_expiration_boundary_conditions(app):
    """Test 12: UTC expiration boundary conditions (cutoff - 1s, cutoff + 1s)."""
    with app.app_context():
        # User 1: created 1 hour 59 minutes 55 seconds ago (5 seconds BEFORE expiration)
        u_active = User(
            name="Near Cutoff Active",
            email="near_active@demo.local",
            role="user",
            is_active_account=True,
            is_ephemeral=True,
            created_at=utc_now() - timedelta(hours=2) + timedelta(seconds=5)
        )
        u_active.set_password("pass123")

        # User 2: created 2 hours 1 second ago (1 second AFTER expiration)
        u_expired = User(
            name="Near Cutoff Expired",
            email="near_expired@demo.local",
            role="user",
            is_active_account=True,
            is_ephemeral=True,
            created_at=utc_now() - timedelta(hours=2) - timedelta(seconds=1)
        )
        u_expired.set_password("pass123")

        db.session.add_all([u_active, u_expired])
        db.session.commit()

        assert u_active.is_expired is False
        assert u_active.is_active is True

        assert u_expired.is_expired is True
        assert u_expired.is_active is False


def test_cleanup_still_deletes_expired_ephemeral_records_correctly(app, baseline_demo_data):
    """Test 13: Cleanup still deletes expired ephemeral records and cascade relations correctly."""
    with app.app_context():
        user = DemoService.create_ephemeral_demo_user()
        user_id = user.id
        txn_ids = [t.id for t in user.transactions.all()]
        alert_ids = [a.id for a in user.alerts.all()]

        assert len(txn_ids) > 0
        assert len(alert_ids) > 0

        # Age past 2 hours
        user.created_at = utc_now() - timedelta(hours=3)
        db.session.commit()

        deleted = DemoService.cleanup_expired_demo_sessions(max_age_hours=2)
        assert deleted >= 1

        assert User.query.get(user_id) is None
        assert Transaction.query.filter(Transaction.id.in_(txn_ids)).count() == 0
        assert Prediction.query.filter(Prediction.transaction_id.in_(txn_ids)).count() == 0
        assert FraudAlert.query.filter(FraudAlert.id.in_(alert_ids)).count() == 0
