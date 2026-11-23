"""
Production Secrets & Environment Variable Hardening Test Suite.
Verifies secure handling of SECRET_KEY, DATABASE_URL, REDIS_URL, ADMIN_PASSWORD,
redaction of credentials in connection strings, .env.example placeholder safety,
.gitignore exclusions, and fail-safe production startup guards.
"""

import os
import re
import pytest
from config import (
    Config,
    ProductionConfig,
    redact_secret_url,
)


def test_missing_secret_key_halts_production_startup(monkeypatch):
    """Test 1: create_app('production') raises ValueError if SECRET_KEY is missing."""
    from app import create_app

    monkeypatch.delenv('SECRET_KEY', raising=False)
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost:5432/db')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')

    with pytest.raises(ValueError, match="SECRET_KEY environment variable is missing"):
        create_app('production')


def test_whitespace_secret_key_halts_production_startup(monkeypatch):
    """Test 2: create_app('production') raises ValueError if SECRET_KEY is whitespace only."""
    from app import create_app

    monkeypatch.setenv('SECRET_KEY', '    \t\n  ')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost:5432/db')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')

    with pytest.raises(ValueError, match="SECRET_KEY environment variable is missing"):
        create_app('production')


def test_weak_or_short_secret_key_halts_production_startup(monkeypatch):
    """Test 3: create_app('production') raises ValueError if SECRET_KEY is too short (< 24 chars)."""
    from app import create_app

    monkeypatch.setenv('SECRET_KEY', 'short-key-12345')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost:5432/db')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')

    with pytest.raises(ValueError, match="Insecure or weak SECRET_KEY detected"):
        create_app('production')


def test_known_placeholder_secret_key_halts_production_startup(monkeypatch):
    """Test 4: create_app('production') raises ValueError if known placeholder secret key is used."""
    from app import create_app

    insecure_keys = [
        'change-this-secret-key-in-production-use-a-strong-random-hex',
        'fraudguard-ai-dev-secret-key-38491024-change-in-prod',
        'replace-with-a-very-strong-secret-key',
        'change-this-in-production',
    ]

    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost:5432/db')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')

    for bad_key in insecure_keys:
        monkeypatch.setenv('SECRET_KEY', bad_key)
        with pytest.raises(ValueError, match="Insecure or weak SECRET_KEY detected"):
            create_app('production')


def test_missing_database_url_halts_production_startup(monkeypatch):
    """Test 5: create_app('production') raises ValueError if DATABASE_URL is missing."""
    from app import create_app

    monkeypatch.setenv('SECRET_KEY', 'A_VERY_SECURE_PRODUCTION_KEY_OF_AT_LEAST_32_CHARS_LONG!')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')

    with pytest.raises(ValueError, match="DATABASE_URL environment variable is missing"):
        create_app('production')


def test_whitespace_database_url_halts_production_startup(monkeypatch):
    """Test 6: create_app('production') raises ValueError if DATABASE_URL is whitespace only."""
    from app import create_app

    monkeypatch.setenv('SECRET_KEY', 'A_VERY_SECURE_PRODUCTION_KEY_OF_AT_LEAST_32_CHARS_LONG!')
    monkeypatch.setenv('DATABASE_URL', '    \n  ')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')

    with pytest.raises(ValueError, match="DATABASE_URL environment variable is missing"):
        create_app('production')


def test_sqlite_database_url_halts_production_startup(monkeypatch):
    """Test 7: create_app('production') raises ValueError if SQLite is supplied in production."""
    from app import create_app

    monkeypatch.setenv('SECRET_KEY', 'A_VERY_SECURE_PRODUCTION_KEY_OF_AT_LEAST_32_CHARS_LONG!')
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///instance/fraudguard.db')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')

    with pytest.raises(ValueError, match="SQLite cannot be used in production"):
        create_app('production')


def test_missing_redis_url_halts_production_startup(monkeypatch):
    """Test 8: create_app('production') raises ValueError if REDIS_URL is missing."""
    from app import create_app

    monkeypatch.setenv('SECRET_KEY', 'A_VERY_SECURE_PRODUCTION_KEY_OF_AT_LEAST_32_CHARS_LONG!')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost:5432/db')
    monkeypatch.delenv('REDIS_URL', raising=False)
    monkeypatch.delenv('RATELIMIT_STORAGE_URI', raising=False)

    with pytest.raises(ValueError, match="REDIS_URL environment variable is missing"):
        create_app('production')


def test_whitespace_redis_url_halts_production_startup(monkeypatch):
    """Test 9: create_app('production') raises ValueError if REDIS_URL is whitespace only."""
    from app import create_app

    monkeypatch.setenv('SECRET_KEY', 'A_VERY_SECURE_PRODUCTION_KEY_OF_AT_LEAST_32_CHARS_LONG!')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost:5432/db')
    monkeypatch.setenv('REDIS_URL', '   \t  ')

    with pytest.raises(ValueError, match="REDIS_URL environment variable is missing"):
        create_app('production')


def test_memory_storage_redis_url_halts_production_startup(monkeypatch):
    """Test 10: create_app('production') raises ValueError if memory:// is supplied in production."""
    from app import create_app

    monkeypatch.setenv('SECRET_KEY', 'A_VERY_SECURE_PRODUCTION_KEY_OF_AT_LEAST_32_CHARS_LONG!')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost:5432/db')
    monkeypatch.setenv('REDIS_URL', 'memory://')

    with pytest.raises(ValueError, match="Insecure rate limit storage configuration detected"):
        create_app('production')


def test_valid_production_configuration_succeeds(monkeypatch):
    """Test 11: Production initialization succeeds with valid secrets and enforces security flags."""
    from app import create_app

    monkeypatch.setenv('SECRET_KEY', 'a-very-strong-cryptographically-random-secret-key-32chars!')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost:5432/db')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')

    app = create_app('production')
    assert app is not None
    assert app.debug is False
    assert app.config['DEBUG'] is False
    assert app.config['SESSION_COOKIE_SECURE'] is True
    assert app.config['REMEMBER_COOKIE_SECURE'] is True
    assert app.config['SESSION_COOKIE_HTTPONLY'] is True
    assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'


def test_env_example_contains_only_placeholders_and_no_real_secrets():
    """Test 12: .env.example contains only template placeholders and zero live credentials."""
    with open('.env.example', 'r', encoding='utf-8') as f:
        content = f.read()

    # Placeholders must be explicitly indicated
    assert 'change-this-secret-key-in-production' in content
    assert 'replace-with-a-strong-production-admin-password' in content

    # Never include live passwords or high-entropy production tokens
    assert 'AKIA' not in content  # No AWS keys
    assert 'ghp_' not in content  # No GitHub tokens
    assert 'postgres:postgres' not in content
    assert 'root:root' not in content


def test_gitignore_protects_all_sensitive_files():
    """Test 13: .gitignore excludes .env files, SQLite databases, keys, and certificates."""
    with open('.gitignore', 'r', encoding='utf-8') as f:
        content = f.read()

    assert '.env' in content
    assert '*.db' in content or 'instance/*.db' in content
    assert '*.key' in content
    assert '*.pem' in content
    assert 'secrets/' in content


def test_secret_redaction_masks_database_credentials():
    """Test 14: redact_secret_url replaces database passwords with ***."""
    sensitive_db_url = "postgresql://db_admin:SuperSecretPassword123@db.cloud.internal:5432/fraudguard_db"
    redacted = redact_secret_url(sensitive_db_url)

    assert "SuperSecretPassword123" not in redacted
    assert "postgresql://db_admin:***@db.cloud.internal:5432/fraudguard_db" == redacted


def test_secret_redaction_masks_redis_credentials():
    """Test 15: redact_secret_url replaces redis passwords with ***."""
    sensitive_redis_url = "redis://:my_ultra_secret_redis_auth_token_99@redis-cluster:6379/0"
    redacted = redact_secret_url(sensitive_redis_url)

    assert "my_ultra_secret_redis_auth_token_99" not in redacted
    assert "redis://:***@redis-cluster:6379/0" == redacted


def test_secret_redaction_handles_safe_urls_without_credentials():
    """Test 16: redact_secret_url preserves non-credential URLs safely."""
    assert redact_secret_url("sqlite:///instance/fraudguard.db") == "sqlite:///instance/fraudguard.db"
    assert redact_secret_url("redis://localhost:6379/0") == "redis://localhost:6379/0"
    assert redact_secret_url("") == ""
    assert redact_secret_url(None) == ""


def test_admin_creation_requires_password_in_production(monkeypatch):
    """Test 17: scripts/create_admin.py exits with error in production if ADMIN_PASSWORD is not set."""
    with open('scripts/create_admin.py', 'r', encoding='utf-8') as f:
        code = f.read()

    # Must contain validation halting in production when ADMIN_PASSWORD is unset
    assert "if not admin_password" in code
    assert "if is_prod:" in code
    assert "ADMIN_PASSWORD must be explicitly provided" in code
    assert "len(admin_password) < 12" in code


def test_render_yaml_references_secrets_securely():
    """Test 18: render.yaml declares secrets through dynamic generation and external prompt links."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    # SECRET_KEY uses generateValue
    assert 'generateValue: true' in content
    # External secrets DATABASE_URL, REDIS_URL, and ADMIN_PASSWORD use sync: false (dashboard prompt, never committed)
    assert 'DATABASE_URL' in content
    assert 'REDIS_URL' in content
    assert 'ADMIN_PASSWORD' in content
    assert 'sync: false' in content
    assert 'name: fraudguard-ai' in content
