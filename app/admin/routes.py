from functools import wraps
from flask import render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from app.admin import admin_bp
from app.extensions import db
from app.models import User, Transaction, Prediction, AuditLog, FraudAlert
from app.services.analytics_service import AnalyticsService
from app.services.ml_service import MLService
from app import log_audit_event

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.path))
        if not current_user.is_admin:
            log_audit_event(
                'UNAUTHORIZED_ADMIN_ACCESS_ATTEMPT',
                current_user.id,
                f"User {current_user.email} attempted to access admin route {request.path}"
            )
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/', strict_slashes=False)
@login_required
@admin_required
def index():
    users = User.query.order_by(User.created_at.desc()).all()
    recent_audit_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(15).all()
    summary = AnalyticsService.get_dashboard_summary(is_admin=True)
    ml_meta = MLService.get_instance().get_metadata()
    high_risk_txns = Transaction.query.join(Prediction).filter(
        Prediction.risk_level.in_(['High', 'Critical'])
    ).order_by(Transaction.created_at.desc()).limit(8).all()

    return render_template(
        'admin/index.html',
        users=users,
        audit_logs=recent_audit_logs,
        summary=summary,
        ml_meta=ml_meta,
        high_risk_txns=high_risk_txns
    )


@admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot deactivate your own administrative account.", "warning")
        return redirect(url_for('admin.index'))

    # Protect shared demonstration accounts from administrative deactivation
    if user.is_demo_account:
        flash("The primary demonstration account cannot be deactivated.", "warning")
        return redirect(url_for('admin.index'))

    user.is_active_account = not user.is_active_account
    status_str = "activated" if user.is_active_account else "deactivated"
    db.session.commit()

    log_audit_event(
        'USER_STATUS_CHANGE',
        current_user.id,
        f"Admin {current_user.email} {status_str} account {user.email} (ID #{user.id})"
    )
    flash(f"User {user.email} has been successfully {status_str}.", "success")
    return redirect(url_for('admin.index'))


@admin_bp.route('/audit-logs')
@login_required
@admin_required
def audit_logs():
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action', '').strip()
    
    query = AuditLog.query
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
        
    pagination = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    actions = [r[0] for r in db.session.query(AuditLog.action).distinct().all()]

    return render_template(
        'admin/audit_logs.html',
        pagination=pagination,
        logs=pagination.items,
        actions=actions,
        selected_action=action_filter
    )


@admin_bp.route('/model-diagnostics')
@login_required
@admin_required
def model_diagnostics():
    ml = MLService.get_instance()
    metadata = ml.get_metadata()
    importances = ml.get_feature_importances()
    return render_template(
        'admin/model_diagnostics.html',
        metadata=metadata,
        importances=importances
    )
