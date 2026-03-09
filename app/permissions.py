"""Role-based permission decorators and helpers."""

from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user


def require_admin(f):
    """Decorator: deny access unless current_user is admin."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash("Access denied.", "error")
            return redirect(url_for("regattas.index"))
        return f(*args, **kwargs)

    return decorated


def require_skipper(f):
    """Decorator: deny access unless current_user is skipper or admin."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if not (current_user.is_admin or current_user.is_skipper):
            flash("Access denied.", "error")
            return redirect(url_for("regattas.index"))
        return f(*args, **kwargs)

    return decorated


def can_manage_regatta(user, regatta) -> bool:
    """True if user can edit/delete this regatta (owner or admin)."""
    if user.is_admin:
        return True
    return user.is_skipper and regatta.created_by == user.id


def can_rsvp_to_regatta(user, regatta) -> bool:
    """True if user can RSVP to this regatta.

    Allowed for: admin, regatta owner, crew of the regatta owner.
    """
    if user.is_admin:
        return True
    if regatta.created_by == user.id:
        return True
    # Check if user is crew of the regatta creator
    creator = regatta.creator
    if creator and user in creator.crew_members.all():
        return True
    return False
