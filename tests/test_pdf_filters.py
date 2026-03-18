"""Tests for PDF schedule respecting schedule and RSVP filters (#71)."""

from datetime import date, timedelta
from unittest.mock import patch

from app.models import RSVP, Regatta, User


def _create_regatta(db, name, created_by, days_offset=7):
    r = Regatta(
        name=name,
        location="Test Location",
        start_date=date.today() + timedelta(days=days_offset),
        created_by=created_by,
    )
    db.session.add(r)
    db.session.commit()
    return r


class TestPDFFilters:
    @patch("app.regattas.routes.HTML")
    def test_pdf_no_filters_includes_all(
        self, mock_html, app, db, logged_in_client, admin_user
    ):
        mock_html.return_value.write_pdf.return_value = b"%PDF-fake"

        _create_regatta(db, "Regatta A", admin_user.id, days_offset=10)
        _create_regatta(db, "Regatta B", admin_user.id, days_offset=11)

        resp = logged_in_client.get("/schedule.pdf")
        assert resp.status_code == 200
        rendered_html = mock_html.call_args[1]["string"]
        assert "Regatta A" in rendered_html
        assert "Regatta B" in rendered_html

    @patch("app.regattas.routes.HTML")
    def test_pdf_skipper_filter(self, mock_html, app, db, logged_in_client, admin_user):
        mock_html.return_value.write_pdf.return_value = b"%PDF-fake"

        other = User(
            email="skipper2@test.com",
            display_name="Other",
            initials="OT",
            is_skipper=True,
        )
        other.set_password("password")
        db.session.add(other)
        db.session.commit()

        _create_regatta(db, "Admin Regatta", admin_user.id, days_offset=10)
        _create_regatta(db, "Other Regatta", other.id, days_offset=11)

        resp = logged_in_client.get(f"/schedule.pdf?skipper={admin_user.id}")
        assert resp.status_code == 200
        rendered_html = mock_html.call_args[1]["string"]
        assert "Admin Regatta" in rendered_html
        assert "Other Regatta" not in rendered_html

    @patch("app.regattas.routes.HTML")
    def test_pdf_rsvp_filter(self, mock_html, app, db, logged_in_client, admin_user):
        mock_html.return_value.write_pdf.return_value = b"%PDF-fake"

        r1 = _create_regatta(db, "Yes Regatta", admin_user.id, days_offset=10)
        r2 = _create_regatta(db, "No Regatta", admin_user.id, days_offset=11)

        db.session.add(RSVP(regatta_id=r1.id, user_id=admin_user.id, status="yes"))
        db.session.add(RSVP(regatta_id=r2.id, user_id=admin_user.id, status="no"))
        db.session.commit()

        resp = logged_in_client.get("/schedule.pdf?rsvp=yes")
        assert resp.status_code == 200
        rendered_html = mock_html.call_args[1]["string"]
        assert "Yes Regatta" in rendered_html
        assert "No Regatta" not in rendered_html

    @patch("app.regattas.routes.HTML")
    def test_pdf_combined_skipper_and_rsvp_filter(
        self, mock_html, app, db, logged_in_client, admin_user
    ):
        mock_html.return_value.write_pdf.return_value = b"%PDF-fake"

        other = User(
            email="skipper2@test.com",
            display_name="Other",
            initials="OT",
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

        resp = logged_in_client.get(f"/schedule.pdf?skipper={admin_user.id}&rsvp=yes")
        assert resp.status_code == 200
        rendered_html = mock_html.call_args[1]["string"]
        assert "Admin Yes" in rendered_html
        assert "Other Yes" not in rendered_html


class TestPDFSkipperColumnAndTitle:
    @patch("app.regattas.routes.HTML")
    def test_all_schedules_shows_skipper_column(
        self, mock_html, app, db, logged_in_client, admin_user
    ):
        mock_html.return_value.write_pdf.return_value = b"%PDF-fake"
        _create_regatta(db, "Regatta A", admin_user.id, days_offset=10)

        resp = logged_in_client.get("/schedule.pdf?skipper=0")
        assert resp.status_code == 200
        rendered_html = mock_html.call_args[1]["string"]
        assert "<th>Skipper</th>" in rendered_html
        assert "Combined Race Schedules" in rendered_html

    @patch("app.regattas.routes.HTML")
    def test_single_skipper_hides_skipper_column(
        self, mock_html, app, db, logged_in_client, admin_user
    ):
        mock_html.return_value.write_pdf.return_value = b"%PDF-fake"
        _create_regatta(db, "Regatta A", admin_user.id, days_offset=10)

        resp = logged_in_client.get(f"/schedule.pdf?skipper={admin_user.id}")
        assert resp.status_code == 200
        rendered_html = mock_html.call_args[1]["string"]
        assert "<th>Skipper</th>" not in rendered_html
        assert "Admin&#39;s Race Schedule" in rendered_html

    @patch("app.regattas.routes.HTML")
    def test_all_schedules_includes_skipper_names(
        self, mock_html, app, db, logged_in_client, admin_user
    ):
        mock_html.return_value.write_pdf.return_value = b"%PDF-fake"

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

        _create_regatta(db, "Admin Regatta", admin_user.id, days_offset=10)
        _create_regatta(db, "Jane Regatta", other.id, days_offset=11)

        resp = logged_in_client.get("/schedule.pdf?skipper=0")
        assert resp.status_code == 200
        rendered_html = mock_html.call_args[1]["string"]
        assert "Admin" in rendered_html
        assert "Jane Doe" in rendered_html


class TestCrewPDFTitle:
    def test_crew_single_skipper_pdf_link_includes_skipper_param(
        self, app, db, logged_in_crew, crew_user, skipper_user
    ):
        """Crew member with one skipper: PDF link should include ?skipper=<id>."""
        _create_regatta(db, "Skipper Race", skipper_user.id, days_offset=10)

        resp = logged_in_crew.get("/")
        html = resp.data.decode()
        assert f"schedule.pdf?skipper={skipper_user.id}" in html

    @patch("app.regattas.routes.HTML")
    def test_crew_single_skipper_pdf_title_matches_page(
        self, mock_html, app, db, logged_in_crew, crew_user, skipper_user
    ):
        """PDF for crew with one skipper should show skipper's name, not 'Combined'."""
        mock_html.return_value.write_pdf.return_value = b"%PDF-fake"
        _create_regatta(db, "Skipper Race", skipper_user.id, days_offset=10)

        resp = logged_in_crew.get(f"/schedule.pdf?skipper={skipper_user.id}")
        assert resp.status_code == 200
        rendered_html = mock_html.call_args[1]["string"]
        assert "Skipper" in rendered_html
        assert "Combined Race Schedules" not in rendered_html
        assert "<th>Skipper</th>" not in rendered_html


class TestPDFMonthDividers:
    @patch("app.regattas.routes.HTML")
    def test_pdf_includes_month_divider_rows(
        self, mock_html, app, db, logged_in_client, admin_user
    ):
        """PDF should include month divider rows between regattas in different months."""
        mock_html.return_value.write_pdf.return_value = b"%PDF-fake"

        _create_regatta(db, "March Race", admin_user.id, days_offset=10)
        _create_regatta(db, "April Race", admin_user.id, days_offset=40)

        resp = logged_in_client.get(f"/schedule.pdf?skipper={admin_user.id}")
        assert resp.status_code == 200
        rendered_html = mock_html.call_args[1]["string"]
        assert "month-divider-cell" in rendered_html


class TestPDFCrewColumnRendering:
    @patch("app.regattas.routes.HTML")
    def test_pdf_uses_avatar_svg_not_profile_image(
        self, mock_html, app, db, logged_in_client, admin_user
    ):
        """PDF crew column should use avatar_svg, not user_icon, to avoid broken images."""
        mock_html.return_value.write_pdf.return_value = b"%PDF-fake"

        # Give admin a profile_image_key to trigger user_icon's <img> path
        admin_user.profile_image_key = "uploads/fake-photo.jpg"
        db.session.commit()

        r = _create_regatta(db, "Test Regatta", admin_user.id, days_offset=10)
        db.session.add(RSVP(regatta_id=r.id, user_id=admin_user.id, status="yes"))
        db.session.commit()

        resp = logged_in_client.get(f"/schedule.pdf?skipper={admin_user.id}")
        assert resp.status_code == 200
        rendered_html = mock_html.call_args[1]["string"]
        # Should NOT contain the display_name as alt text from a broken <img>
        assert "avatar-photo" not in rendered_html
        # Should contain inline SVG avatar instead
        assert "avatar-icon" in rendered_html


class TestPDFLinkCarriesFilters:
    def test_pdf_link_includes_skipper_param(
        self, app, db, logged_in_client, admin_user
    ):
        resp = logged_in_client.get(f"/?skipper={admin_user.id}")
        html = resp.data.decode()
        assert f"schedule.pdf?skipper={admin_user.id}" in html

    def test_pdf_link_includes_rsvp_params(self, app, db, logged_in_client, admin_user):
        resp = logged_in_client.get("/?rsvp=yes&rsvp=maybe")
        html = resp.data.decode()
        assert "schedule.pdf?" in html
        assert "rsvp=yes" in html
        assert "rsvp=maybe" in html

    def test_pdf_link_no_filters_is_plain(self, app, db, logged_in_client, admin_user):
        resp = logged_in_client.get("/?skipper=0")
        html = resp.data.decode()
        # skipper=0 means "All Schedules" — should still be in the URL
        assert "schedule.pdf?skipper=0" in html
