from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.extensions import db, limiter
from app.models import User
from app.forms import LoginForm, RegistrationForm
from app import log_audit_event

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(lambda: current_app.config.get('RATELIMIT_LOGIN', '5/minute'), methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                log_audit_event('LOGIN_BLOCKED_INACTIVE', user.id, f"Attempted login on deactivated/expired account: {user.email}")
                flash("Your account has been deactivated or expired. Please contact support.", "danger")
                return render_template('auth/login.html', form=form)

            login_user(user, remember=form.remember_me.data)
            log_audit_event('LOGIN_SUCCESS', user.id, f"User {user.email} logged in successfully.")
            flash(f"Welcome back, {user.name}!", "success")
            
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            log_audit_event('LOGIN_FAILED', None, f"Failed login attempt for email: {form.email.data}")
            flash("Invalid email address or password. Please verify your credentials.", "danger")

    return render_template('auth/login.html', form=form)


@auth_bp.route('/demo-login', methods=['POST'])
@limiter.limit(lambda: current_app.config.get('RATELIMIT_DEMO_LOGIN', '10/minute'), methods=['POST'])
def demo_login():
    """
    Dedicated endpoint for secure one-click recruiter demonstration access.
    Provisions a unique ephemeral user with isolated baseline records,
    authenticates the session with remember=False, and redirects to the analyst dashboard.
    """
    from app.services.demo_service import DemoService

    # If already authenticated as non-ephemeral user, redirect to dashboard
    if current_user.is_authenticated and not current_user.is_ephemeral:
        return redirect(url_for('dashboard.index'))

    # If already authenticated as active (non-expired) ephemeral user, redirect to dashboard
    if current_user.is_authenticated and current_user.is_ephemeral and not current_user.is_expired:
        return redirect(url_for('dashboard.index'))

    try:
        user = DemoService.create_ephemeral_demo_user()
        login_user(user, remember=False)
        log_audit_event('DEMO_LOGIN_SUCCESS', user.id, f"One-click recruiter demo session provisioned: {user.email}")
        flash("Welcome to your isolated demonstration workspace! You can now analyze transactions and evaluate fraud risk.", "success")
        return redirect(url_for('dashboard.index'))
    except Exception as e:
        current_app.logger.error(f"Failed to provision one-click recruiter demo user: {str(e)}", exc_info=True)
        flash("Unable to provision live demonstration workspace at this time. Please try again shortly or use standard sign in.", "danger")
        return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit(lambda: current_app.config.get('RATELIMIT_REGISTER', '5/hour'), methods=['POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data.strip(),
            email=form.email.data.lower().strip(),
            role='user',
            is_active_account=True
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        log_audit_event('USER_REGISTERED', user.id, f"New user account registered: {user.email}")
        flash("Registration successful! You may now sign in to your FraudGuard AI account.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    user_id = current_user.id
    email = current_user.email
    logout_user()
    log_audit_event('LOGOUT', user_id, f"User {email} logged out.")
    flash("You have been signed out safely.", "info")
    return redirect(url_for('dashboard.landing'))
