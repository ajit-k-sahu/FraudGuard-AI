from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.alerts import alerts_bp
from app.extensions import db
from app.models import FraudAlert
from app import log_audit_event

@alerts_bp.route('/', strict_slashes=False)
@login_required
def index():
    severity = request.args.get('severity', '').strip()
    status = request.args.get('status', '').strip()
    page = request.args.get('page', 1, type=int)

    query = FraudAlert.query

    # Authorization / Scoping
    if not current_user.is_admin:
        query = query.filter(FraudAlert.user_id == current_user.id)

    if severity in ['Medium', 'High', 'Critical']:
        query = query.filter(FraudAlert.severity == severity)

    if status == 'unread':
        query = query.filter(FraudAlert.is_read == False)
    elif status == 'read':
        query = query.filter(FraudAlert.is_read == True)

    pagination = query.order_by(FraudAlert.created_at.desc()).paginate(page=page, per_page=12, error_out=False)
    
    # Counts
    base_q = FraudAlert.query if current_user.is_admin else FraudAlert.query.filter_by(user_id=current_user.id)
    unread_total = base_q.filter_by(is_read=False).count()
    critical_total = base_q.filter_by(severity='Critical').count()
    medium_total = base_q.filter_by(severity='Medium').count()

    return render_template(
        'alerts/index.html',
        alerts=pagination.items,
        pagination=pagination,
        severity=severity,
        status=status,
        unread_total=unread_total,
        critical_total=critical_total,
        medium_total=medium_total
    )


@alerts_bp.route('/<int:alert_id>/read', methods=['POST'])
@login_required
def mark_as_read(alert_id):
    alert = FraudAlert.query.get_or_404(alert_id)
    if not current_user.is_admin and alert.user_id != current_user.id:
        abort(403)

    alert.is_read = True
    db.session.commit()
    log_audit_event('ALERT_READ', current_user.id, f"Marked alert #{alert.id} as read.")
    flash("Alert marked as resolved / read.", "success")
    return redirect(request.referrer or url_for('alerts.index'))


@alerts_bp.route('/read-all', methods=['POST'])
@login_required
def mark_all_read():
    query = FraudAlert.query.filter_by(is_read=False)
    if not current_user.is_admin:
        query = query.filter_by(user_id=current_user.id)
    
    updated_count = query.update({FraudAlert.is_read: True})
    db.session.commit()

    log_audit_event('ALERTS_ALL_READ', current_user.id, f"Marked {updated_count} alerts as read.")
    flash(f"All {updated_count} active alerts marked as read.", "success")
    return redirect(url_for('alerts.index'))
