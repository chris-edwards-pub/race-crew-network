"""Tests for admin routes (access control and basic flows)."""

from datetime import date

from app.models import Regatta, User


class TestAdminAccessUnauthenticated:
    """Tests that run without login — must come before authenticated tests."""

    def test_import_single_requires_login(self, client):
        resp = client.get("/admin/import-single")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_import_multiple_requires_login(self, client):
        resp = client.get("/admin/import-multiple")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_import_paste_requires_login(self, client):
        resp = client.get("/admin/import-paste")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_import_multiple_requires_admin(self, app, client, db):
        """Non-admin user should be denied."""
        user = User(
            email="crew@test.com",
            display_name="Crew",
            initials="CR",
            is_admin=False,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "crew@test.com", "password": "password"},
            follow_redirects=True,
        )
        resp = client.get("/admin/import-multiple", follow_redirects=True)
        assert b"Access denied" in resp.data


class TestAdminAccessAuthenticated:
    """Tests that require an admin login."""

    def test_import_schedule_redirects_to_multiple(self, logged_in_client):
        """Legacy URL should redirect to import-multiple."""
        resp = logged_in_client.get("/admin/import-schedule")
        assert resp.status_code == 302
        assert "/admin/import-multiple" in resp.headers["Location"]

    def test_import_single_accessible_for_admin(self, logged_in_client):
        resp = logged_in_client.get("/admin/import-single")
        assert resp.status_code == 200
        assert b"Import Single Regatta" in resp.data

    def test_import_multiple_accessible_for_admin(self, logged_in_client):
        resp = logged_in_client.get("/admin/import-multiple")
        assert resp.status_code == 200
        assert b"Import Multiple Regattas" in resp.data

    def test_import_paste_accessible_for_admin(self, logged_in_client):
        resp = logged_in_client.get("/admin/import-paste")
        assert resp.status_code == 200
        assert b"Paste Schedule Text" in resp.data


class TestImportSchedulePreview:
    def test_missing_task_id_redirects(self, logged_in_client):
        resp = logged_in_client.get(
            "/admin/import-schedule/preview", follow_redirects=True
        )
        assert b"Extraction results not found" in resp.data

    def test_invalid_task_id_redirects(self, logged_in_client):
        resp = logged_in_client.get(
            "/admin/import-schedule/preview?task_id=bogus",
            follow_redirects=True,
        )
        assert b"Extraction results not found" in resp.data


class TestImportSinglePreview:
    def test_missing_task_id_redirects(self, logged_in_client):
        resp = logged_in_client.get(
            "/admin/import-single/preview", follow_redirects=True
        )
        assert b"Extraction results not found" in resp.data

    def test_invalid_task_id_redirects(self, logged_in_client):
        resp = logged_in_client.get(
            "/admin/import-single/preview?task_id=bogus",
            follow_redirects=True,
        )
        assert b"Extraction results not found" in resp.data


class TestImportScheduleConfirm:
    def test_no_selection_redirects(self, logged_in_client):
        resp = logged_in_client.post(
            "/admin/import-schedule/confirm",
            data={},
            follow_redirects=True,
        )
        assert b"No regattas selected" in resp.data

    def test_imports_regatta(self, app, logged_in_client, db):
        resp = logged_in_client.post(
            "/admin/import-schedule/confirm",
            data={
                "selected": "0",
                "name_0": "Test Regatta",
                "boat_class_0": "Thistle",
                "location_0": "Test YC",
                "start_date_0": "2026-09-01",
                "end_date_0": "2026-09-02",
                "notes_0": "",
                "location_url_0": "",
                "doc_count_0": "0",
            },
            follow_redirects=True,
        )
        assert b"Successfully imported 1 regatta" in resp.data

        regatta = Regatta.query.filter_by(name="Test Regatta").first()
        assert regatta is not None
        assert regatta.start_date == date(2026, 9, 1)
        assert regatta.boat_class == "Thistle"

    def test_imports_regatta_boat_class_defaults_to_tbd(
        self, app, logged_in_client, db
    ):
        resp = logged_in_client.post(
            "/admin/import-schedule/confirm",
            data={
                "selected": "0",
                "name_0": "No Class Regatta",
                "location_0": "Test YC",
                "start_date_0": "2026-09-05",
                "end_date_0": "",
                "notes_0": "",
                "location_url_0": "",
                "doc_count_0": "0",
            },
            follow_redirects=True,
        )
        assert b"Successfully imported 1 regatta" in resp.data

        regatta = Regatta.query.filter_by(name="No Class Regatta").first()
        assert regatta is not None
        assert regatta.boat_class == "TBD"

    def test_skips_duplicate(self, app, logged_in_client, db, admin_user):
        existing = Regatta(
            name="Duplicate Test",
            location="Test",
            start_date=date(2026, 10, 1),
            created_by=admin_user.id,
        )
        db.session.add(existing)
        db.session.commit()

        resp = logged_in_client.post(
            "/admin/import-schedule/confirm",
            data={
                "selected": "0",
                "name_0": "Duplicate Test",
                "location_0": "Test",
                "start_date_0": "2026-10-01",
                "end_date_0": "",
                "notes_0": "",
                "location_url_0": "",
                "doc_count_0": "0",
            },
            follow_redirects=True,
        )
        assert b"Skipped 1 regatta" in resp.data

    def test_imports_with_documents(self, app, logged_in_client, db):
        resp = logged_in_client.post(
            "/admin/import-schedule/confirm",
            data={
                "selected": "0",
                "name_0": "Doc Import Test",
                "location_0": "Test YC",
                "start_date_0": "2026-11-01",
                "end_date_0": "",
                "notes_0": "",
                "location_url_0": "",
                "doc_count_0": "2",
                "doc_0_0": "1",
                "doc_type_0_0": "NOR",
                "doc_url_0_0": "https://example.com/nor.pdf",
                "doc_0_1": "1",
                "doc_type_0_1": "WWW",
                "doc_url_0_1": "https://example.com/regatta",
            },
            follow_redirects=True,
        )
        assert b"Successfully imported 1 regatta" in resp.data
        assert b"2 document(s) attached" in resp.data


class TestDocumentReview:
    def test_missing_task_id_redirects(self, logged_in_client):
        resp = logged_in_client.get(
            "/admin/import-schedule/documents",
            follow_redirects=True,
        )
        assert b"Document discovery results not found" in resp.data
