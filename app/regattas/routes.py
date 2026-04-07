import logging
import os
import uuid
from datetime import date
from urllib.parse import quote_plus

from flask import (flash, make_response, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required
from weasyprint import HTML

from app import db, storage
from app.models import RSVP, Document, Regatta, User
from app.notifications.service import (get_eligible_crew, notify_crew,
                                       notify_rsvp_to_skipper)
from app.permissions import can_manage_regatta, can_rsvp_to_regatta
from app.regattas import bp

logger = logging.getLogger(__name__)


def _apply_schedule_filters(upcoming, past, user):
    """Apply skipper and RSVP query-string filters to regatta lists."""
    skipper_id = request.args.get("skipper", type=int)
    if skipper_id is None and user.is_skipper:
        skipper_id = user.id
    # skipper_id == 0 means "All Schedules" (explicit selection, no filter)
    if skipper_id:
        upcoming = [r for r in upcoming if r.created_by == skipper_id]
        past = [r for r in past if r.created_by == skipper_id]

    rsvp_filters = [
        v.lower()
        for v in request.args.getlist("rsvp")
        if v.lower() in ("yes", "no", "maybe")
    ]
    if rsvp_filters and set(rsvp_filters) != {"yes", "no", "maybe"}:
        visible_ids = {r.id for r in upcoming + past}
        rsvp_regatta_ids = {
            r.regatta_id
            for r in RSVP.query.filter(
                RSVP.regatta_id.in_(visible_ids),
                RSVP.status.in_(rsvp_filters),
            ).all()
        }
        upcoming = [r for r in upcoming if r.id in rsvp_regatta_ids]
        past = [r for r in past if r.id in rsvp_regatta_ids]

    return upcoming, past, skipper_id, rsvp_filters


@bp.route("/")
def index():
    if not current_user.is_authenticated:
        return render_template("login.html")

    upcoming, past = current_user.visible_regattas_split()
    upcoming, past, skipper_id, rsvp_filters = _apply_schedule_filters(
        upcoming, past, current_user
    )

    users = (
        User.query.filter(User.invite_token.is_(None)).order_by(User.display_name).all()
    )

    # Build schedule contexts for dropdown
    schedules = []
    if current_user.is_skipper:
        schedules.append(current_user)
    for skipper in current_user.skippers:
        if skipper.id != current_user.id:
            schedules.append(skipper)

    # Can user manage any regattas in current view?
    if current_user.is_skipper:
        can_manage_any = skipper_id in (0, current_user.id) or not skipper_id
    else:
        can_manage_any = False

    # Build PDF URL with current filters
    pdf_args = {}
    if skipper_id is not None:
        pdf_args["skipper"] = skipper_id
    elif len(schedules) == 1:
        pdf_args["skipper"] = schedules[0].id
    if rsvp_filters:
        pdf_args["rsvp"] = rsvp_filters

    # Crew list for "Notify Crew" modal (skippers only)
    crew_list = []
    if current_user.is_skipper:
        crew_list = get_eligible_crew(current_user)

    # Build public schedule URL for the viewed skipper (if published)
    public_schedule_url = None
    view_skipper_id = skipper_id if skipper_id and skipper_id != 0 else None
    if not view_skipper_id and len(schedules) == 1:
        view_skipper_id = schedules[0].id
    if view_skipper_id:
        view_skipper = db.session.get(User, view_skipper_id)
        if (
            view_skipper
            and view_skipper.schedule_published
            and view_skipper.schedule_slug
        ):
            public_schedule_url = url_for(
                "regattas.public_schedule", slug=view_skipper.schedule_slug
            )

    return render_template(
        "index.html",
        upcoming=upcoming,
        past=past,
        users=users,
        schedules=schedules,
        selected_skipper=skipper_id,
        can_manage_any=can_manage_any,
        rsvp_filters=rsvp_filters,
        pdf_url=url_for("regattas.pdf", **pdf_args),
        crew_list=crew_list,
        show_calendar_banner=current_user.calendar_token is None,
        public_schedule_url=public_schedule_url,
    )


@bp.route("/schedule.pdf")
@login_required
def pdf():
    upcoming, past = current_user.visible_regattas_split()
    upcoming, past, skipper_id, _rsvp_filters = _apply_schedule_filters(
        upcoming, past, current_user
    )

    # Determine title and whether to show skipper column
    show_skipper = skipper_id == 0 or (
        skipper_id is None and not current_user.is_skipper
    )
    if skipper_id and skipper_id != 0:
        skipper = db.session.get(User, skipper_id)
        pdf_title = (
            f"{skipper.display_name}'s Race Schedule" if skipper else "Race Schedule"
        )
    elif show_skipper:
        pdf_title = "Combined Race Schedules"
    else:
        pdf_title = f"{current_user.display_name}'s Race Schedule"

    html_str = render_template(
        "pdf_schedule.html",
        upcoming=upcoming,
        past=past,
        generated_date=date.today().strftime("%B %d, %Y"),
        show_skipper=show_skipper,
        pdf_title=pdf_title,
    )
    pdf_bytes = HTML(string=html_str).write_pdf()
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "inline; filename=race-crew-schedule.pdf"
    return response


@bp.route("/schedule/<slug>")
def public_schedule(slug):
    skipper = User.query.filter_by(
        schedule_slug=slug, schedule_published=True
    ).first_or_404()
    today = date.today()
    upcoming = (
        Regatta.query.filter(
            Regatta.created_by == skipper.id, Regatta.start_date >= today
        )
        .order_by(Regatta.start_date)
        .all()
    )
    past = (
        Regatta.query.filter(
            Regatta.created_by == skipper.id, Regatta.start_date < today
        )
        .order_by(Regatta.start_date.desc())
        .all()
    )
    return render_template(
        "public_schedule.html",
        skipper=skipper,
        upcoming=upcoming,
        past=past,
        pdf_url=url_for("regattas.public_pdf", slug=slug),
    )


@bp.route("/schedule/<slug>/schedule.pdf")
def public_pdf(slug):
    skipper = User.query.filter_by(
        schedule_slug=slug, schedule_published=True
    ).first_or_404()
    today = date.today()
    upcoming = (
        Regatta.query.filter(
            Regatta.created_by == skipper.id, Regatta.start_date >= today
        )
        .order_by(Regatta.start_date)
        .all()
    )
    past = (
        Regatta.query.filter(
            Regatta.created_by == skipper.id, Regatta.start_date < today
        )
        .order_by(Regatta.start_date.desc())
        .all()
    )
    html_str = render_template(
        "pdf_schedule.html",
        upcoming=upcoming,
        past=past,
        generated_date=date.today().strftime("%B %d, %Y"),
        show_skipper=False,
        pdf_title=f"{skipper.display_name}'s Race Schedule",
    )
    pdf_bytes = HTML(string=html_str).write_pdf()
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "inline; filename=race-crew-schedule.pdf"
    return response


@bp.route("/regattas/new", methods=["GET", "POST"])
@login_required
def create():
    if not (current_user.is_admin or current_user.is_skipper):
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    if request.method == "POST":
        return _save_regatta(None)

    return render_template("regatta_form.html", regatta=None)


@bp.route("/regattas/<int:regatta_id>/edit", methods=["GET", "POST"])
@login_required
def edit(regatta_id: int):
    regatta = db.session.get(Regatta, regatta_id)
    if not regatta:
        flash("Event not found.", "error")
        return redirect(url_for("regattas.index"))

    if not can_manage_regatta(current_user, regatta):
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    if request.method == "POST":
        return _save_regatta(regatta)

    return render_template("regatta_form.html", regatta=regatta)


@bp.route("/regattas/<int:regatta_id>/delete", methods=["POST"])
@login_required
def delete(regatta_id: int):
    regatta = db.session.get(Regatta, regatta_id)
    if not regatta:
        return redirect(url_for("regattas.index"))

    if not can_manage_regatta(current_user, regatta):
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    if regatta:
        db.session.delete(regatta)
        db.session.commit()
        flash(f"Event '{regatta.name}' deleted.", "success")
    return redirect(url_for("regattas.index"))


@bp.route("/regattas/bulk-delete", methods=["POST"])
@login_required
def bulk_delete():
    if not (current_user.is_admin or current_user.is_skipper):
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    selected = request.form.getlist("selected")
    if not selected:
        flash("No events selected.", "warning")
        return redirect(url_for("regattas.index"))

    count = 0
    for regatta_id in selected:
        try:
            rid = int(regatta_id)
        except (ValueError, TypeError):
            continue
        regatta = db.session.get(Regatta, rid)
        if regatta and can_manage_regatta(current_user, regatta):
            db.session.delete(regatta)
            count += 1

    db.session.commit()
    flash(f"Deleted {count} event(s).", "success")
    return redirect(url_for("regattas.index"))


@bp.route("/regattas/notify-crew", methods=["POST"])
@login_required
def notify_crew_action():
    if not current_user.is_skipper:
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    selected_ids = request.form.getlist("selected[]")
    crew_ids = request.form.getlist("crew[]")
    message = request.form.get("message", "").strip() or None

    if not selected_ids:
        flash("No events selected.", "warning")
        return redirect(url_for("regattas.index"))

    if not crew_ids:
        flash("No crew members selected.", "warning")
        return redirect(url_for("regattas.index"))

    # Validate regattas belong to current user
    regattas = []
    for rid in selected_ids:
        try:
            regatta = db.session.get(Regatta, int(rid))
        except (ValueError, TypeError):
            continue
        if regatta and regatta.created_by == current_user.id:
            regattas.append(regatta)

    if not regattas:
        flash("No valid events selected.", "warning")
        return redirect(url_for("regattas.index"))

    # Validate crew members belong to current user's crew
    crew_members = []
    valid_crew_ids = {c.id for c in current_user.crew_members.all()}
    for cid in crew_ids:
        try:
            uid = int(cid)
        except (ValueError, TypeError):
            continue
        if uid in valid_crew_ids:
            user = db.session.get(User, uid)
            if user:
                crew_members.append(user)

    if not crew_members:
        flash("No valid crew members selected.", "warning")
        return redirect(url_for("regattas.index"))

    sent = notify_crew(regattas, crew_members, message, current_user)
    flash(
        f"Notified {sent} crew member(s) about {len(regattas)} event(s).",
        "success",
    )
    return redirect(url_for("regattas.index"))


@bp.route("/regattas/<int:regatta_id>/rsvp", methods=["POST"])
@login_required
def rsvp(regatta_id: int):
    status = request.form.get("status", "").lower()

    # Build redirect args early — used by all exit paths
    redirect_args = {}
    redirect_skipper = request.form.get("redirect_skipper")
    if redirect_skipper is not None and redirect_skipper != "":
        redirect_args["skipper"] = redirect_skipper
    redirect_rsvp = request.form.getlist("redirect_rsvp")
    if redirect_rsvp:
        redirect_args["rsvp"] = redirect_rsvp

    if not status:
        # User selected "-" — clear their RSVP
        existing = RSVP.query.filter_by(
            regatta_id=regatta_id, user_id=current_user.id
        ).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
        return redirect(url_for("regattas.index", **redirect_args))

    if status not in ("yes", "no", "maybe"):
        flash("Invalid RSVP status.", "error")
        return redirect(url_for("regattas.index", **redirect_args))

    regatta = db.session.get(Regatta, regatta_id)
    if not regatta or not can_rsvp_to_regatta(current_user, regatta):
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index", **redirect_args))

    existing = RSVP.query.filter_by(
        regatta_id=regatta_id, user_id=current_user.id
    ).first()

    if existing:
        existing.status = status
        rsvp_obj = existing
    else:
        rsvp_obj = RSVP(regatta_id=regatta_id, user_id=current_user.id, status=status)
        db.session.add(rsvp_obj)

    db.session.commit()

    try:
        notify_rsvp_to_skipper(rsvp_obj)
    except Exception:
        logger.exception("Failed to send RSVP notification for regatta %s", regatta.id)

    return redirect(url_for("regattas.index", **redirect_args))


@bp.route("/docs/<int:doc_id>")
@login_required
def download_doc(doc_id: int):
    doc = db.session.get(Document, doc_id)
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("regattas.index"))

    if doc.url:
        return redirect(doc.url)

    return redirect(storage.get_file_url(doc.stored_filename))


@bp.route("/regattas/<int:regatta_id>/upload", methods=["POST"])
@login_required
def upload_doc(regatta_id: int):
    regatta = db.session.get(Regatta, regatta_id)
    if not regatta:
        flash("Event not found.", "error")
        return redirect(url_for("regattas.index"))

    if not can_manage_regatta(current_user, regatta):
        flash("Event not found.", "error")
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

        storage.upload_file(file, stored_filename)

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
    doc = db.session.get(Document, doc_id)
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("regattas.index"))

    regatta = db.session.get(Regatta, doc.regatta_id)
    if regatta and not can_manage_regatta(current_user, regatta):
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))

    regatta_id = doc.regatta_id

    # Delete file from S3 if it's a file-based document
    if doc.stored_filename:
        storage.delete_file(doc.stored_filename)

    db.session.delete(doc)
    db.session.commit()
    flash("Document removed.", "success")
    return redirect(url_for("regattas.edit", regatta_id=regatta_id))


def _save_regatta(regatta: Regatta | None):
    name = request.form.get("name", "").strip()
    boat_class = request.form.get("boat_class", "").strip()
    location = request.form.get("location", "").strip()
    city_state = request.form.get("city_state", "").strip()
    location_url = request.form.get("location_url", "").strip()
    start_date_str = request.form.get("start_date", "")
    end_date_str = request.form.get("end_date", "")
    notes = request.form.get("notes", "").strip()
    source_url = request.form.get("source_url", "").strip()

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
    regatta.boat_class = boat_class
    regatta.location = location
    regatta.city_state = city_state or None
    if location_url:
        regatta.location_url = location_url
    else:
        # Auto-generate Google Maps search link from full location text
        maps_query = f"{location}, {city_state}" if city_state else location
        regatta.location_url = (
            f"https://www.google.com/maps/search/{quote_plus(maps_query)}"
        )
    regatta.start_date = start_date
    regatta.end_date = end_date
    regatta.notes = notes or None
    regatta.source_url = source_url or None

    db.session.commit()
    flash(f"Event '{name}' saved.", "success")
    return redirect(url_for("regattas.index"))
