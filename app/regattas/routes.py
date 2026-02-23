import os
import uuid
from datetime import date

from urllib.parse import quote_plus

from flask import current_app, flash, make_response, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from weasyprint import HTML

from app import db
from app.models import Document, Regatta, RSVP, User
from app.regattas import bp


@bp.route("/")
@login_required
def index():
    today = date.today()
    upcoming = (
        Regatta.query.filter(Regatta.start_date >= today)
        .order_by(Regatta.start_date)
        .all()
    )
    past = (
        Regatta.query.filter(Regatta.start_date < today)
        .order_by(Regatta.start_date.desc())
        .all()
    )
    users = User.query.filter(User.invite_token.is_(None)).order_by(User.display_name).all()
    return render_template("index.html", upcoming=upcoming, past=past, users=users)


@bp.route("/schedule.pdf")
@login_required
def pdf():
    today = date.today()
    upcoming = (
        Regatta.query.filter(Regatta.start_date >= today)
        .order_by(Regatta.start_date)
        .all()
    )
    past = (
        Regatta.query.filter(Regatta.start_date < today)
        .order_by(Regatta.start_date.desc())
        .all()
    )
    html_str = render_template(
        "pdf_schedule.html",
        upcoming=upcoming,
        past=past,
        generated_date=today.strftime("%B %d, %Y"),
    )
    pdf_bytes = HTML(string=html_str).write_pdf()
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "inline; filename=race-crew-schedule.pdf"
    return response


@bp.route("/regattas/new", methods=["GET", "POST"])
@login_required
def create():
    if not current_user.is_admin:
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    if request.method == "POST":
        return _save_regatta(None)

    return render_template("regatta_form.html", regatta=None)


@bp.route("/regattas/<int:regatta_id>/edit", methods=["GET", "POST"])
@login_required
def edit(regatta_id: int):
    if not current_user.is_admin:
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    regatta = db.session.get(Regatta, regatta_id)
    if not regatta:
        flash("Regatta not found.", "error")
        return redirect(url_for("regattas.index"))

    if request.method == "POST":
        return _save_regatta(regatta)

    return render_template("regatta_form.html", regatta=regatta)


@bp.route("/regattas/<int:regatta_id>/delete", methods=["POST"])
@login_required
def delete(regatta_id: int):
    if not current_user.is_admin:
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    regatta = db.session.get(Regatta, regatta_id)
    if regatta:
        db.session.delete(regatta)
        db.session.commit()
        flash(f"Regatta '{regatta.name}' deleted.", "success")
    return redirect(url_for("regattas.index"))


@bp.route("/regattas/<int:regatta_id>/rsvp", methods=["POST"])
@login_required
def rsvp(regatta_id: int):
    status = request.form.get("status", "").lower()
    if status not in ("yes", "no", "maybe"):
        flash("Invalid RSVP status.", "error")
        return redirect(url_for("regattas.index"))

    existing = RSVP.query.filter_by(
        regatta_id=regatta_id, user_id=current_user.id
    ).first()

    if existing:
        existing.status = status
    else:
        db.session.add(
            RSVP(regatta_id=regatta_id, user_id=current_user.id, status=status)
        )

    db.session.commit()
    return redirect(url_for("regattas.index"))


@bp.route("/docs/<int:doc_id>")
@login_required
def download_doc(doc_id: int):
    doc = db.session.get(Document, doc_id)
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("regattas.index"))

    if doc.url:
        return redirect(doc.url)

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(
        upload_folder, doc.stored_filename, download_name=doc.original_filename
    )


@bp.route("/regattas/<int:regatta_id>/upload", methods=["POST"])
@login_required
def upload_doc(regatta_id: int):
    if not current_user.is_admin:
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    regatta = db.session.get(Regatta, regatta_id)
    if not regatta:
        flash("Regatta not found.", "error")
        return redirect(url_for("regattas.index"))

    doc_type = request.form.get("doc_type", "Other")
    doc_url = request.form.get("doc_url", "").strip()
    file = request.files.get("file")

    if doc_url:
        # URL-based document
        doc = Document(
            regatta_id=regatta_id,
            doc_type=doc_type,
            url=doc_url,
            uploaded_by=current_user.id,
        )
        db.session.add(doc)
        db.session.commit()
        flash(f"{doc_type} link added.", "success")
    elif file and file.filename:
        # File-based document
        ext = os.path.splitext(file.filename)[1].lower()
        stored_filename = f"{uuid.uuid4().hex}{ext}"

        upload_folder = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_folder, exist_ok=True)
        file.save(os.path.join(upload_folder, stored_filename))

        doc = Document(
            regatta_id=regatta_id,
            doc_type=doc_type,
            original_filename=file.filename,
            stored_filename=stored_filename,
            uploaded_by=current_user.id,
        )
        db.session.add(doc)
        db.session.commit()
        flash(f"{doc_type} uploaded.", "success")
    else:
        flash("Provide either a URL or a file.", "error")

    return redirect(url_for("regattas.edit", regatta_id=regatta_id))


@bp.route("/docs/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_doc(doc_id: int):
    if not current_user.is_admin:
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    doc = db.session.get(Document, doc_id)
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("regattas.index"))

    regatta_id = doc.regatta_id

    # Delete file from disk if it's a file-based document
    if doc.stored_filename:
        upload_folder = current_app.config["UPLOAD_FOLDER"]
        filepath = os.path.join(upload_folder, doc.stored_filename)
        if os.path.exists(filepath):
            os.remove(filepath)

    db.session.delete(doc)
    db.session.commit()
    flash("Document removed.", "success")
    return redirect(url_for("regattas.edit", regatta_id=regatta_id))


def _save_regatta(regatta: Regatta | None):
    name = request.form.get("name", "").strip()
    location = request.form.get("location", "").strip()
    location_url = request.form.get("location_url", "").strip()
    start_date_str = request.form.get("start_date", "")
    end_date_str = request.form.get("end_date", "")
    notes = request.form.get("notes", "").strip()

    if not name or not location or not start_date_str:
        flash("Name, location, and start date are required.", "error")
        return render_template("regatta_form.html", regatta=regatta)

    try:
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str) if end_date_str else None
    except ValueError:
        flash("Invalid date format.", "error")
        return render_template("regatta_form.html", regatta=regatta)

    if regatta is None:
        regatta = Regatta(created_by=current_user.id)
        db.session.add(regatta)

    regatta.name = name
    regatta.location = location
    if location_url:
        regatta.location_url = location_url
    else:
        # Auto-generate Google Maps search link from location text
        regatta.location_url = f"https://www.google.com/maps/search/{quote_plus(location)}"
    regatta.start_date = start_date
    regatta.end_date = end_date
    regatta.notes = notes or None

    db.session.commit()
    flash(f"Regatta '{name}' saved.", "success")
    return redirect(url_for("regattas.index"))
