"""
Command-Line Interface (CLI) Commands for FraudGuard AI.
Registered with the Flask application instance and invoked via `flask <command>`.
"""

import sys
import click
from flask.cli import with_appcontext


def register_cli_commands(app):
    """Registers custom command-line interface commands with the Flask application."""

    @app.cli.command('cleanup-demo-sessions')
    @click.option(
        '--max-age-hours',
        default=None,
        type=int,
        help='Maximum age in hours before ephemeral demo sessions expire. Defaults to DEMO_SESSION_LIFETIME_HOURS.'
    )
    @click.option(
        '--quiet',
        is_flag=True,
        default=False,
        help='Suppress informational stdout messages.'
    )
    @with_appcontext
    def cleanup_demo_sessions_command(max_age_hours, quiet):
        """Purge expired ephemeral recruiter demo accounts and associated data."""
        from app.services.demo_service import DemoService
        try:
            deleted_count = DemoService.cleanup_expired_demo_sessions(max_age_hours=max_age_hours)
            if not quiet:
                click.echo(f"[DemoCleanup] Successfully purged {deleted_count} expired ephemeral demo session(s).")
        except Exception as e:
            click.echo(f"[DemoCleanup ERROR] Failed to clean up expired demo sessions: {str(e)}", err=True)
            sys.exit(1)
