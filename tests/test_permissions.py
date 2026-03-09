"""Tests for app.permissions."""

from datetime import date

from app.models import Regatta
from app.permissions import can_manage_regatta, can_rsvp_to_regatta


class TestCanManageRegatta:
    def test_admin_can_manage_any(self, app, db, admin_user, skipper_user):
        regatta = Regatta(
            name="Skipper Regatta",
            location="Test YC",
            start_date=date(2026, 7, 1),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.commit()
        assert can_manage_regatta(admin_user, regatta) is True

    def test_skipper_can_manage_own(self, app, db, skipper_user):
        regatta = Regatta(
            name="My Regatta",
            location="Test YC",
            start_date=date(2026, 7, 1),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.commit()
        assert can_manage_regatta(skipper_user, regatta) is True

    def test_skipper_cannot_manage_others(self, app, db, admin_user, skipper_user):
        regatta = Regatta(
            name="Admin Regatta",
            location="Test YC",
            start_date=date(2026, 7, 1),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()
        assert can_manage_regatta(skipper_user, regatta) is False

    def test_crew_cannot_manage(self, app, db, skipper_user, crew_user):
        regatta = Regatta(
            name="Skipper Regatta",
            location="Test YC",
            start_date=date(2026, 7, 1),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.commit()
        assert can_manage_regatta(crew_user, regatta) is False


class TestCanRsvpToRegatta:
    def test_admin_can_rsvp_any(self, app, db, admin_user, skipper_user):
        regatta = Regatta(
            name="Skipper Regatta",
            location="Test YC",
            start_date=date(2026, 7, 1),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.commit()
        assert can_rsvp_to_regatta(admin_user, regatta) is True

    def test_owner_can_rsvp(self, app, db, skipper_user):
        regatta = Regatta(
            name="My Regatta",
            location="Test YC",
            start_date=date(2026, 7, 1),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.commit()
        assert can_rsvp_to_regatta(skipper_user, regatta) is True

    def test_crew_can_rsvp_to_skippers_regatta(self, app, db, skipper_user, crew_user):
        regatta = Regatta(
            name="Skipper Regatta",
            location="Test YC",
            start_date=date(2026, 7, 1),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.commit()
        assert can_rsvp_to_regatta(crew_user, regatta) is True

    def test_crew_cannot_rsvp_to_unrelated_regatta(
        self, app, db, admin_user, crew_user
    ):
        regatta = Regatta(
            name="Admin Regatta",
            location="Test YC",
            start_date=date(2026, 7, 1),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()
        assert can_rsvp_to_regatta(crew_user, regatta) is False
