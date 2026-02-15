from flask import Blueprint

bp = Blueprint("calendar", __name__)

from app.calendar import routes  # noqa: E402, F401
