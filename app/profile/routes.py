from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.profile import profile_bp
from app.extensions import db
from app.forms import UpdateProfileForm
from app import log_audit_event

@profile_bp.route('/', methods=['GET', 'POST'], strict_slashes=False)
@login_required
def index():
    form = UpdateProfileForm()

    if request.method == 'GET':
        form.name.data = current_user.name

    if form.validate_on_submit():
        # Protect shared demonstration accounts against lockout and defacement
        if current_user.is_demo_account:
            if form.new_password.data:
                flash("Password modifications are disabled on public demonstration accounts to preserve recruiter access.", "warning")
                return redirect(url_for('profile.index'))
            if form.name.data.strip() != current_user.name:
                flash("Profile identity modifications are disabled on public demonstration accounts to preserve recruiter access.", "warning")
                return redirect(url_for('profile.index'))
            flash("Your profile information has been saved.", "info")
            return redirect(url_for('profile.index'))

        current_user.name = form.name.data.strip()
        
        # If user is changing password
        if form.new_password.data:
            if not form.current_password.data:
                flash("Current password is required to set a new password.", "warning")
                return render_template('profile/index.html', form=form)
            
            if not current_user.check_password(form.current_password.data):
                flash("Current password provided does not match our records.", "danger")
                return render_template('profile/index.html', form=form)

            current_user.set_password(form.new_password.data)
            log_audit_event('PASSWORD_CHANGED', current_user.id, "User updated their account password.")
            flash("Your password and profile have been successfully updated.", "success")
        else:
            log_audit_event('PROFILE_UPDATED', current_user.id, f"User updated profile name to {current_user.name}")
            flash("Your profile information has been saved.", "success")

        db.session.commit()
        return redirect(url_for('profile.index'))

    return render_template('profile/index.html', form=form)
