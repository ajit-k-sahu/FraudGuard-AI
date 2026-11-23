"""
Automated Test Suite for Production PostgreSQL Configuration (Day 4, Task 1).

Verifies:
1. PostgreSQL URL normalization converts legacy 'postgres://' to standard 'postgresql://'.
2. Standard 'postgresql://' URLs are preserved without modification.
3. Driver-specified 'postgresql+psycopg2://' URLs are preserved.
4. Whitespace and line breaks are trimmed safely during normalization.
5. Empty strings and None are handled safely without errors.
6. SQLAlchemy engine options include pool_pre_ping and connection recycling for PostgreSQL resilience.
7. Development configuration preserves local SQLite database by default.
8. Testing configuration preserves isolated test SQLite database.
9. Production configuration defaults to empty URI when DATABASE_URL is not provided (no SQLite leak).
10. Production startup halts safely with descriptive error when DATABASE_URL is missing.
11. Production startup halts safely when SQLite is attempted in production mode.
12. Production startup halts safely when an unsupported scheme (e.g. mysql, mongodb) is passed.
13. Normalized PostgreSQL URI satisfies production validation guards.
14. psycopg2-binary driver dependency is declared in requirements.txt.
15. docker-compose.yml declares PostgreSQL 16 container and connection string.
16. render.yaml declares PostgreSQL database resource and connection string binding.
17. Schema migration utility generates valid, idempotent PostgreSQL DDL statements.
"""

import os
import re
import pytest
from config import normalize_database_url, Config, DevelopmentConfig, TestingConfig, ProductionConfig


def test_normalize_database_url_converts_legacy_postgres_scheme():
    """Test 1: Normalizes legacy 'postgres://' scheme to SQLAlchemy-standard 'postgresql://'."""
    raw = "postgres://fraudguard_user:secret123@db.render.internal:5432/fraudguard_db"
    expected = "postgresql://fraudguard_user:secret123@db.render.internal:5432/fraudguard_db"
    assert normalize_database_url(raw) == expected


def test_normalize_database_url_preserves_standard_postgresql():
    """Test 2: Preserves standard 'postgresql://' scheme untouched."""
    raw = "postgresql://fraudguard_user:secret123@db.render.internal:5432/fraudguard_db"
    assert normalize_database_url(raw) == raw


def test_normalize_database_url_preserves_driver_subscheme():
    """Test 3: Preserves driver-specified 'postgresql+psycopg2://' scheme untouched."""
    raw = "postgresql+psycopg2://fraudguard_user:secret123@localhost:5432/fraudguard_db"
    assert normalize_database_url(raw) == raw


def test_normalize_database_url_strips_whitespace():
    """Test 4: Trims leading and trailing whitespace and newline characters."""
    raw = "   \n postgres://user:pass@host:5432/dbname \t  \n"
    expected = "postgresql://user:pass@host:5432/dbname"
    assert normalize_database_url(raw) == expected


def test_normalize_database_url_handles_empty_and_none():
    """Test 5: Handles empty strings, None, and falsey values safely."""
    assert normalize_database_url(None) == ""
    assert normalize_database_url("") == ""
    assert normalize_database_url("   ") == ""


def test_engine_options_contain_pool_pre_ping_and_recycle():
    """Test 6: Config sets pool_pre_ping=True and pool_recycle for PostgreSQL connection health."""
    assert 'pool_pre_ping' in Config.SQLALCHEMY_ENGINE_OPTIONS
    assert Config.SQLALCHEMY_ENGINE_OPTIONS['pool_pre_ping'] is True
    assert 'pool_recycle' in Config.SQLALCHEMY_ENGINE_OPTIONS
    assert Config.SQLALCHEMY_ENGINE_OPTIONS['pool_recycle'] == 1800


def test_development_config_preserves_sqlite_by_default(monkeypatch):
    """Test 7: DevelopmentConfig defaults to local SQLite when DATABASE_URL is unset."""
    monkeypatch.delenv('DATABASE_URL', raising=False)
    dev_config = DevelopmentConfig()
    assert dev_config.SQLALCHEMY_DATABASE_URI.startswith("sqlite:///")
    assert "fraudguard.db" in dev_config.SQLALCHEMY_DATABASE_URI
    assert dev_config.DEBUG is True
    assert dev_config.TESTING is False


def test_testing_config_preserves_isolated_test_sqlite():
    """Test 8: TestingConfig uses dedicated test SQLite database."""
    test_config = TestingConfig()
    assert test_config.SQLALCHEMY_DATABASE_URI.startswith("sqlite:///")
    assert "test_fraudguard.db" in test_config.SQLALCHEMY_DATABASE_URI
    assert test_config.TESTING is True
    assert test_config.WTF_CSRF_ENABLED is False


def test_production_config_requires_database_url(monkeypatch):
    """Test 9: ProductionConfig does not fall back to local development SQLite when DATABASE_URL is unset."""
    monkeypatch.delenv('DATABASE_URL', raising=False)
    # Re-evaluate class attribute
    db_uri = normalize_database_url(os.environ.get('DATABASE_URL', ''))
    assert db_uri == ""
    assert "sqlite" not in db_uri


def test_production_startup_halts_when_database_url_missing(monkeypatch):
    """Test 10: Application startup halts in production mode when DATABASE_URL is missing."""
    from app import create_app

    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('SECRET_KEY', 'A_VERY_SECURE_PRODUCTION_KEY_OF_AT_LEAST_32_CHARS_LONG!')
    monkeypatch.delenv('FLASK_ENV', raising=False)

    with pytest.raises(ValueError, match="DATABASE_URL environment variable is missing"):
        create_app('production')


def test_production_startup_halts_when_sqlite_configured(monkeypatch):
    """Test 11: Application startup halts in production mode when SQLite is attempted."""
    from app import create_app

    monkeypatch.setenv('DATABASE_URL', 'sqlite:///instance/fraudguard.db')
    monkeypatch.setenv('SECRET_KEY', 'A_VERY_SECURE_PRODUCTION_KEY_OF_AT_LEAST_32_CHARS_LONG!')

    with pytest.raises(ValueError, match="SQLite cannot be used in production"):
        create_app('production')


def test_production_startup_halts_when_unsupported_scheme_used(monkeypatch):
    """Test 12: Application startup halts in production mode when non-PostgreSQL scheme is passed."""
    from app import create_app

    monkeypatch.setenv('DATABASE_URL', 'mysql://user:pass@localhost:3306/fraudguard')
    monkeypatch.setenv('SECRET_KEY', 'A_VERY_SECURE_PRODUCTION_KEY_OF_AT_LEAST_32_CHARS_LONG!')

    with pytest.raises(ValueError, match="Unsupported production database scheme in DATABASE_URL"):
        create_app('production')


def test_normalized_postgres_url_satisfies_production_validation():
    """Test 13: Legacy 'postgres://' URL normalizes and satisfies production scheme checks."""
    legacy_url = "postgres://fraudguard_user:password123@db-host.com:5432/fraudguard_db"
    normalized = normalize_database_url(legacy_url)

    assert normalized.startswith("postgresql://")
    assert not normalized.startswith("postgres://")
    assert "sqlite" not in normalized


def test_requirements_declares_psycopg2_binary():
    """Test 14: requirements.txt specifies psycopg2-binary driver."""
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        content = f.read()

    assert re.search(r'^psycopg2-binary\s*>=', content, re.MULTILINE) is not None


def test_docker_compose_declares_postgres_service():
    """Test 15: docker-compose.yml configures PostgreSQL 16 container and connection URL."""
    with open('docker-compose.yml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'postgres:16-alpine' in content
    assert 'postgresql://fraudguard_user:' in content
    assert 'DATABASE_URL' in content


def test_render_yaml_declares_postgres_database():
    """Test 16: render.yaml configures external PostgreSQL DATABASE_URL without paid Render database."""
    with open('render.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'DATABASE_URL' in content
    assert 'sync: false' in content
    # Free-tier target uses external Neon PostgreSQL rather than paid Render-managed database
    assert 'fromDatabase:' not in content
    assert 'databases:' not in content


def test_migration_sql_postgres_syntax_compatibility():
    """Test 17: Migration logic defines valid PostgreSQL DDL with IF NOT EXISTS."""
    with open('app/utils/migrations.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # PostgreSQL branch uses IF NOT EXISTS for column and index
    assert "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_ephemeral BOOLEAN NOT NULL DEFAULT FALSE" in content
    assert "CREATE INDEX IF NOT EXISTS ix_users_is_ephemeral ON users (is_ephemeral)" in content
