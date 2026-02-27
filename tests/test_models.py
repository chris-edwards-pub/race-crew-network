"""Tests for app.models."""

from datetime import date

import pytest

from app.models import RSVP, Document, Regatta, User


class TestUserModel:
    def test_set_and_check_password(self, app, db):
        user = User(
            email="test@test.com",
            display_name="Test User",
            initials="TU",
        )
        user.set_password("secret123")
        db.session.add(user)
        db.session.commit()

        assert user.check_password("secret123") is True
        assert user.check_password("wrong") is False

    def test_password_is_hashed(self, app, db):
        user = User(
            email="test2@test.com",
            display_name="Test",
            initials="T2",
        )
        user.set_password("mypassword")
        assert user.password_hash != "mypassword"
        assert len(user.password_hash) > 20


class TestRegattaModel:
    def test_create_regatta(self, app, db, admin_user):
        regatta = Regatta(
            name="Test Regatta",
            location="Test Yacht Club",
            start_date=date(2026, 6, 15),
            end_date=date(2026, 6, 16),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        assert regatta.id is not None
        assert regatta.name == "Test Regatta"

    def test_boat_class_defaults_to_tbd(self, app, db, admin_user):
        regatta = Regatta(
            name="Default Class Test",
            location="Test YC",
            start_date=date(2026, 6, 20),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        assert regatta.boat_class == "TBD"

    def test_boat_class_explicit_value(self, app, db, admin_user):
        regatta = Regatta(
            name="Thistle Regatta",
            boat_class="Thistle",
            location="Test YC",
            start_date=date(2026, 6, 21),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        assert regatta.boat_class == "Thistle"

    def test_regatta_cascade_delete_documents(self, app, db, admin_user):
        regatta = Regatta(
            name="Cascade Test",
            location="Test",
            start_date=date(2026, 7, 1),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.flush()

        doc = Document(
            regatta_id=regatta.id,
            doc_type="NOR",
            url="https://example.com/nor.pdf",
            uploaded_by=admin_user.id,
        )
        db.session.add(doc)
        db.session.commit()

        regatta_id = regatta.id
        db.session.delete(regatta)
        db.session.commit()

        assert Document.query.filter_by(regatta_id=regatta_id).count() == 0

    def test_regatta_cascade_delete_rsvps(self, app, db, admin_user):
        regatta = Regatta(
            name="RSVP Cascade",
            location="Test",
            start_date=date(2026, 7, 1),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.flush()

        rsvp = RSVP(
            regatta_id=regatta.id,
            user_id=admin_user.id,
            status="yes",
        )
        db.session.add(rsvp)
        db.session.commit()

        regatta_id = regatta.id
        db.session.delete(regatta)
        db.session.commit()

        assert RSVP.query.filter_by(regatta_id=regatta_id).count() == 0


class TestDocumentModel:
    def test_url_based_document(self, app, db, admin_user):
        regatta = Regatta(
            name="Doc Test",
            location="Test",
            start_date=date(2026, 8, 1),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.flush()

        doc = Document(
            regatta_id=regatta.id,
            doc_type="WWW",
            url="https://example.com/regatta",
            uploaded_by=admin_user.id,
        )
        db.session.add(doc)
        db.session.commit()

        assert doc.id is not None
        assert doc.url == "https://example.com/regatta"
        assert doc.stored_filename is None
