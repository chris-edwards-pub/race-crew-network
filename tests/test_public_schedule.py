"""Tests for public schedule page and slug management."""

from datetime import date, timedelta

from app.models import RSVP, Document, Regatta, User


def _publish_skipper(db, skipper, slug="test-skipper"):
    """Enable schedule publishing for a skipper."""
    skipper.schedule_published = True
    skipper.schedule_slug = slug
    db.session.commit()
    return skipper


def _create_regatta(db, skipper, name="Test Regatta", days_ahead=30):
    """Create a regatta owned by the given skipper."""
    r = Regatta(
        name=name,
        location="Test Location",
        start_date=date.today() + timedelta(days=days_ahead),
        created_by=skipper.id,
    )
    db.session.add(r)
    db.session.commit()
    return r


def _create_past_regatta(db, skipper, name="Past Regatta", days_ago=30):
    """Create a past regatta owned by the given skipper."""
    r = Regatta(
        name=name,
        location="Test Location",
        start_date=date.today() - timedelta(days=days_ago),
        created_by=skipper.id,
    )
    db.session.add(r)
    db.session.commit()
    return r


def _rsvp(db, user, regatta, status):
    """Create an RSVP record."""
    rsvp = RSVP(user_id=user.id, regatta_id=regatta.id, status=status)
    db.session.add(rsvp)
    db.session.commit()
    return rsvp


# ---------------------------------------------------------------------------
# Public Schedule Page
# ---------------------------------------------------------------------------


class TestPublicSchedule:
    """Public schedule page for anonymous access."""

    def test_public_schedule_returns_200(self, db, client, admin_user):
        _publish_skipper(db, admin_user, "admin-schedule")
        resp = client.get("/schedule/admin-schedule")
        assert resp.status_code == 200

    def test_public_schedule_404_unpublished(self, db, client, admin_user):
        admin_user.schedule_slug = "admin-schedule"
        admin_user.schedule_published = False
        db.session.commit()
        resp = client.get("/schedule/admin-schedule")
        assert resp.status_code == 404

    def test_public_schedule_404_no_slug(self, client):
        resp = client.get("/schedule/nonexistent-slug")
        assert resp.status_code == 404

    def test_public_schedule_shows_upcoming(self, db, client, admin_user):
        _publish_skipper(db, admin_user, "admin-schedule")
        _create_regatta(db, admin_user, name="Spring Series")
        resp = client.get("/schedule/admin-schedule")
        assert b"Spring Series" in resp.data

    def test_public_schedule_shows_past(self, db, client, admin_user):
        _publish_skipper(db, admin_user, "admin-schedule")
        _create_past_regatta(db, admin_user, name="Winter Series")
        resp = client.get("/schedule/admin-schedule")
        assert b"Winter Series" in resp.data

    def test_public_schedule_shows_skipper_name(self, db, client, admin_user):
        _publish_skipper(db, admin_user, "admin-schedule")
        resp = client.get("/schedule/admin-schedule")
        assert b"Admin&#39;s Race Schedule" in resp.data or b"Admin's Race Schedule" in resp.data

    def test_public_schedule_hides_rsvp_controls(self, db, client, admin_user):
        _publish_skipper(db, admin_user, "admin-schedule")
        _create_regatta(db, admin_user)
        resp = client.get("/schedule/admin-schedule")
        html = resp.data.decode()
        assert "Your RSVP" not in html
        assert '<select name="status"' not in html

    def test_public_schedule_no_profile_links(self, db, client, admin_user, crew_user):
        _publish_skipper(db, admin_user, "admin-schedule")
        r = _create_regatta(db, admin_user)
        _rsvp(db, crew_user, r, "yes")
        resp = client.get("/schedule/admin-schedule")
        html = resp.data.decode()
        assert "view_profile" not in html
        assert crew_user.initials.encode() in resp.data

    def test_public_schedule_shows_crew_initials(
        self, db, client, admin_user, crew_user
    ):
        _publish_skipper(db, admin_user, "admin-schedule")
        r = _create_regatta(db, admin_user)
        _rsvp(db, crew_user, r, "yes")
        resp = client.get("/schedule/admin-schedule")
        assert crew_user.initials.encode() in resp.data

    def test_public_schedule_shows_doc_links(self, db, client, admin_user):
        _publish_skipper(db, admin_user, "admin-schedule")
        r = _create_regatta(db, admin_user)
        doc = Document(
            regatta_id=r.id,
            doc_type="NOR",
            url="https://example.com/nor.pdf",
            uploaded_by=admin_user.id,
        )
        db.session.add(doc)
        db.session.commit()
        resp = client.get("/schedule/admin-schedule")
        assert b"NOR" in resp.data

    def test_public_schedule_has_pdf_link(self, db, client, admin_user):
        _publish_skipper(db, admin_user, "admin-schedule")
        resp = client.get("/schedule/admin-schedule")
        assert b"Print PDF" in resp.data
        assert b"/schedule/admin-schedule/schedule.pdf" in resp.data

    def test_public_schedule_anonymous_access(self, db, client, admin_user):
        """No login required — plain client (not logged_in_client)."""
        _publish_skipper(db, admin_user, "admin-schedule")
        _create_regatta(db, admin_user, name="Open Regatta")
        resp = client.get("/schedule/admin-schedule")
        assert resp.status_code == 200
        assert b"Open Regatta" in resp.data

    def test_public_schedule_no_edit_buttons(self, db, client, admin_user):
        _publish_skipper(db, admin_user, "admin-schedule")
        _create_regatta(db, admin_user)
        resp = client.get("/schedule/admin-schedule")
        html = resp.data.decode()
        assert "Edit</a>" not in html
        assert "Add Event" not in html
        assert "Delete" not in html


# ---------------------------------------------------------------------------
# Public PDF
# ---------------------------------------------------------------------------


class TestPublicPdf:
    """Public PDF download."""

    def test_public_pdf_returns_pdf(self, db, client, admin_user):
        _publish_skipper(db, admin_user, "admin-schedule")
        _create_regatta(db, admin_user)
        resp = client.get("/schedule/admin-schedule/schedule.pdf")
        assert resp.status_code == 200
        assert "application/pdf" in resp.content_type

    def test_public_pdf_404_unpublished(self, db, client, admin_user):
        admin_user.schedule_slug = "admin-schedule"
        admin_user.schedule_published = False
        db.session.commit()
        resp = client.get("/schedule/admin-schedule/schedule.pdf")
        assert resp.status_code == 404

    def test_public_pdf_404_no_slug(self, client):
        resp = client.get("/schedule/nonexistent/schedule.pdf")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Slug Generation
# ---------------------------------------------------------------------------


class TestSlugGeneration:
    """Schedule slug generation and uniqueness."""

    def test_slug_from_display_name(self, db, admin_user):
        admin_user.display_name = "Chris Edwards"
        db.session.commit()
        slug = admin_user.generate_schedule_slug()
        assert slug == "chris-edwards"

    def test_slug_strips_special_chars(self, db, admin_user):
        admin_user.display_name = "Jane O'Brien-Smith!"
        db.session.commit()
        slug = admin_user.generate_schedule_slug()
        assert slug == "jane-o-brien-smith"

    def test_slug_uniqueness(self, db, admin_user):
        admin_user.display_name = "Test User"
        admin_user.schedule_slug = "test-user"
        db.session.commit()

        other = User(
            email="other@test.com",
            display_name="Test User",
            initials="TU",
            password_hash="x",
        )
        db.session.add(other)
        db.session.commit()

        slug = other.generate_schedule_slug()
        assert slug == "test-user-1"

    def test_slug_uniqueness_multiple(self, db, admin_user):
        admin_user.display_name = "Test User"
        admin_user.schedule_slug = "test-user"
        db.session.commit()

        other1 = User(
            email="other1@test.com",
            display_name="Test User",
            initials="T1",
            password_hash="x",
            schedule_slug="test-user-1",
        )
        db.session.add(other1)
        db.session.commit()

        other2 = User(
            email="other2@test.com",
            display_name="Test User",
            initials="T2",
            password_hash="x",
        )
        db.session.add(other2)
        db.session.commit()

        slug = other2.generate_schedule_slug()
        assert slug == "test-user-2"


# ---------------------------------------------------------------------------
# Profile Publishing Settings
# ---------------------------------------------------------------------------


class TestProfilePublishing:
    """Publish toggle via profile POST."""

    def test_profile_auto_generates_slug(self, db, logged_in_client, admin_user):
        logged_in_client.post(
            "/profile",
            data={
                "display_name": admin_user.display_name,
                "initials": admin_user.initials,
                "email": admin_user.email,
                "schedule_published": "on",
            },
            follow_redirects=True,
        )
        db.session.refresh(admin_user)
        assert admin_user.schedule_slug == "admin"
        assert admin_user.schedule_published is True

    def test_slug_preserved_across_saves(self, db, logged_in_client, admin_user):
        _publish_skipper(db, admin_user, "admin-schedule")
        logged_in_client.post(
            "/profile",
            data={
                "display_name": admin_user.display_name,
                "initials": admin_user.initials,
                "email": admin_user.email,
                "schedule_published": "on",
            },
            follow_redirects=True,
        )
        db.session.refresh(admin_user)
        assert admin_user.schedule_slug == "admin-schedule"

    def test_unpublish_hides_page(self, db, client, logged_in_client, admin_user):
        _publish_skipper(db, admin_user, "admin-schedule")
        assert client.get("/schedule/admin-schedule").status_code == 200

        logged_in_client.post(
            "/profile",
            data={
                "display_name": admin_user.display_name,
                "initials": admin_user.initials,
                "email": admin_user.email,
                # schedule_published NOT included = unchecked
            },
            follow_redirects=True,
        )
        db.session.refresh(admin_user)
        assert admin_user.schedule_published is False
        assert client.get("/schedule/admin-schedule").status_code == 404


# ---------------------------------------------------------------------------
# Public View Button on Index
# ---------------------------------------------------------------------------


class TestPublicViewButton:
    """Public View button on the main schedule page."""

    def test_public_view_button_shown(self, db, logged_in_client, admin_user):
        _publish_skipper(db, admin_user, "admin-schedule")
        resp = logged_in_client.get("/")
        assert b"Public View URL" in resp.data
        assert b"/schedule/admin-schedule" in resp.data

    def test_public_view_button_hidden_when_unpublished(
        self, db, logged_in_client, admin_user
    ):
        admin_user.schedule_published = False
        db.session.commit()
        resp = logged_in_client.get("/")
        assert b"Public View URL" not in resp.data
