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


def _create_regatta_on(db, name, created_by, start_date):
    """Helper to create a regatta on an explicit date."""
    r = Regatta(
        name=name,
        location="Test Location",
        start_date=start_date,
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
        # Create another skipper and link admin as crew so dropdown appears
        other = User(
            email="skipper2@test.com",
            display_name="John Smith",
            initials="JS",
            is_skipper=True,
        )
        other.set_password("password")
        db.session.add(other)
        db.session.flush()
        other.crew_members.append(admin_user)
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
        db.session.flush()
        other.crew_members.append(admin_user)
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
        db.session.flush()
        other.crew_members.append(admin_user)
        db.session.commit()

        resp = logged_in_client.get("/?skipper=0")
        assert b"Combined Schedules" in resp.data


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
        db.session.flush()
        other.crew_members.append(admin_user)
        db.session.commit()

        _create_regatta(db, "Regatta A", admin_user.id)
        _create_regatta(db, "Regatta B", other.id)

        resp = logged_in_client.get("/?skipper=0")
        assert b"<th>Skipper</th>" in resp.data
        assert b"Jane Doe" in resp.data
        assert b"Admin" in resp.data

    def test_skipper_name_links_to_profile(self, app, db, logged_in_client, admin_user):
        other = User(
            email="skipper2@test.com",
            display_name="Jane Doe",
            initials="JD",
            is_skipper=True,
        )
        other.set_password("password")
        db.session.add(other)
        db.session.flush()
        other.crew_members.append(admin_user)
        db.session.commit()

        _create_regatta(db, "Regatta A", other.id)

        resp = logged_in_client.get("/?skipper=0")
        html = resp.data.decode()
        assert f'/crew/{other.id}"' in html
        assert "Jane Doe</a>" in html

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
        db.session.flush()
        other.crew_members.append(admin_user)
        db.session.commit()

        _create_regatta(db, "Regatta A", other.id)

        resp = logged_in_client.get("/?skipper=0")
        html = resp.data.decode()
        assert "Skipper:" in html
        assert "Jane Doe</a>" in html


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

    def test_filter_yes_includes_regatta_with_mixed_rsvps(
        self, app, db, logged_in_client, admin_user
    ):
        """A regatta with a Yes AND a No RSVP should appear when filtering Yes."""
        crew = User(
            email="crew@test.com",
            display_name="Crew",
            initials="CR",
        )
        crew.set_password("password")
        db.session.add(crew)
        db.session.commit()

        r1 = _create_regatta(db, "Mixed Regatta", admin_user.id, days_offset=10)
        r2 = _create_regatta(db, "Only No Regatta", admin_user.id, days_offset=11)

        # Mixed: admin says Yes, crew says No
        db.session.add(RSVP(regatta_id=r1.id, user_id=admin_user.id, status="yes"))
        db.session.add(RSVP(regatta_id=r1.id, user_id=crew.id, status="no"))
        # Only No
        db.session.add(RSVP(regatta_id=r2.id, user_id=crew.id, status="no"))
        db.session.commit()

        resp = logged_in_client.get("/?rsvp=yes")
        assert b"Mixed Regatta" in resp.data
        assert b"Only No Regatta" not in resp.data

    def test_filter_no_includes_regatta_with_mixed_rsvps(
        self, app, db, logged_in_client, admin_user
    ):
        """A regatta with a Yes AND a No RSVP should also appear when filtering No."""
        crew = User(
            email="crew@test.com",
            display_name="Crew",
            initials="CR",
        )
        crew.set_password("password")
        db.session.add(crew)
        db.session.commit()

        r1 = _create_regatta(db, "Mixed Regatta", admin_user.id, days_offset=10)
        db.session.add(RSVP(regatta_id=r1.id, user_id=admin_user.id, status="yes"))
        db.session.add(RSVP(regatta_id=r1.id, user_id=crew.id, status="no"))
        db.session.commit()

        resp = logged_in_client.get("/?rsvp=no")
        assert b"Mixed Regatta" in resp.data


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


class TestRSVPReset:
    """Submitting empty status (the '-' option) deletes the RSVP record."""

    def test_empty_status_deletes_existing_rsvp(
        self, app, db, logged_in_client, admin_user
    ):
        r = _create_regatta(db, "Test Regatta", admin_user.id)
        db.session.add(RSVP(regatta_id=r.id, user_id=admin_user.id, status="yes"))
        db.session.commit()

        assert RSVP.query.filter_by(regatta_id=r.id, user_id=admin_user.id).first()

        resp = logged_in_client.post(
            f"/regattas/{r.id}/rsvp",
            data={"status": ""},
        )
        assert resp.status_code == 302
        assert (
            RSVP.query.filter_by(regatta_id=r.id, user_id=admin_user.id).first() is None
        )

    def test_empty_status_no_existing_rsvp_does_not_error(
        self, app, db, logged_in_client, admin_user
    ):
        r = _create_regatta(db, "Test Regatta", admin_user.id)

        resp = logged_in_client.post(
            f"/regattas/{r.id}/rsvp",
            data={"status": ""},
        )
        assert resp.status_code == 302
        assert (
            RSVP.query.filter_by(regatta_id=r.id, user_id=admin_user.id).first() is None
        )

    def test_empty_status_preserves_filter_params(
        self, app, db, logged_in_client, admin_user
    ):
        r = _create_regatta(db, "Test Regatta", admin_user.id)

        resp = logged_in_client.post(
            f"/regattas/{r.id}/rsvp",
            data={
                "status": "",
                "redirect_skipper": str(admin_user.id),
                "redirect_rsvp": ["yes", "maybe"],
            },
        )
        assert resp.status_code == 302
        location = resp.headers["Location"]
        assert f"skipper={admin_user.id}" in location
        assert "rsvp=yes" in location
        assert "rsvp=maybe" in location


class TestMonthDividerLabels:
    """Month divider labels render once per month group per view."""

    def test_upcoming_shows_month_dividers_for_each_month(
        self, app, db, logged_in_client, admin_user
    ):
        today = date.today()
        first_next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        first_after_next_month = (
            first_next_month.replace(day=28) + timedelta(days=4)
        ).replace(day=1)

        first_month_date = first_next_month + timedelta(days=2)
        second_month_date = first_after_next_month + timedelta(days=2)

        _create_regatta_on(db, "Month One", admin_user.id, first_month_date)
        _create_regatta_on(db, "Month Two", admin_user.id, second_month_date)

        resp = logged_in_client.get("/")
        html = resp.data.decode()

        month_one = first_month_date.strftime("%B")
        month_two = second_month_date.strftime("%B")

        assert html.count(f'class="month-divider-text">{month_one}<') == 2
        assert html.count(f'class="month-divider-text">{month_two}<') == 2

    def test_past_shows_month_dividers_for_each_month(
        self, app, db, logged_in_client, admin_user
    ):
        today = date.today()
        first_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        first_two_months_ago = (first_last_month - timedelta(days=1)).replace(day=1)

        last_month_date = first_last_month + timedelta(days=2)
        two_months_ago_date = first_two_months_ago + timedelta(days=2)

        _create_regatta_on(db, "Past One", admin_user.id, two_months_ago_date)
        _create_regatta_on(db, "Past Two", admin_user.id, last_month_date)

        resp = logged_in_client.get("/")
        html = resp.data.decode()

        month_one = two_months_ago_date.strftime("%B")
        month_two = last_month_date.strftime("%B")

        assert html.count(f'class="month-divider-text">{month_one}<') == 2
        assert html.count(f'class="month-divider-text">{month_two}<') == 2

    def test_same_month_renders_single_divider_per_view(
        self, app, db, logged_in_client, admin_user
    ):
        today = date.today()
        first_next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        first_date = first_next_month + timedelta(days=2)
        second_date = first_next_month + timedelta(days=8)

        _create_regatta_on(db, "Same Month One", admin_user.id, first_date)
        _create_regatta_on(db, "Same Month Two", admin_user.id, second_date)

        resp = logged_in_client.get("/")
        html = resp.data.decode()

        month_label = first_date.strftime("%B")
        assert html.count(f'class="month-divider-text">{month_label}<') == 2
