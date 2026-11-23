from flask import render_template
from flask_login import login_required, current_user
from app.dashboard import dashboard_bp
from app.services.analytics_service import AnalyticsService
from app.services.ml_service import MLService

@dashboard_bp.route('/')
def landing():
    # Gather aggregate high-level figures for demo display on the landing page
    summary = AnalyticsService.get_dashboard_summary(is_admin=True)
    ml_meta = MLService.get_instance().get_metadata()
    return render_template('index.html', summary=summary, ml_meta=ml_meta)


@dashboard_bp.route('/dashboard')
@login_required
def index():
    is_admin = current_user.is_admin
    user_id = current_user.id
    
    summary = AnalyticsService.get_dashboard_summary(user_id=user_id, is_admin=is_admin)
    charts = AnalyticsService.get_chart_data(user_id=user_id, is_admin=is_admin)
    recent_txns = AnalyticsService.get_recent_transactions(limit=8, user_id=user_id, is_admin=is_admin)
    recent_high_risk = AnalyticsService.get_recent_high_risk(limit=5, user_id=user_id, is_admin=is_admin)
    ml_meta = MLService.get_instance().get_metadata()

    return render_template(
        'dashboard/index.html',
        summary=summary,
        charts=charts,
        recent_txns=recent_txns,
        recent_high_risk=recent_high_risk,
        ml_meta=ml_meta
    )
