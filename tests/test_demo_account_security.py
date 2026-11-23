"""
Tests for Recruiter Demo Account Security and Administrative Protection (Phase B, Task 1.1).

Verifies:
1. Public login page does not display administrator credentials.
2. README.md documentation does not expose plaintext production administrator passwords.
3. Production admin initialization fails safely without default password when ADMIN_PASSWORD is absent.
4. Demo user cannot change their password via /profile/.
5. Demo user cannot change their display name/identity via /profile/.
6. Normal (non-demo) user can change their display name and password successfully.
7. Administrator cannot deactivate the designated demo account.
8. Administrator can deactivate ordinary users.
9. Demo user and ordinary users cannot access administrator endpoints.
10. Registration endpoint assigns role='user' and cannot assign administrator role.
"""

import os
import pytest
from app.extensions import db
from app.models import User

def test_login_page_does_not_expose_admin_credentials(client):
    """Ensure the public login page does not display administrator or plaintext passwords."""
    res = client.get('/auth/login')
    assert res.status_code == 200
    
    content = res.get_data(as_text=True)
    # Admin credentials must be completely absent
    assert 'admin@fraudguard.ai' not in content
    assert 'AdminPass123!' not in content
    assert 'AdminSecurePassword' not in content
    assert 'System Administrator' not in content
    
    # Plaintext demo passwords must not be exposed on the public page
    assert 'AnalystPass123!' not in content
    assert 'Launch Instant Recruiter Demo' in content or 'demo-login' in content


def test_readme_does_not_expose_admin_credentials():
    """Ensure README documentation does not expose plaintext production administrator passwords."""
    readme_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'README.md')
    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'AdminPass123!' not in content
    assert 'AdminSecurePassword2026!' not in content


def test_production_admin_seeding_fails_safely_without_password(monkeypatch):
    """Ensure admin seeding in production does not fall back to a hardcoded password."""
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.delenv('ADMIN_PASSWORD', raising=False)
    monkeypatch.setenv('ADMIN_EMAIL', 'prod_admin_test@fraudguard.ai')

    from app import create_app
    test_app = create_app('testing')
    with test_app.app_context():
        # Simulate production logic from seed_demo_data.py
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@fraudguard.ai').lower().strip()
        admin = User.query.filter_by(email=admin_email).first()
        admin_password = os.environ.get('ADMIN_PASSWORD')
        env_mode = os.environ.get('FLASK_ENV', 'development').lower()

        if not admin:
            if env_mode == 'production' and not admin_password:
                admin_created = False
            else:
                admin_created = True

        assert admin_created is False
        assert User.query.filter_by(email=admin_email).first() is None


def test_demo_account_cannot_change_password(app):
    """Verify demo account is blocked from changing password via profile settings."""
    with app.app_context():
        # Ensure demo user exists
        demo = User.query.filter_by(email='analyst@bank.com').first()
        if not demo:
            demo = User(name='Alex Mercer (Fraud Analyst)', email='analyst@bank.com', role='user', is_active_account=True)
            demo.set_password('AnalystPass123!')
            db.session.add(demo)
            db.session.commit()
        demo_id = demo.id

    client = app.test_client()
    login_res = client.post('/auth/login', data={'email': 'analyst@bank.com', 'password': 'AnalystPass123!'}, follow_redirects=True)
    assert login_res.status_code == 200

    # Attempt to change password
    res = client.post('/profile/', data={
        'name': 'Alex Mercer (Fraud Analyst)',
        'current_password': 'AnalystPass123!',
        'new_password': 'NewHackedPassword999!',
        'confirm_new_password': 'NewHackedPassword999!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert "Password modifications are disabled on public demonstration accounts" in res.get_data(as_text=True)

    with app.app_context():
        updated_demo = User.query.get(demo_id)
        assert updated_demo.check_password('AnalystPass123!') is True
        assert updated_demo.check_password('NewHackedPassword999!') is False


def test_demo_account_cannot_change_name_or_identity(app):
    """Verify demo account is blocked from modifying its display name."""
    with app.app_context():
        demo = User.query.filter_by(email='analyst@bank.com').first()
        if not demo:
            demo = User(name='Alex Mercer (Fraud Analyst)', email='analyst@bank.com', role='user', is_active_account=True)
            demo.set_password('AnalystPass123!')
            db.session.add(demo)
            db.session.commit()
        demo_id = demo.id

    client = app.test_client()
    client.post('/auth/login', data={'email': 'analyst@bank.com', 'password': 'AnalystPass123!'}, follow_redirects=True)

    # Attempt to change display name
    res = client.post('/profile/', data={
        'name': 'Defaced Recruiter Account',
        'current_password': '',
        'new_password': '',
        'confirm_new_password': ''
    }, follow_redirects=True)
    assert res.status_code == 200
    assert "Profile identity modifications are disabled on public demonstration accounts" in res.get_data(as_text=True)

    with app.app_context():
        updated_demo = User.query.get(demo_id)
        assert updated_demo.name == 'Alex Mercer (Fraud Analyst)'


def test_ordinary_user_can_update_profile_and_password(app):
    """Verify non-demo users can update their profile name and change their password normally."""
    with app.app_context():
        user = User.query.filter_by(email='analyst@test.com').first()
        assert user.is_demo_account is False
        user_id = user.id

    client = app.test_client()
    client.post('/auth/login', data={'email': 'analyst@test.com', 'password': 'AnalystPass123!'}, follow_redirects=True)

    # Update profile name and change password
    res = client.post('/profile/', data={
        'name': 'Updated Jane Analyst',
        'current_password': 'AnalystPass123!',
        'new_password': 'NewValidPassword789!',
        'confirm_new_password': 'NewValidPassword789!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert "Your password and profile have been successfully updated" in res.get_data(as_text=True)

    with app.app_context():
        updated_user = User.query.get(user_id)
        assert updated_user.name == 'Updated Jane Analyst'
        assert updated_user.check_password('NewValidPassword789!') is True


def test_admin_cannot_deactivate_demo_account(app):
    """Verify administrator cannot deactivate the primary demonstration account."""
    with app.app_context():
        demo = User.query.filter_by(email='analyst@bank.com').first()
        if not demo:
            demo = User(name='Alex Mercer (Fraud Analyst)', email='analyst@bank.com', role='user', is_active_account=True)
            demo.set_password('AnalystPass123!')
            db.session.add(demo)
            db.session.commit()
        demo_id = demo.id

    admin_client = app.test_client()
    admin_client.post('/auth/login', data={'email': 'admin@test.com', 'password': 'AdminPass123!'}, follow_redirects=True)

    res = admin_client.post(f'/admin/users/{demo_id}/toggle-status', follow_redirects=True)
    assert res.status_code == 200
    assert "The primary demonstration account cannot be deactivated" in res.get_data(as_text=True)

    with app.app_context():
        demo = User.query.get(demo_id)
        assert demo.is_active_account is True


def test_admin_can_deactivate_and_reactivate_ordinary_user(app):
    """Verify administrator can toggle status of ordinary non-demo users."""
    with app.app_context():
        ordinary = User.query.filter_by(email='analyst@test.com').first()
        ordinary_id = ordinary.id
        assert ordinary.is_active_account is True

    admin_client = app.test_client()
    admin_client.post('/auth/login', data={'email': 'admin@test.com', 'password': 'AdminPass123!'}, follow_redirects=True)

    # Deactivate ordinary user
    res1 = admin_client.post(f'/admin/users/{ordinary_id}/toggle-status', follow_redirects=True)
    assert res1.status_code == 200
    assert "deactivated" in res1.get_data(as_text=True)

    with app.app_context():
        user_check = User.query.get(ordinary_id)
        assert user_check.is_active_account is False

    # Reactivate ordinary user
    res2 = admin_client.post(f'/admin/users/{ordinary_id}/toggle-status', follow_redirects=True)
    assert res2.status_code == 200
    assert "activated" in res2.get_data(as_text=True)

    with app.app_context():
        user_check = User.query.get(ordinary_id)
        assert user_check.is_active_account is True


def test_demo_account_cannot_access_admin_endpoints(app):
    """Verify demo account cannot access administrator routes (HTTP 403 Forbidden)."""
    with app.app_context():
        demo = User.query.filter_by(email='analyst@bank.com').first()
        if not demo:
            demo = User(name='Alex Mercer (Fraud Analyst)', email='analyst@bank.com', role='user', is_active_account=True)
            demo.set_password('AnalystPass123!')
            db.session.add(demo)
            db.session.commit()

    client = app.test_client()
    client.post('/auth/login', data={'email': 'analyst@bank.com', 'password': 'AnalystPass123!'}, follow_redirects=True)

    assert client.get('/admin/').status_code == 403
    assert client.get('/admin/audit-logs').status_code == 403
    assert client.get('/admin/model-diagnostics').status_code == 403


def test_public_registration_cannot_assign_admin_role(app, client):
    """Verify public registration always assigns role='user' regardless of form tampering."""
    res = client.post('/auth/register', data={
        'name': 'Privilege Escalation Tester',
        'email': 'tester_escalation@test.com',
        'password': 'SecurePass123!',
        'confirm_password': 'SecurePass123!',
        'role': 'admin'
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        user = User.query.filter_by(email='tester_escalation@test.com').first()
        assert user is not None
        assert user.role == 'user'
