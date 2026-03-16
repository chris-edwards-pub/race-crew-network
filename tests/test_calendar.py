"""Tests for iCal feed RSVP filtering and calendar awareness features."""

from datetime import date, timedelta

from app.models import RSVP, Regatta

# ---------------------------------------------------------------------------
# iCal Feed Filtering
# ---------------------------------------------------------------------------


def _create_regatta(db, skipper, name="Test Regatta", days_ahead=30):
    """Helper to create a regatta owned by the given skipper."""
    r = Regatta(
        name=name,
        location="Test Location",
        start_date=date.today() + timedelta(days=days_ahead),
        created_by=skipper.id,
    )
    db.session.add(r)
    db.session.commit()
    return r


def _rsvp(db, user, regatta, status):
    """Helper to create an RSVP record."""
    rsvp = RSVP(user_id=user.id, regatta_id=regatta.id, status=status)
    db.session.add(rsvp)
    db.session.commit()
    return rsvp


def _subscribe(client):
    """Hit subscribe endpoint to generate a calendar token, return the response."""
    resp = client.get("/calendar/subscribe")
    assert resp.status_code == 200
    return resp


class TestIcalFeedFiltering:
    """Feed only includes regattas with yes/maybe RSVP."""

    def test_feed_includes_yes_rsvp(self, db, logged_in_client, admin_user):
        r = _create_regatta(db, admin_user)
        _rsvp(db, admin_user, r, "yes")
        _subscribe(logged_in_client)
        db.session.refresh(admin_user)

        resp = logged_in_client.get(f"/calendar/{admin_user.calendar_token}.ics")
        assert resp.status_code == 200
        assert b"Test Regatta" in resp.data

    def test_feed_includes_maybe_rsvp(self, db, logged_in_client, admin_user):
        r = _create_regatta(db, admin_user)
        _rsvp(db, admin_user, r, "maybe")
        _subscribe(logged_in_client)
        db.session.refresh(admin_user)

        resp = logged_in_client.get(f"/calendar/{admin_user.calendar_token}.ics")
        assert resp.status_code == 200
        assert b"Test Regatta" in resp.data

    def test_feed_excludes_no_rsvp(self, db, logged_in_client, admin_user):
        r = _create_regatta(db, admin_user)
        _rsvp(db, admin_user, r, "no")
        _subscribe(logged_in_client)
        db.session.refresh(admin_user)

        resp = logged_in_client.get(f"/calendar/{admin_user.calendar_token}.ics")
        assert resp.status_code == 200
        assert b"Test Regatta" not in resp.data

    def test_feed_excludes_no_rsvp_record(self, db, logged_in_client, admin_user):
        _create_regatta(db, admin_user)
        _subscribe(logged_in_client)
        db.session.refresh(admin_user)

        resp = logged_in_client.get(f"/calendar/{admin_user.calendar_token}.ics")
        assert resp.status_code == 200
        assert b"Test Regatta" not in resp.data

    def test_mixed_rsvps_only_yes_maybe(self, db, logged_in_client, admin_user):
        r1 = _create_regatta(db, admin_user, name="Yes Regatta", days_ahead=10)
        r2 = _create_regatta(db, admin_user, name="Maybe Regatta", days_ahead=20)
        r3 = _create_regatta(db, admin_user, name="No Regatta", days_ahead=30)
        _create_regatta(db, admin_user, name="No RSVP Regatta", days_ahead=40)
        _rsvp(db, admin_user, r1, "yes")
        _rsvp(db, admin_user, r2, "maybe")
        _rsvp(db, admin_user, r3, "no")
        # r4 has no RSVP
        _subscribe(logged_in_client)
        db.session.refresh(admin_user)

        resp = logged_in_client.get(f"/calendar/{admin_user.calendar_token}.ics")
        assert resp.status_code == 200
        assert b"Yes Regatta" in resp.data
        assert b"Maybe Regatta" in resp.data
        assert b"No Regatta" not in resp.data
        assert b"No RSVP Regatta" not in resp.data

    def test_skipper_own_regatta_excluded_without_rsvp(
        self, db, logged_in_skipper, skipper_user
    ):
        _create_regatta(db, skipper_user)
        _subscribe(logged_in_skipper)
        db.session.refresh(skipper_user)

        resp = logged_in_skipper.get(f"/calendar/{skipper_user.calendar_token}.ics")
        assert resp.status_code == 200
        assert b"Test Regatta" not in resp.data

    def test_skipper_own_regatta_included_with_yes(
        self, db, logged_in_skipper, skipper_user
    ):
        r = _create_regatta(db, skipper_user)
        _rsvp(db, skipper_user, r, "yes")
        _subscribe(logged_in_skipper)
        db.session.refresh(skipper_user)

        resp = logged_in_skipper.get(f"/calendar/{skipper_user.calendar_token}.ics")
        assert resp.status_code == 200
        assert b"Test Regatta" in resp.data

    def test_feed_content_type(self, db, logged_in_client, admin_user):
        r = _create_regatta(db, admin_user)
        _rsvp(db, admin_user, r, "yes")
        _subscribe(logged_in_client)
        db.session.refresh(admin_user)

        resp = logged_in_client.get(f"/calendar/{admin_user.calendar_token}.ics")
        assert resp.status_code == 200
        assert "text/calendar" in resp.content_type

    def test_invalid_token_returns_404(self, client):
        resp = client.get("/calendar/invalid-token-12345.ics")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Subscribe Page
# ---------------------------------------------------------------------------


class TestSubscribePage:
    """Dedicated calendar subscription page."""

    def test_page_renders_200(self, db, logged_in_client):
        resp = logged_in_client.get("/calendar/subscribe")
        assert resp.status_code == 200
        assert b"Calendar Subscription" in resp.data

    def test_generates_token_on_first_visit(self, db, logged_in_client, admin_user):
        assert admin_user.calendar_token is None
        logged_in_client.get("/calendar/subscribe")
        db.session.refresh(admin_user)
        assert admin_user.calendar_token is not None

    def test_shows_ics_url_with_token(self, db, logged_in_client, admin_user):
        resp = logged_in_client.get("/calendar/subscribe")
        db.session.refresh(admin_user)
        assert admin_user.calendar_token.encode() in resp.data
        assert b".ics" in resp.data

    def test_shows_copy_button(self, db, logged_in_client):
        resp = logged_in_client.get("/calendar/subscribe")
        assert b"Copy" in resp.data

    def test_shows_webcal_subscribe_button(self, db, logged_in_client, admin_user):
        resp = logged_in_client.get("/calendar/subscribe")
        db.session.refresh(admin_user)
        assert b"Open in Calendar App" in resp.data
        assert b"webcal://" in resp.data
        assert admin_user.calendar_token.encode() in resp.data

    def test_shows_apple_instructions(self, db, logged_in_client):
        resp = logged_in_client.get("/calendar/subscribe")
        assert b"Apple Calendar (iPhone / iPad)" in resp.data
        assert b"Apple Calendar (Mac)" in resp.data

    def test_shows_google_instructions(self, db, logged_in_client):
        resp = logged_in_client.get("/calendar/subscribe")
        assert b"Google Calendar" in resp.data
        assert b"calendar.google.com" in resp.data

    def test_shows_outlook_instructions(self, db, logged_in_client):
        resp = logged_in_client.get("/calendar/subscribe")
        assert b"Outlook" in resp.data
        assert b"outlook.live.com" in resp.data

    def test_preserves_existing_token(self, db, logged_in_client, admin_user):
        # First visit generates token
        logged_in_client.get("/calendar/subscribe")
        db.session.refresh(admin_user)
        original_token = admin_user.calendar_token
        # Second visit preserves it
        logged_in_client.get("/calendar/subscribe")
        db.session.refresh(admin_user)
        assert admin_user.calendar_token == original_token

    def test_requires_login(self, client):
        resp = client.get("/calendar/subscribe", follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert "/login" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# Calendar Banner on Index Page
# ---------------------------------------------------------------------------


class TestCalendarBanner:
    """Banner shown/hidden based on calendar_token presence."""

    def test_banner_shown_without_token(self, db, logged_in_client, admin_user):
        assert admin_user.calendar_token is None
        resp = logged_in_client.get("/")
        assert b"Sync your race schedule" in resp.data

    def test_banner_hidden_with_token(self, db, logged_in_client, admin_user):
        _subscribe(logged_in_client)
        db.session.refresh(admin_user)
        assert admin_user.calendar_token is not None
        resp = logged_in_client.get("/")
        assert b"Sync your race schedule" not in resp.data


# ---------------------------------------------------------------------------
# Profile Page Calendar Section
# ---------------------------------------------------------------------------


class TestProfileCalendarSection:
    """Profile shows generate button or subscription URL."""

    def test_profile_shows_generate_button_without_token(
        self, db, logged_in_client, admin_user
    ):
        resp = logged_in_client.get("/profile")
        assert b"Generate Calendar Feed" in resp.data

    def test_profile_shows_ics_url_with_token(self, db, logged_in_client, admin_user):
        _subscribe(logged_in_client)
        db.session.refresh(admin_user)
        resp = logged_in_client.get("/profile")
        assert admin_user.calendar_token.encode() in resp.data
        assert b".ics" in resp.data
        assert b"Copy" in resp.data
