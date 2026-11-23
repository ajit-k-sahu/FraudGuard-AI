from datetime import datetime, timezone, timedelta
import json
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager


def utc_now():
    """Returns naive UTC datetime for consistent database storage and comparisons without deprecation warnings."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # 'user' or 'admin'
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    is_ephemeral = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    transactions = db.relationship('Transaction', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    alerts = db.relationship('FraudAlert', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_expired(self):
        """
        Determines whether an ephemeral demo account has exceeded its configured lifetime.
        Non-ephemeral users (including admin and permanent analyst) never expire.
        """
        if not getattr(self, 'is_ephemeral', False):
            return False

        if not self.created_at:
            return False

        from flask import current_app
        lifetime_hours = 2
        if current_app:
            lifetime_hours = current_app.config.get('DEMO_SESSION_LIFETIME_HOURS', 2)

        created_utc = self.created_at
        if created_utc.tzinfo is not None:
            created_utc = created_utc.astimezone(timezone.utc).replace(tzinfo=None)

        now_utc = utc_now()
        return now_utc >= (created_utc + timedelta(hours=lifetime_hours))

    @property
    def is_demo_account(self):
        """Identifies whether this user account is a designated public demonstration account."""
        if getattr(self, 'is_ephemeral', False):
            return True
        from flask import current_app
        if current_app:
            demo_accounts = current_app.config.get('DEMO_ACCOUNTS', set())
            demo_email = current_app.config.get('DEMO_USER_EMAIL', 'analyst@bank.com')
            email_clean = (self.email or '').lower().strip()
            return email_clean in demo_accounts or email_clean == (demo_email or '').lower().strip()
        return (self.email or '').lower().strip() == 'analyst@bank.com'

    @property
    def is_active(self):
        # Override Flask-Login is_active to respect admin deactivation and demo expiration
        if getattr(self, 'is_ephemeral', False) and self.is_expired:
            return False
        return self.is_active_account

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'


@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    if user and getattr(user, 'is_ephemeral', False) and user.is_expired:
        return None
    return user


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    transaction_ref = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(32), nullable=False)  # Payment, Transfer, Cash Withdrawal, Deposit, Purchase
    sender_account = db.Column(db.String(64), nullable=False)
    receiver_account = db.Column(db.String(64), nullable=False)
    channel = db.Column(db.String(32), nullable=False)  # Mobile Banking, Internet Banking, ATM, POS, UPI
    location = db.Column(db.String(64), nullable=False, default='Domestic')
    device = db.Column(db.String(64), nullable=False, default='Mobile App')
    
    frequency_24h = db.Column(db.Integer, nullable=False, default=1)
    account_age_days = db.Column(db.Integer, nullable=False, default=365)
    previous_amount = db.Column(db.Float, nullable=False, default=0.0)
    
    old_balance_orig = db.Column(db.Float, nullable=False, default=0.0)
    new_balance_orig = db.Column(db.Float, nullable=False, default=0.0)
    old_balance_dest = db.Column(db.Float, nullable=False, default=0.0)
    new_balance_dest = db.Column(db.Float, nullable=False, default=0.0)
    
    is_demo = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)

    # Relationships
    prediction = db.relationship('Prediction', backref='transaction', uselist=False, cascade='all, delete-orphan')
    alerts = db.relationship('FraudAlert', backref='transaction', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def created_at_ist(self):
        from app.utils.timezone import to_ist
        return to_ist(self.created_at)

    @property
    def formatted_ist(self):
        from app.utils.timezone import format_ist
        return format_ist(self.created_at)

    def to_dict(self):
        pred = self.prediction
        return {
            'id': self.id,
            'transaction_ref': self.transaction_ref,
            'amount': self.amount,
            'transaction_type': self.transaction_type,
            'sender_account': self.sender_account,
            'receiver_account': self.receiver_account,
            'channel': self.channel,
            'location': self.location,
            'device': self.device,
            'frequency_24h': self.frequency_24h,
            'account_age_days': self.account_age_days,
            'previous_amount': self.previous_amount,
            'is_demo': self.is_demo,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'created_at_ist': self.formatted_ist,
            'prediction': pred.to_dict() if pred else None
        }

    def __repr__(self):
        return f'<Transaction {self.transaction_ref} - ${self.amount}>'


class Prediction(db.Model):
    __tablename__ = 'predictions'

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id', ondelete='CASCADE'), unique=True, nullable=False)
    
    model_name = db.Column(db.String(64), nullable=False, default='FraudGuard-Ensemble')
    model_version = db.Column(db.String(32), nullable=False, default='1.0.0')
    fraud_probability = db.Column(db.Float, nullable=False)  # 0.0000 to 1.0000
    is_fraud_predicted = db.Column(db.Boolean, nullable=False)
    risk_level = db.Column(db.String(20), nullable=False)  # Low, Medium, High
    
    explanation_summary = db.Column(db.Text, nullable=True)  # JSON formatted array of contributing factor strings
    recommended_action = db.Column(db.String(160), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    def get_explanations(self):
        if not self.explanation_summary:
            return []
        try:
            return json.loads(self.explanation_summary)
        except Exception:
            return [self.explanation_summary]

    def to_dict(self):
        return {
            'id': self.id,
            'transaction_id': self.transaction_id,
            'model_name': self.model_name,
            'model_version': self.model_version,
            'fraud_probability': round(self.fraud_probability, 4),
            'fraud_probability_pct': round(self.fraud_probability * 100, 2),
            'is_fraud_predicted': self.is_fraud_predicted,
            'risk_level': self.risk_level,
            'explanations': self.get_explanations(),
            'recommended_action': self.recommended_action,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

    def __repr__(self):
        return f'<Prediction TXN#{self.transaction_id} Risk={self.risk_level} ({self.fraud_probability:.2%})>'


class FraudAlert(db.Model):
    __tablename__ = 'fraud_alerts'

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    
    severity = db.Column(db.String(20), nullable=False)  # Medium, High, Critical
    title = db.Column(db.String(128), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)

    @property
    def created_at_ist(self):
        from app.utils.timezone import to_ist
        return to_ist(self.created_at)

    @property
    def formatted_ist(self):
        from app.utils.timezone import format_ist
        return format_ist(self.created_at)

    def to_dict(self):
        return {
            'id': self.id,
            'transaction_id': self.transaction_id,
            'transaction_ref': self.transaction.transaction_ref if self.transaction else None,
            'severity': self.severity,
            'title': self.title,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'created_at_ist': self.formatted_ist
        }

    def __repr__(self):
        return f'<FraudAlert #{self.id} [{self.severity}] {self.title}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = db.Column(db.String(64), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)

    @property
    def created_at_ist(self):
        from app.utils.timezone import to_ist
        return to_ist(self.created_at)

    @property
    def formatted_ist(self):
        from app.utils.timezone import format_ist
        return format_ist(self.created_at)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_email': self.user.email if self.user else 'System/Anonymous',
            'action': self.action,
            'ip_address': self.ip_address,
            'details': self.details,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'created_at_ist': self.formatted_ist
        }

    def __repr__(self):
        return f'<AuditLog {self.action} by User {self.user_id} at {self.created_at}>'
