"""Tests for schedule page filter enhancements: dropdown labels, skipper column, RSVP filter."""

from datetime import date, timedelta

from app.models import RSVP, Regatta, User


def _create_regatta(db, name, created_by, days_offset=7):
    """Helper to create a regatta with a future start date."""
    r = Regatta(
        name=name,
        location="Test Location",
        start_date=date.today() + timedelta(days=days_offset),
        created_by=created_by,
    )
    db.session.add(r)
    db.session.commit()
    return r


class TestDropdownLabels:
    """Dropdown shows "'s Schedule" suffix for other skippers."""

    def test_other_skipper_shows_schedule_suffix(
        self, app, db, logged_in_client, admin_user
    ):
        # Create another skipper so dropdown appears (admin + other = 2 schedules)
        other = User(
            email="skipper2@test.com",
            display_name="John Smith",
            initials="JS",
            is_skipper=True,
        )
        other.set_password("password")
        db.session.add(other)
        db.session.commit()

        resp = logged_in_client.get("/")
        assert (
            b"John Smith&#39;s Schedule" in resp.data
            or b"John Smith's Schedule" in resp.data
        )

    def test_my_schedule_label_unchanged(self, app, db, logged_in_client, admin_user):
        other = User(
            email="skipper2@test.com",
            display_name="Other Skipper",
            initials="OS",
            is_skipper=True,
        )
        other.set_password("password")
        db.session.add(other)
        db.session.commit()

        resp = logged_in_client.get("/")
        assert b"My Schedule" in resp.data

    def test_all_schedules_label_unchanged(self, app, db, logged_in_client, admin_user):
        other = User(
            email="skipper2@test.com",
            display_name="Other Skipper",
            initials="OS",
            is_skipper=True,
        )
        other.set_password("password")
        db.session.add(other)
        db.session.commit()

        resp = logged_in_client.get("/?skipper=0")
        assert b"All Schedules" in resp.data


class TestSkipperColumn:
    """All Schedules view includes Skipper column; single skipper hides it."""

    def test_all_schedules_shows_skipper_column(
        self, app, db, logged_in_client, admin_user
    ):
        other = User(
            email="skipper2@test.com",
            display_name="Jane Doe",
            initials="JD",
            is_skipper=True,
        )
        other.set_password("password")
        db.session.add(other)
        db.session.commit()

        _create_regatta(db, "Regatta A", admin_user.id)
        _create_regatta(db, "Regatta B", other.id)

        resp = logged_in_client.get("/?skipper=0")
        assert b"<th>Skipper</th>" in resp.data
        assert b"Jane Doe" in resp.data
        assert b"Admin" in resp.data

    def test_single_skipper_hides_skipper_column(
        self, app, db, logged_in_client, admin_user
    ):
        _create_regatta(db, "Regatta A", admin_user.id)

        resp = logged_in_client.get(f"/?skipper={admin_user.id}")
        assert b"<th>Skipper</th>" not in resp.data

    def test_mobile_shows_skipper_in_all_schedules(
        self, app, db, logged_in_client, admin_user
    ):
        other = User(
            email="skipper2@test.com",
            display_name="Jane Doe",
            initials="JD",
            is_skipper=True,
        )
        other.set_password("password")
        db.session.add(other)
        db.session.commit()

        _create_regatta(db, "Regatta A", other.id)

        resp = logged_in_client.get("/?skipper=0")
        assert b"Skipper: Jane Doe" in resp.data


class TestRSVPFilter:
    """RSVP toggle buttons filter regattas by attendance status."""

    def test_filter_yes_shows_only_yes_regattas(
        self, app, db, logged_in_client, admin_user
    ):
        r1 = _create_regatta(db, "Yes Regatta", admin_user.id, days_offset=10)
        r2 = _create_regatta(db, "No Regatta", admin_user.id, days_offset=11)

        db.session.add(RSVP(regatta_id=r1.id, user_id=admin_user.id, status="yes"))
        db.session.add(RSVP(regatta_id=r2.id, user_id=admin_user.id, status="no"))
        db.session.commit()

        resp = logged_in_client.get("/?rsvp=yes")
        assert b"Yes Regatta" in resp.data
        assert b"No Regatta" not in resp.data

    def test_filter_no_shows_only_no_regattas(
        self, app, db, logged_in_client, admin_user
    ):
        r1 = _create_regatta(db, "Yes Regatta", admin_user.id, days_offset=10)
        r2 = _create_regatta(db, "No Regatta", admin_user.id, days_offset=11)

        db.session.add(RSVP(regatta_id=r1.id, user_id=admin_user.id, status="yes"))
        db.session.add(RSVP(regatta_id=r2.id, user_id=admin_user.id, status="no"))
        db.session.commit()

        resp = logged_in_client.get("/?rsvp=no")
        assert b"No Regatta" in resp.data
        assert b"Yes Regatta" not in resp.data

    def test_combined_yes_maybe_shows_both(self, app, db, logged_in_client, admin_user):
        r1 = _create_regatta(db, "Yes Regatta", admin_user.id, days_offset=10)
        r2 = _create_regatta(db, "Maybe Regatta", admin_user.id, days_offset=11)
        r3 = _create_regatta(db, "No Regatta", admin_user.id, days_offset=12)

        db.session.add(RSVP(regatta_id=r1.id, user_id=admin_user.id, status="yes"))
        db.session.add(RSVP(regatta_id=r2.id, user_id=admin_user.id, status="maybe"))
        db.session.add(RSVP(regatta_id=r3.id, user_id=admin_user.id, status="no"))
        db.session.commit()

        resp = logged_in_client.get("/?rsvp=yes&rsvp=maybe")
        assert b"Yes Regatta" in resp.data
        assert b"Maybe Regatta" in resp.data
        assert b"No Regatta" not in resp.data

    def test_all_three_checked_shows_everything(
        self, app, db, logged_in_client, admin_user
    ):
        r1 = _create_regatta(db, "Yes Regatta", admin_user.id, days_offset=10)
        _create_regatta(db, "Unrsvpd Regatta", admin_user.id, days_offset=11)

        db.session.add(RSVP(regatta_id=r1.id, user_id=admin_user.id, status="yes"))
        db.session.commit()

        resp = logged_in_client.get("/?rsvp=yes&rsvp=no&rsvp=maybe")
        assert b"Yes Regatta" in resp.data
        assert b"Unrsvpd Regatta" in resp.data

    def test_no_filter_shows_everything(self, app, db, logged_in_client, admin_user):
        r1 = _create_regatta(db, "Yes Regatta", admin_user.id, days_offset=10)
        _create_regatta(db, "Unrsvpd Regatta", admin_user.id, days_offset=11)

        db.session.add(RSVP(regatta_id=r1.id, user_id=admin_user.id, status="yes"))
        db.session.commit()

        resp = logged_in_client.get("/")
        assert b"Yes Regatta" in resp.data
        assert b"Unrsvpd Regatta" in resp.data

    def test_combined_skipper_and_rsvp_filter(
        self, app, db, logged_in_client, admin_user
    ):
        other = User(
            email="skipper2@test.com",
            display_name="Other Skipper",
            initials="OS",
            is_skipper=True,
        )
        other.set_password("password")
        db.session.add(other)
        db.session.commit()

        r1 = _create_regatta(db, "Admin Yes", admin_user.id, days_offset=10)
        r2 = _create_regatta(db, "Other Yes", other.id, days_offset=11)

        db.session.add(RSVP(regatta_id=r1.id, user_id=admin_user.id, status="yes"))
        db.session.add(RSVP(regatta_id=r2.id, user_id=admin_user.id, status="yes"))
        db.session.commit()

        # Filter by admin's schedule + RSVP yes
        resp = logged_in_client.get(f"/?skipper={admin_user.id}&rsvp=yes")
        assert b"Admin Yes" in resp.data
        assert b"Other Yes" not in resp.data


class TestRSVPToggleButtons:
    """Toggle buttons are present with correct checked state."""

    def test_toggle_buttons_present(self, app, db, logged_in_client, admin_user):
        resp = logged_in_client.get("/")
        assert b'id="rsvp-yes"' in resp.data
        assert b'id="rsvp-maybe"' in resp.data
        assert b'id="rsvp-no"' in resp.data

    def test_default_all_checked(self, app, db, logged_in_client, admin_user):
        resp = logged_in_client.get("/")
        html = resp.data.decode()
        # All three should be checked by default (no rsvp_filters)
        assert 'id="rsvp-yes" checked' in html
        assert 'id="rsvp-maybe" checked' in html
        assert 'id="rsvp-no" checked' in html

    def test_filtered_state_reflected(self, app, db, logged_in_client, admin_user):
        resp = logged_in_client.get("/?rsvp=yes")
        html = resp.data.decode()
        assert 'id="rsvp-yes" checked' in html
        # Maybe and No should NOT be checked
        assert 'id="rsvp-maybe" checked' not in html
        assert 'id="rsvp-no" checked' not in html


class TestRSVPFilterStatePreservation:
    """RSVP submission preserves filter state in redirect."""

    def test_rsvp_preserves_skipper_filter(self, app, db, logged_in_client, admin_user):
        r = _create_regatta(db, "Test Regatta", admin_user.id)

        resp = logged_in_client.post(
            f"/regattas/{r.id}/rsvp",
            data={
                "status": "yes",
                "redirect_skipper": str(admin_user.id),
            },
        )
        assert resp.status_code == 302
        location = resp.headers["Location"]
        assert f"skipper={admin_user.id}" in location

    def test_rsvp_preserves_rsvp_filter(self, app, db, logged_in_client, admin_user):
        r = _create_regatta(db, "Test Regatta", admin_user.id)

        resp = logged_in_client.post(
            f"/regattas/{r.id}/rsvp",
            data={
                "status": "yes",
                "redirect_rsvp": ["yes", "maybe"],
            },
        )
        assert resp.status_code == 302
        location = resp.headers["Location"]
        assert "rsvp=yes" in location
        assert "rsvp=maybe" in location

    def test_rsvp_preserves_combined_filters(
        self, app, db, logged_in_client, admin_user
    ):
        r = _create_regatta(db, "Test Regatta", admin_user.id)

        resp = logged_in_client.post(
            f"/regattas/{r.id}/rsvp",
            data={
                "status": "yes",
                "redirect_skipper": "0",
                "redirect_rsvp": ["yes"],
            },
        )
        assert resp.status_code == 302
        location = resp.headers["Location"]
        assert "skipper=0" in location
        assert "rsvp=yes" in location
