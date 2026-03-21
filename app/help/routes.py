import time

from flask import current_app, redirect, render_template, request, url_for

from app.help import bp


@bp.route("/help")
def index():
    """Render the public help page."""
    contact_status = request.args.get("contact")
    return render_template(
        "help/index.html",
        form_timestamp=int(time.time()),
        contact_status=contact_status,
    )


@bp.route("/help/contact", methods=["POST"])
def contact():
    """Handle contact form submission with spam protection."""
    # Honeypot check — bots fill the hidden field; humans never see it
    if request.form.get("website"):
        return redirect(url_for("help.index", contact="sent", _anchor="contact"))

    # Timestamp check — reject submissions faster than 3 seconds
    try:
        form_ts = int(request.form.get("form_timestamp", 0))
        if time.time() - form_ts < 3:
            return redirect(url_for("help.index", contact="sent", _anchor="contact"))
    except (ValueError, TypeError):
        pass

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()

    if not name or not email or not message:
        return redirect(url_for("help.index", contact="missing", _anchor="contact"))

    # Send via SES to admin
    try:
        from app.admin.email_service import _send_via_ses, load_email_settings

        settings = load_email_settings()
        recipient = settings["ses_sender_to"] or settings["ses_sender"]
        if not recipient:
            raise ValueError("No admin email configured.")

        subject = f"[Contact Form] Message from {name}"
        body_text = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"
        body_html = (
            f"<p><strong>Name:</strong> {name}</p>"
            f"<p><strong>Email:</strong> {email}</p>"
            f"<hr><p>{message}</p>"
        )

        _send_via_ses(recipient, subject, body_text, body_html, reply_to=email)

        return redirect(url_for("help.index", contact="sent", _anchor="contact"))
    except Exception:
        current_app.logger.exception("Contact form email failed")
        return redirect(url_for("help.index", contact="error", _anchor="contact"))
