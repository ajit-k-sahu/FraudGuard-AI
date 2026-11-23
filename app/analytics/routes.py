from flask import render_template, jsonify
from flask_login import login_required, current_user
from app.analytics import analytics_bp
from app.services.analytics_service import AnalyticsService

@analytics_bp.route('/', strict_slashes=False)
@login_required
def index():
    user_id = current_user.id
    is_admin = current_user.is_admin

    summary = AnalyticsService.get_dashboard_summary(user_id=user_id, is_admin=is_admin)
    charts = AnalyticsService.get_chart_data(user_id=user_id, is_admin=is_admin)

    return render_template(
        'analytics/index.html',
        summary=summary,
        charts=charts
    )


@analytics_bp.route('/data')
@login_required
def chart_data_api():
    """Returns JSON payload to support client-side live updating of charts."""
    user_id = current_user.id
    is_admin = current_user.is_admin
    charts = AnalyticsService.get_chart_data(user_id=user_id, is_admin=is_admin)
    return jsonify(charts)
