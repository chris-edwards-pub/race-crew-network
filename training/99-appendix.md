# Appendix: Quick Reference

This appendix provides quick reference materials for all topics covered in
the 18-day curriculum.

# Model Reference

## Models Summary (8 + 1 Association Table)

| Model | Table | Key Fields | Day |
|-------|-------|------------|-----|
| User | users | email, is_admin, is_skipper, avatar_seed, profile_image_key, email_opt_in, notification_prefs, calendar_token | 3 |
| Regatta | regattas | name, boat_class, start_date, end_date, location, created_by | 3 |
| Document | documents | filename, doc_type, storage_key, regatta_id, uploaded_by | 3 |
| RSVP | rsvps | user_id, regatta_id, status (yes/no/maybe) | 3 |
| ImportCache | import_cache | url, year, results_json, regatta_count | 13 |
| TaskResult | task_results | id (UUID), result_type, data_json | 13 |
| NotificationLog | notification_log | notification_type, regatta_id, user_id, sent_at, trigger_date | 11 |
| SiteSetting | site_settings | key (unique), value | 15 |
| skipper_crew | skipper_crew | skipper_id, crew_id, created_at (association table) | 9 |

## User Fields

| Field | Type | Purpose | Day |
|-------|------|---------|-----|
| email | String | Login identifier, unique | 3 |
| password_hash | String | bcrypt hash | 3 |
| display_name | String | Shown in UI | 3 |
| initials | String(5) | Shown in RSVP badges | 3 |
| is_admin | Boolean | Admin role flag | 3 |
| is_skipper | Boolean | Skipper role flag | 3 |
| invite_token | String | Pending registration token | 4 |
| invited_by | Integer FK | Who invited this user | 4 |
| avatar_seed | String | Multiavatar SVG seed | 14 |
| profile_image_key | String | S3/local storage key | 8 |
| email_opt_in | Boolean | Email preference (default True) | 10 |
| notification_prefs | Text | JSON: rsvp_notification, rsvp_delivery | 11 |
| phone | String(30) | Optional phone number | 3 |
| calendar_token | String | iCal feed auth token | 12 |

# Permission Patterns Reference

## Decorators and Helpers (app/permissions.py)

| Function | Usage | Day |
|----------|-------|-----|
| `require_admin` | Decorator: redirects non-admin users | 5 |
| `require_skipper` | Decorator: redirects non-skipper/non-admin users | 5 |
| `can_manage_regatta(user, regatta)` | Returns True if user can edit/delete | 5 |
| `can_rsvp_to_regatta(user, regatta)` | Returns True if user can RSVP | 5 |

## Permission Matrix

| Action | Admin | Skipper | Crew |
|--------|-------|---------|------|
| View all schedules | Yes | Yes | Yes |
| Create/edit/delete own events | Yes | Yes | No |
| Create/edit/delete any event | Yes | No | No |
| RSVP to events | Yes | Yes | Yes |
| Manage crew | Yes | Own crew | No |
| Send notifications | Yes | Own crew | No |
| Import schedules | Yes | Own events | No |
| Admin settings | Yes | No | No |
| Impersonate users | Yes | No | No |

# Notification Types Reference

| Type | Trigger | Recipient | Day |
|------|---------|-----------|-----|
| `notify_crew` | Skipper clicks "Notify Crew" | Selected crew members | 11 |
| `rsvp_notification` | Crew RSVPs (per_rsvp mode) | Event's skipper | 11 |
| `rsvp_digest` | Daily cron (digest mode) | Skipper with digest pref | 11 |
| `crew_joined` | Crew completes registration | Inviting skipper | 11 |
| `rsvp_reminder` | 14 days before event | Crew who haven't RSVPed | 11 |
| `coming_up_reminder` | 3 days before event | Crew who RSVPed yes/maybe | 11 |

# SiteSetting Keys Reference

| Key | Used By | Default | Day |
|-----|---------|---------|-----|
| `ga_measurement_id` | Google Analytics injection | "" (disabled) | 15 |
| `ses_sender` | SES sender email address | "" | 10 |
| `ses_sender_to` | Default test email recipient | "" | 15 |
| `ses_region` | SES AWS region | config["AWS_REGION"] | 10 |
| `reminder_rsvp_days_before` | RSVP reminder window | "14" | 11 |
| `reminder_upcoming_days_before` | Coming-up reminder window | "3" | 11 |
| `reminder_api_token` | Reminder API auth token | "" | 15 |

# Template Filters Reference

| Filter | Usage | Purpose | Day |
|--------|-------|---------|-----|
| `avatar_svg` | `{{ user\|avatar_svg(20) }}` | Render Multiavatar SVG | 14 |
| `user_icon` | `{{ user\|user_icon(28) }}` | Photo with SVG fallback | 14 |
| `sort_rsvps` | `{{ rsvps\|sort_rsvps }}` | Sort: yes → no → maybe | 14 |
| `regatta_days` | `{{ start\|regatta_days(end) }}` | "Sat", "Sat & Sun", "Fri thru Sun" | 14 |

# Email Templates

| Template | Used By | Description |
|----------|---------|-------------|
| `email/notify_crew.html/.txt` | `notify_crew()` | Crew notification with event list |
| `email/rsvp_notification.html/.txt` | `notify_rsvp_to_skipper()` | Per-RSVP alert to skipper |
| `email/rsvp_digest.html/.txt` | `send_rsvp_digests()` | Daily RSVP summary for skipper |
| `email/rsvp_reminder.html/.txt` | `send_rsvp_reminders()` | "Please RSVP" reminder |
| `email/coming_up_reminder.html/.txt` | `send_coming_up_reminders()` | "Event in 3 days" reminder |
| `email/crew_digest.html/.txt` | `send_crew_digests()` | Daily digest for crew |
| `email/invite_crew.html/.txt` | `invite_crew()` | Crew invitation email |

# Flask Routing Reference

## Basic Routes
```python
@app.route("/")
def index():
    return "Hello"

@app.route("/about")
def about():
    return render_template("about.html")
```

## HTTP Methods
```python
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Process form
        pass
    return render_template("login.html")
```

## URL Parameters
```python
@app.route("/user/<int:user_id>")
def user_profile(user_id: int):
    user = db.session.get(User, user_id)
    return render_template("profile.html", user=user)

@app.route("/search")
def search():
    query = request.args.get("q", "")  # /search?q=flask
```

## Redirects and url_for
```python
from flask import redirect, url_for

return redirect(url_for("auth.profile"))
return redirect(url_for("regattas.edit", regatta_id=regatta.id))
```

## Flash Messages
```python
flash("Operation successful!", "success")   # green
flash("An error occurred.", "error")         # red (maps to alert-danger)
flash("Please note...", "warning")           # yellow
```

# SQLAlchemy Query Reference

## Basic Queries
```python
# Get all
users = User.query.all()

# Get by primary key
user = db.session.get(User, 1)

# Filter
users = User.query.filter_by(is_admin=True).all()
users = User.query.filter(User.email.like("%@example.com")).all()

# Order and limit
users = User.query.order_by(User.display_name).limit(10).all()

# Count
count = User.query.filter_by(is_admin=True).count()
```

## Filtering
```python
# IN list
User.query.filter(User.id.in_([1, 2, 3]))

# IS NULL / IS NOT NULL
User.query.filter(User.invite_token.is_(None))
User.query.filter(User.invite_token.isnot(None))

# AND (chain filters)
User.query.filter_by(is_admin=True).filter_by(is_skipper=True)

# OR
from sqlalchemy import or_
User.query.filter(or_(User.is_admin == True, User.is_skipper == True))
```

## Create, Update, Delete
```python
# Create
user = User(email="test@example.com", display_name="Test")
db.session.add(user)
db.session.commit()

# Update
user.display_name = "New Name"
db.session.commit()

# Delete
db.session.delete(user)
db.session.commit()
```

# Docker Compose Commands

```bash
# Start services
docker compose up --build          # Build and start
docker compose up -d               # Start in background

# Stop services
docker compose down                # Stop (keep volumes)
docker compose down -v             # Stop and delete volumes

# Logs
docker compose logs                # All logs
docker compose logs -f web         # Follow web logs

# Execute in container
docker compose exec web flask create-admin
docker compose exec web flask db current
docker compose exec db mysql -u racecrew -p

# Status
docker compose ps                  # Running containers
```

# Flask CLI Commands

```bash
# Custom commands (this app)
flask init-admin                   # Create admin from env vars
flask create-admin                 # Interactive admin creation
flask send-reminders               # Run all scheduled reminders

# Migration commands
flask db upgrade                   # Apply pending migrations
flask db migrate -m "message"      # Generate migration from model changes
flask db downgrade -1              # Undo last migration
flask db current                   # Show current version
flask db history                   # Show migration history
```

# Terraform Commands

```bash
cd terraform/

terraform init                     # Download providers
terraform fmt -check               # Check formatting
terraform validate                 # Validate config
terraform plan                     # Preview changes
terraform apply                    # Apply changes
terraform destroy                  # Tear down all resources
```

# Trivy Commands

```bash
# Scan a local image
trivy image ghcr.io/chris-edwards-pub/race-crew-network:latest

# Scan with severity filter
trivy image --severity CRITICAL,HIGH --ignore-unfixed \
  ghcr.io/chris-edwards-pub/race-crew-network:latest

# Output as SARIF
trivy image --format sarif --output results.sarif \
  ghcr.io/chris-edwards-pub/race-crew-network:latest
```

# Troubleshooting Guide

## Can't Connect to Localhost
1. Check containers: `docker compose ps`
2. Check logs: `docker compose logs`
3. Verify port 80 isn't in use: `lsof -i :80`
4. Restart: `docker compose restart`

## Database Connection Errors
1. Check db health: `docker compose ps` (should show "healthy")
2. Verify DATABASE_URL in .env matches MySQL credentials
3. Check db logs: `docker compose logs db`
4. Fresh start: `docker compose down -v && docker compose up --build`

## Migration Errors
1. Check current version: `docker compose exec web flask db current`
2. Check history: `docker compose exec web flask db history`
3. If stuck, fresh start: `docker compose down -v && docker compose up --build`

## Session Cookie Not Persisting
1. Check SECRET_KEY is set in .env
2. Verify: `docker compose exec web env | grep SECRET`
3. Generate new key: `python3 -c "import secrets; print(secrets.token_hex(32))"`

## Static Files Not Loading
1. Check browser console for 404 errors
2. Verify file paths in templates use `url_for('static', filename=...)`
3. Clear browser cache
4. Check container logs for errors

# Security Best Practices

## Passwords
- Use bcrypt for hashing (implemented)
- Generate strong SECRET_KEY (64+ hex chars)
- Never hardcode secrets in source code
- Use environment variables or GitHub Secrets

## File Uploads
- Validate file extensions before accepting
- Use UUID filenames to prevent collisions
- Set MAX_CONTENT_LENGTH (10 MB default)
- Use path traversal protection (secure_filename)

## Network
- SSRF protection for all URL fetching (_is_private_ip)
- CSRF tokens on all forms (@csrf.exempt only for webhooks)
- HMAC tokens for stateless verification
- Timing-safe comparison (hmac.compare_digest)
- Request timeouts on outbound HTTP calls

## Infrastructure
- Trivy scanning gates deployment (CRITICAL/HIGH = block)
- Dedicated IAM users with minimal permissions
- Email authentication: DKIM + SPF + DMARC
- Secrets in GitHub Secrets, not in code

# Further Reading

## Flask
- Official Documentation: https://flask.palletsprojects.com/
- Flask Mega-Tutorial: https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world

## SQLAlchemy
- Official Documentation: https://docs.sqlalchemy.org/
- ORM Tutorial: https://docs.sqlalchemy.org/orm/tutorial.html

## Docker
- Official Documentation: https://docs.docker.com/
- Docker Compose: https://docs.docker.com/compose/

## AWS
- Lightsail Containers: https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-container-services.html
- SES Developer Guide: https://docs.aws.amazon.com/ses/latest/dg/

## Security
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- Flask Security: https://flask.palletsprojects.com/security/

# End of Appendix

This appendix covers the complete Race Crew Network v0.61.0 application.
Return to it whenever you need a quick reference for any topic covered in
the 18-day curriculum.
