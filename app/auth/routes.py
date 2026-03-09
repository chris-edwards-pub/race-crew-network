import logging

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.admin.email_service import is_email_configured, send_email
from app.auth import bp
from app.models import User

logger = logging.getLogger(__name__)


def _send_invite_email(email: str, invite_url: str, inviter_name: str) -> None:
    """Send a welcome email with the invite link."""
    subject = "You're invited to Race Crew Network"
    body_text = (
        f"You've been invited to join {inviter_name}'s crew on Race Crew Network!\n\n"
        f"Click the link below to set up your account:\n{invite_url}\n\n"
        "See you on the water!"
    )
    body_html = (
        "<h2>You're invited to Race Crew Network!</h2>"
        f"<p>You've been invited to join {inviter_name}'s crew. "
        "Click the link below to set up your account:</p>"
        f'<p><a href="{invite_url}">Accept Invitation</a></p>'
        "<p>See you on the water!</p>"
    )
    send_email(email, subject, body_text, body_html)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("regattas.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.invite_token is None and user.check_password(password):
            login_user(user)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("regattas.index"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/register/<token>", methods=["GET", "POST"])
def register(token: str):
    user = User.query.filter_by(invite_token=token).first_or_404()

    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        initials = request.form.get("initials", "").strip().upper()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if not display_name or not initials:
            flash("Name and initials are required.", "error")
        elif len(initials) < 2 or len(initials) > 3:
            flash("Initials must be 2-3 characters.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif password != password2:
            flash("Passwords do not match.", "error")
        else:
            user.display_name = display_name
            user.initials = initials
            user.set_password(password)
            user.invite_token = None  # Mark registration complete
            db.session.commit()
            login_user(user)
            flash("Welcome aboard!", "success")
            return redirect(url_for("regattas.index"))

    return render_template("register.html", user=user)


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        initials = request.form.get("initials", "").strip().upper()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if not display_name or not initials or not email:
            flash("Name, initials, and email are required.", "error")
        elif len(initials) < 2 or len(initials) > 3:
            flash("Initials must be 2-3 characters.", "error")
        elif email != current_user.email and User.query.filter_by(email=email).first():
            flash("That email is already in use.", "error")
        elif password and len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif password and password != password2:
            flash("Passwords do not match.", "error")
        else:
            current_user.display_name = display_name
            current_user.initials = initials
            current_user.email = email
            current_user.phone = request.form.get("phone", "").strip() or None
            current_user.email_opt_in = request.form.get("email_opt_in") == "on"
            if password:
                current_user.set_password(password)
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("auth.profile"))

    return render_template("profile.html")


@bp.route("/crew/<int:user_id>")
@login_required
def view_profile(user_id: int):
    user = db.session.get(User, user_id)
    if not user or user.invite_token:
        flash("User not found.", "error")
        return redirect(url_for("regattas.index"))
    return render_template("view_profile.html", user=user)


@bp.route("/admin/users")
@login_required
def admin_users():
    if not current_user.is_admin:
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    users = User.query.order_by(User.display_name).all()
    return render_template(
        "admin_users.html",
        users=users,
        email_configured=is_email_configured(),
    )


@bp.route("/admin/users/invite", methods=["POST"])
@login_required
def invite_user():
    if not current_user.is_admin:
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    import secrets

    email = request.form.get("email", "").strip().lower()
    if not email:
        flash("Email is required.", "error")
        return redirect(url_for("auth.admin_users"))

    if User.query.filter_by(email=email).first():
        flash("A user with that email already exists.", "error")
        return redirect(url_for("auth.admin_users"))

    token = secrets.token_urlsafe(32)
    user = User(
        email=email,
        password_hash="pending",
        display_name=email,
        initials="??",
        invite_token=token,
    )
    db.session.add(user)
    db.session.commit()

    invite_url = url_for("auth.register", token=token, _external=True)

    send_email_invite = request.form.get("send_email_invite") == "on"
    if send_email_invite and is_email_configured():
        try:
            _send_invite_email(email, invite_url, current_user.display_name)
            flash(f"Invite email sent to {email}.", "success")
        except Exception:
            logger.exception("Failed to send invite email to %s", email)
            flash("Failed to send invite email. Copy the link below.", "error")
            flash(f"Invite link: {invite_url}", "success")
    else:
        flash(f"Invite link: {invite_url}", "success")

    return redirect(url_for("auth.admin_users"))


@bp.route("/admin/users/resend-invites", methods=["POST"])
@login_required
def resend_invites():
    if not current_user.is_admin:
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    if not is_email_configured():
        flash("Email is not configured.", "error")
        return redirect(url_for("auth.admin_users"))

    user_ids = request.form.getlist("user_ids")
    if not user_ids:
        flash("No users selected.", "error")
        return redirect(url_for("auth.admin_users"))

    sent = 0
    failed = 0
    for uid in user_ids:
        user = db.session.get(User, int(uid))
        if not user or not user.invite_token:
            continue
        invite_url = url_for("auth.register", token=user.invite_token, _external=True)
        try:
            _send_invite_email(user.email, invite_url, current_user.display_name)
            sent += 1
        except Exception:
            logger.exception("Failed to resend invite to %s", user.email)
            failed += 1

    if sent:
        flash(f"Invite emails sent to {sent} user(s).", "success")
    if failed:
        flash(f"Failed to send {failed} invite(s).", "error")
    if not sent and not failed:
        flash("No pending users in selection.", "warning")

    return redirect(url_for("auth.admin_users"))


@bp.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_user(user_id: int):
    if not current_user.is_admin:
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("auth.admin_users"))

    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        initials = request.form.get("initials", "").strip().upper()
        email = request.form.get("email", "").strip().lower()
        is_admin = request.form.get("is_admin") == "on"
        password = request.form.get("password", "")

        if not display_name or not initials or not email:
            flash("Name, initials, and email are required.", "error")
        elif len(initials) < 2 or len(initials) > 3:
            flash("Initials must be 2-3 characters.", "error")
        elif email != user.email and User.query.filter_by(email=email).first():
            flash("That email is already in use.", "error")
        elif password and len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        else:
            user.display_name = display_name
            user.initials = initials
            user.email = email
            user.is_admin = is_admin
            user.phone = request.form.get("phone", "").strip() or None
            if password:
                user.set_password(password)
            db.session.commit()
            flash(f"User '{display_name}' updated.", "success")
            return redirect(url_for("auth.admin_users"))

    return render_template("edit_user.html", user=user)


@bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
def delete_user(user_id: int):
    if not current_user.is_admin:
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "error")
    elif user.id == current_user.id:
        flash("You cannot delete yourself.", "error")
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f"User {user.display_name} deleted.", "success")

    return redirect(url_for("auth.admin_users"))
