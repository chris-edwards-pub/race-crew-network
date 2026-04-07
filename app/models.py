import json
import secrets
from datetime import date, datetime, timezone

import bcrypt
from flask_login import UserMixin

from app import db, login_manager

# Self-referential many-to-many: skipper <-> crew
skipper_crew = db.Table(
    "skipper_crew",
    db.Column("skipper_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("crew_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column(
        "created_at",
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    ),
)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    initials = db.Column(db.String(5), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_skipper = db.Column(db.Boolean, default=False, nullable=False)
    invited_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Registration invite token (null after registration is complete)
    invite_token = db.Column(db.String(64), unique=True, nullable=True)
    # Token for iCal subscription feed (generated on first request)
    calendar_token = db.Column(db.String(64), unique=True, nullable=True)
    # Password reset token and expiry
    reset_token = db.Column(db.String(64), unique=True, nullable=True)
    reset_token_expires_at = db.Column(db.DateTime, nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    yacht_club = db.Column(db.String(100), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    email_opt_in = db.Column(db.Boolean, default=True, nullable=False)
    profile_image_key = db.Column(db.String(255), nullable=True)
    avatar_seed = db.Column(db.String(100), nullable=True)
    schedule_slug = db.Column(db.String(100), unique=True, nullable=True)
    schedule_published = db.Column(db.Boolean, default=True, nullable=False)
    notification_prefs = db.Column(db.Text, nullable=True)

    rsvps = db.relationship("RSVP", backref="user", lazy="dynamic")
    documents = db.relationship("Document", backref="uploaded_by_user", lazy="dynamic")

    # Skipper -> their crew members
    crew_members = db.relationship(
        "User",
        secondary=skipper_crew,
        primaryjoin=id == skipper_crew.c.skipper_id,
        secondaryjoin=id == skipper_crew.c.crew_id,
        backref="skippers",
        lazy="dynamic",
    )

    # Who invited this user
    inviter = db.relationship("User", remote_side=[id], foreign_keys=[invited_by])

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(
            password.encode("utf-8"), self.password_hash.encode("utf-8")
        )

    @staticmethod
    def generate_avatar_seed() -> str:
        """Generate a unique random seed for Multiavatar."""
        return f"avatar-{secrets.token_hex(12)}"

    @property
    def avatar_key(self) -> str:
        """Return the seed used for Multiavatar generation."""
        return self.avatar_seed or self.email

    @property
    def is_crew(self) -> bool:
        """True if this user is crew for at least one skipper."""
        return len(self.skippers) > 0

    def generate_schedule_slug(self) -> str:
        """Generate a URL slug from display_name, ensuring uniqueness."""
        import re

        base = re.sub(r"[^a-z0-9]+", "-", self.display_name.lower()).strip("-")
        slug = base
        counter = 1
        while User.query.filter(User.schedule_slug == slug, User.id != self.id).first():
            slug = f"{base}-{counter}"
            counter += 1
        return slug

    @property
    def notification_preferences(self) -> dict:
        """Return notification preferences with defaults."""
        defaults = {
            "rsvp_notification": True,
            "rsvp_delivery": "per_rsvp",
        }
        if self.notification_prefs:
            try:
                stored = json.loads(self.notification_prefs)
                defaults.update(stored)
            except (json.JSONDecodeError, TypeError):
                pass
        return defaults

    def visible_regattas(self):
        """Return a query of regattas this user can see.

        - Skipper: their own regattas
        - Crew: regattas from their skippers
        - Skipper+Crew: union of own + skippers' regattas
        """
        owner_ids = set()
        if self.is_skipper:
            owner_ids.add(self.id)
        for skipper in self.skippers:
            owner_ids.add(skipper.id)

        if not owner_ids:
            # User has no role — return empty query
            return Regatta.query.filter(Regatta.id < 0)

        return Regatta.query.filter(Regatta.created_by.in_(owner_ids))

    def visible_regattas_split(self):
        """Return (upcoming, past) tuples of visible regattas."""
        today = date.today()
        base = self.visible_regattas()
        upcoming = (
            base.filter(Regatta.start_date >= today).order_by(Regatta.start_date).all()
        )
        past = (
            base.filter(Regatta.start_date < today)
            .order_by(Regatta.start_date.desc())
            .all()
        )
        return upcoming, past


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


class Regatta(db.Model):
    __tablename__ = "regattas"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    boat_class = db.Column(db.String(100), nullable=False, default="")
    location = db.Column(db.String(200), nullable=False)
    city_state = db.Column(db.String(100), nullable=True)
    location_url = db.Column(db.String(500), nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    source_url = db.Column(db.String(500), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    documents = db.relationship(
        "Document", backref="regatta", lazy="dynamic", cascade="all, delete-orphan"
    )
    rsvps = db.relationship(
        "RSVP", backref="regatta", lazy="dynamic", cascade="all, delete-orphan"
    )
    creator = db.relationship(
        "User", backref="created_regattas", foreign_keys=[created_by]
    )

    @property
    def full_location(self) -> str:
        if self.city_state:
            return f"{self.location}, {self.city_state}"
        return self.location


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    regatta_id = db.Column(db.Integer, db.ForeignKey("regattas.id"), nullable=False)
    doc_type = db.Column(db.String(20), nullable=False)  # NOR, SI, WWW
    original_filename = db.Column(db.String(255), nullable=True)
    stored_filename = db.Column(db.String(255), nullable=True)
    url = db.Column(db.String(500), nullable=True)  # External URL (alternative to file)
    uploaded_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)


class RSVP(db.Model):
    __tablename__ = "rsvps"

    id = db.Column(db.Integer, primary_key=True)
    regatta_id = db.Column(db.Integer, db.ForeignKey("regattas.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(10), nullable=False)  # yes, no, maybe
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint("regatta_id", "user_id", name="uq_rsvp_regatta_user"),
    )


class ImportCache(db.Model):
    __tablename__ = "import_cache"

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False, unique=True)
    year = db.Column(db.Integer, nullable=False)
    results_json = db.Column(db.Text, nullable=False)
    regatta_count = db.Column(db.Integer, nullable=False, default=0)
    extracted_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class TaskResult(db.Model):
    __tablename__ = "task_results"

    id = db.Column(db.String(36), primary_key=True)  # UUID
    result_type = db.Column(
        db.String(20), nullable=False
    )  # "extraction" or "discovery"
    data_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class NotificationLog(db.Model):
    __tablename__ = "notification_log"

    id = db.Column(db.Integer, primary_key=True)
    notification_type = db.Column(db.String(50), nullable=False)
    regatta_id = db.Column(db.Integer, db.ForeignKey("regattas.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    sent_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    trigger_date = db.Column(db.Date, default=date.today, nullable=False)

    regatta = db.relationship("Regatta", backref="notification_logs")
    user = db.relationship("User", backref="notification_logs")

    __table_args__ = (
        db.Index("ix_notification_type_regatta", "notification_type", "regatta_id"),
    )


class EmailQueue(db.Model):
    __tablename__ = "email_queue"

    id = db.Column(db.Integer, primary_key=True)
    to_email = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(500), nullable=False)
    body_text = db.Column(db.Text, nullable=False)
    body_html = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="pending", nullable=False)
    queued_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    sent_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)


class AIUsageLog(db.Model):
    __tablename__ = "ai_usage_log"

    id = db.Column(db.Integer, primary_key=True)
    function_name = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    input_tokens = db.Column(db.Integer, nullable=False)
    output_tokens = db.Column(db.Integer, nullable=False)
    cost_usd = db.Column(db.Float, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SiteSetting(db.Model):
    __tablename__ = "site_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False, unique=True, index=True)
    value = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
