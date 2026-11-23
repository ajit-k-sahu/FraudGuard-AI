"""
Database Migration Utility for FraudGuard AI (Phase B, Task 1.3.2).

Provides:
- Idempotent, engine-agnostic schema evolution for SQLite, PostgreSQL, and ANSI SQL.
- Safe column addition for 'is_ephemeral' without data loss.
- Failure logging and safe error propagation.
"""

import logging
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def run_migrations(app=None, db_instance=None):
    """
    Applies additive, backward-compatible schema migrations idempotently.
    Supports SQLite, PostgreSQL, and other SQLAlchemy-supported SQL dialects.
    Fails safely and logs any unexpected migration errors.
    """
    from app.extensions import db
    db_obj = db_instance or db

    ctx_mgr = app.app_context() if app else (db_obj.app.app_context() if hasattr(db_obj, 'app') and db_obj.app else None)

    def _execute():
        engine = db_obj.engine
        dialect_name = engine.dialect.name.lower()
        inspector = inspect(engine)

        existing_tables = inspector.get_table_names()
        # Fresh database: if 'users' table does not exist at all, db.create_all() creates full schema
        if 'users' not in existing_tables:
            logger.info("Initializing fresh database schema via db.create_all()...")
            db_obj.create_all()
            return True

        columns = [c['name'] for c in inspector.get_columns('users')]
        if 'is_ephemeral' not in columns:
            logger.info(f"Existing database detected without 'is_ephemeral' on dialect '{dialect_name}'. Running additive migration...")
            try:
                with engine.begin() as conn:
                    if 'sqlite' in dialect_name:
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_ephemeral BOOLEAN NOT NULL DEFAULT 0"))
                        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_is_ephemeral ON users (is_ephemeral)"))
                    elif 'postgres' in dialect_name:
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_ephemeral BOOLEAN NOT NULL DEFAULT FALSE"))
                        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_is_ephemeral ON users (is_ephemeral)"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_ephemeral BOOLEAN DEFAULT FALSE"))
                        conn.execute(text("CREATE INDEX ix_users_is_ephemeral ON users (is_ephemeral)"))
                logger.info("Additive migration successful: 'is_ephemeral' column and index added.")
            except Exception as e:
                logger.error(f"Database schema migration failed on dialect '{dialect_name}': {str(e)}", exc_info=True)
                raise RuntimeError(f"Database schema migration failed: {str(e)}") from e
        else:
            logger.debug("Database schema is up-to-date: 'is_ephemeral' column already present.")

        return True

    if ctx_mgr:
        with ctx_mgr:
            return _execute()
    else:
        return _execute()
