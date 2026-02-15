from datetime import datetime, timezone

import bcrypt
from flask_login import UserMixin

from app import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    initials = db.Column(db.String(5), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Registration invite token (null after registration is complete)
    invite_token = db.Column(db.String(64), unique=True, nullable=True)
    # Token for iCal subscription feed (generated on first request)
    calendar_token = db.Column(db.String(64), unique=True, nullable=True)

    rsvps = db.relationship("RSVP", backref="user", lazy="dynamic")
    documents = db.relationship("Document", backref="uploaded_by_user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(
            password.encode("utf-8"), self.password_hash.encode("utf-8")
        )


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


class Regatta(db.Model):
    __tablename__ = "regattas"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    location_url = db.Column(db.String(500), nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
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
    creator = db.relationship("User", backref="created_regattas", foreign_keys=[created_by])


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    regatta_id = db.Column(
        db.Integer, db.ForeignKey("regattas.id"), nullable=False
    )
    doc_type = db.Column(db.String(20), nullable=False)  # NOR, SI, other
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)


class RSVP(db.Model):
    __tablename__ = "rsvps"

    id = db.Column(db.Integer, primary_key=True)
    regatta_id = db.Column(
        db.Integer, db.ForeignKey("regattas.id"), nullable=False
    )
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
