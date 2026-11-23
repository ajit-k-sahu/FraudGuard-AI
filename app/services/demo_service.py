"""
Ephemeral Recruiter Demo Service for FraudGuard AI (Phase B, Task 1.3).

Provides:
- Ephemeral demo user provisioning with unpredictable credentials.
- Atomic baseline demonstration data cloning (Transactions, Predictions, FraudAlerts).
- Safe cascade cleanup of expired ephemeral accounts.
"""

import os
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from flask import current_app
from app.extensions import db
from app.models import User, Transaction, Prediction, FraudAlert, AuditLog


def utc_now():
    """Returns naive UTC datetime for consistent database storage and comparisons without deprecation warnings."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DemoService:
    @classmethod
    def get_baseline_transactions(cls):
        """
        Retrieves approved baseline demonstration transactions from the permanent demo account.
        Only sources from non-ephemeral template records to prevent cross-contamination.
        """
        demo_email = 'analyst@bank.com'
        if current_app:
            demo_email = current_app.config.get('DEMO_USER_EMAIL', 'analyst@bank.com')

        # First priority: permanent demo analyst account
        analyst = User.query.filter_by(email=demo_email.lower().strip(), is_ephemeral=False).first()
        if analyst:
            txns = Transaction.query.filter_by(user_id=analyst.id, is_demo=True).order_by(Transaction.id.asc()).all()
            if txns:
                return txns

        # Second priority: any non-ephemeral account with is_demo=True transactions
        return Transaction.query.join(User).filter(
            User.is_ephemeral == False,
            Transaction.is_demo == True
        ).order_by(Transaction.id.asc()).all()

    @classmethod
    def clone_baseline_data_for_user(cls, user_id):
        """
        Clones approved baseline demonstration transactions, predictions,
        and alerts for the specified user_id.
        Preserves valid foreign-key relationships while generating fresh primary keys.
        """
        baselines = cls.get_baseline_transactions()
        if not baselines:
            raise RuntimeError(
                "Baseline demonstration transactions are unavailable in the database. "
                "Please ensure demonstration data has been seeded before creating ephemeral accounts."
            )

        cloned_transactions = []
        for src_t in baselines:
            # Generate new unique transaction reference
            new_ref = f"TXN-DEMO-{uuid.uuid4().hex[:10].upper()}"

            cloned_t = Transaction(
                transaction_ref=new_ref,
                user_id=user_id,
                amount=src_t.amount,
                transaction_type=src_t.transaction_type,
                sender_account=src_t.sender_account,
                receiver_account=src_t.receiver_account,
                channel=src_t.channel,
                location=src_t.location,
                device=src_t.device,
                frequency_24h=src_t.frequency_24h,
                account_age_days=src_t.account_age_days,
                previous_amount=src_t.previous_amount,
                old_balance_orig=src_t.old_balance_orig,
                new_balance_orig=src_t.new_balance_orig,
                old_balance_dest=src_t.old_balance_dest,
                new_balance_dest=src_t.new_balance_dest,
                is_demo=True,
                created_at=src_t.created_at or utc_now()
            )
            db.session.add(cloned_t)
            db.session.flush()  # Populates cloned_t.id for foreign-key references

            # Clone Prediction record if present on source transaction
            if src_t.prediction:
                src_p = src_t.prediction
                cloned_p = Prediction(
                    transaction_id=cloned_t.id,
                    model_name=src_p.model_name,
                    model_version=src_p.model_version,
                    fraud_probability=src_p.fraud_probability,
                    is_fraud_predicted=src_p.is_fraud_predicted,
                    risk_level=src_p.risk_level,
                    explanation_summary=src_p.explanation_summary,
                    recommended_action=src_p.recommended_action,
                    created_at=src_p.created_at or utc_now()
                )
                db.session.add(cloned_p)

            # Clone FraudAlert records if present on source transaction
            if src_t.alerts:
                for src_a in src_t.alerts.all():
                    cloned_a = FraudAlert(
                        transaction_id=cloned_t.id,
                        user_id=user_id,
                        severity=src_a.severity,
                        title=src_a.title,
                        message=src_a.message,
                        is_read=src_a.is_read,
                        created_at=src_a.created_at or utc_now()
                    )
                    db.session.add(cloned_a)

            cloned_transactions.append(cloned_t)

        return cloned_transactions

    @classmethod
    def create_ephemeral_demo_user(cls, name=None):
        """
        Creates a new, unique ephemeral demo user and clones baseline demonstration data.
        Executes within an atomic transaction. On error, rolls back completely.
        """
        session_id = uuid.uuid4().hex[:12]
        user_name = name or f"Demo Recruiter ({session_id[:6]})"
        user_email = f"recruiter_{session_id}@demo.local"
        unpredictable_password = secrets.token_urlsafe(32)

        try:
            user = User(
                name=user_name,
                email=user_email,
                role='user',  # Strictly standard user, never administrator
                is_active_account=True,
                is_ephemeral=True
            )
            user.set_password(unpredictable_password)
            db.session.add(user)
            db.session.flush()  # Populates user.id

            # Clone approved baseline data into the new user's ownership
            cls.clone_baseline_data_for_user(user.id)

            db.session.commit()
            return user
        except Exception:
            db.session.rollback()
            raise

    @classmethod
    def cleanup_expired_demo_sessions(cls, max_age_hours=None):
        """
        Purges expired ephemeral demo users and their cascade-associated records.
        Strictly guarantees non-ephemeral users and administrators are never deleted.
        Returns the number of ephemeral user accounts deleted.
        """
        if max_age_hours is None:
            max_age_hours = 2
            if current_app:
                max_age_hours = current_app.config.get('DEMO_SESSION_LIFETIME_HOURS', 2)

        cutoff = utc_now() - timedelta(hours=max_age_hours)

        try:
            # Query only ephemeral accounts created before the cutoff
            expired_users = User.query.filter(
                User.is_ephemeral == True,
                User.created_at < cutoff
            ).all()

            deleted_count = 0
            for user in expired_users:
                # Defensive sanity check: NEVER delete non-ephemeral or admin accounts
                if not user.is_ephemeral or user.is_admin:
                    continue

                # Clean up any audit logs specifically tied to this ephemeral user
                AuditLog.query.filter_by(user_id=user.id).delete(synchronize_session=False)

                # SQLAlchemy ORM cascade deletion cleans child transactions, predictions, and alerts
                db.session.delete(user)
                deleted_count += 1

            db.session.commit()
            if current_app:
                current_app.logger.info(
                    f"[DemoCleanup] Successfully purged {deleted_count} expired ephemeral demo session(s) "
                    f"(retention window: {max_age_hours}h, cutoff: {cutoff.strftime('%Y-%m-%d %H:%M:%S UTC')})."
                )
            return deleted_count
        except Exception as e:
            db.session.rollback()
            if current_app:
                current_app.logger.error(
                    f"[DemoCleanup] Error executing expired demo session cleanup: {str(e)}",
                    exc_info=True
                )
            raise
