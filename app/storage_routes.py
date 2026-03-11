from pathlib import Path

from flask import Blueprint, current_app, send_from_directory
from flask_login import login_required

bp = Blueprint("storage_bp", __name__)


@bp.route("/uploads/<path:filename>")
@login_required
def serve_file(filename: str):
    """Serve a locally stored file. Only used when S3 is not configured."""
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    base = Path(upload_folder)
    if not base.is_absolute():
        base = Path(current_app.root_path).parent / upload_folder
    return send_from_directory(str(base), filename)
