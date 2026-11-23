"""
Scheduled Cleanup Script for Expired Ephemeral Recruiter Demo Accounts.
Invoked periodically by external schedulers (Render Cron, Heroku Scheduler, Linux crontab, etc.).
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.demo_service import DemoService


def run_cleanup(app=None, max_age_hours=None, quiet=False):
    """Executes the expired demo session cleanup in the appropriate Flask application context."""
    if app is None:
        try:
            from flask import current_app
            if current_app:
                app = current_app._get_current_object()
        except RuntimeError:
            pass

    if app is None:
        env_name = os.environ.get('FLASK_ENV', 'development')
        app = create_app(env_name)

    with app.app_context():
        try:
            effective_max_age = max_age_hours
            if effective_max_age is None:
                effective_max_age = int(app.config.get('DEMO_SESSION_LIFETIME_HOURS', 2))
            deleted = DemoService.cleanup_expired_demo_sessions(max_age_hours=effective_max_age)
            if not quiet:
                print(f"[DemoCleanup] Successfully purged {deleted} expired demo session(s) (window: {effective_max_age}h).")
            return 0
        except Exception as e:
            print(f"[DemoCleanup ERROR] Cleanup execution failed: {e}", file=sys.stderr)
            return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Purge expired ephemeral recruiter demo accounts.")
    parser.add_argument(
        '--max-age-hours',
        type=int,
        default=None,
        help="Retention window in hours before ephemeral accounts are deleted."
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help="Suppress informational stdout output."
    )
    args = parser.parse_args()

    sys.exit(run_cleanup(max_age_hours=args.max_age_hours, quiet=args.quiet))
