"""
Command-Line Utility to Create or Update Administrator Account for FraudGuard AI.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import User

def create_or_update_admin(name, email, password):
    app = create_app('development')
    with app.app_context():
        db.create_all()
        user = User.query.filter_by(email=email.lower().strip()).first()
        if user:
            user.name = name
            user.role = 'admin'
            user.is_active_account = True
            user.set_password(password)
            print(f"Updated existing user '{user.email}' with administrative role and new password.")
        else:
            user = User(
                name=name,
                email=email.lower().strip(),
                role='admin',
                is_active_account=True
            )
            user.set_password(password)
            db.session.add(user)
            print(f"Created new administrative account for '{user.email}'.")

        db.session.commit()

if __name__ == '__main__':
    admin_name = os.environ.get('ADMIN_NAME', 'Security Administrator')
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@fraudguard.ai')
    admin_password = os.environ.get('ADMIN_PASSWORD')

    if len(sys.argv) >= 4:
        admin_name = sys.argv[1]
        admin_email = sys.argv[2]
        admin_password = sys.argv[3]

    is_prod = os.environ.get('FLASK_ENV', 'development').lower() == 'production'
    if not admin_password:
        if is_prod:
            print("ERROR: In production, ADMIN_PASSWORD must be explicitly provided (via environment variable or command-line argument).", file=sys.stderr)
            sys.exit(1)
        else:
            admin_password = 'AdminDevPassword2026!'

    if is_prod and len(admin_password) < 12:
        print("ERROR: In production, administrator password must be at least 12 characters long.", file=sys.stderr)
        sys.exit(1)

    create_or_update_admin(admin_name, admin_email, admin_password)
