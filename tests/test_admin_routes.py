"""Tests for admin routes (access control and basic flows)."""

import json
from datetime import date, datetime, timezone
from unittest.mock import patch

from app.models import Document, ImportCache, Regatta, SiteSetting, User


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

    def test_analytics_settings_requires_login(self, client):
        resp = client.get("/admin/settings/analytics")
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

    def test_analytics_settings_requires_admin(self, app, client, db):
        user = User(
            email="crew2@test.com",
            display_name="Crew 2",
            initials="C2",
            is_admin=False,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "crew2@test.com", "password": "password"},
            follow_redirects=True,
        )
        resp = client.get("/admin/settings/analytics", follow_redirects=True)
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

    def test_analytics_settings_accessible_for_admin(self, logged_in_client):
        resp = logged_in_client.get("/admin/settings/analytics")
        assert resp.status_code == 200
        assert b"Analytics Settings" in resp.data

    def test_analytics_settings_persists_measurement_id(self, logged_in_client):
        resp = logged_in_client.post(
            "/admin/settings/analytics",
            data={"ga_measurement_id": "G-TESTABC123"},
            follow_redirects=True,
        )
        assert b"Google Analytics settings updated" in resp.data

        setting = SiteSetting.query.filter_by(key="ga_measurement_id").first()
        assert setting is not None
        assert setting.value == "G-TESTABC123"


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


class TestImportCacheMultiple:
    """Tests for cache behavior in the multiple-regattas extract endpoint."""

    def _consume_sse(self, resp) -> list[dict]:
        """Parse SSE events from a response."""
        events = []
        for line in resp.data.decode().splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
        return events

    @patch("app.admin.routes._fetch_url_content")
    @patch("app.admin.routes.extract_regattas")
    def test_cache_miss_calls_ai_and_saves(
        self, mock_extract, mock_fetch, app, logged_in_client, db
    ):
        """First import of a URL should call AI and save to cache."""
        mock_fetch.return_value = "page content"
        mock_extract.return_value = [
            {
                "name": "Midwinters",
                "start_date": "2026-12-01",
                "location": "Test YC",
            }
        ]

        resp = logged_in_client.post(
            "/admin/import-schedule/extract",
            data={"schedule_url": "https://example.com/schedule", "year": "2026"},
        )
        self._consume_sse(resp)

        mock_extract.assert_called_once()

        # Verify cache was created
        cached = ImportCache.query.filter_by(url="https://example.com/schedule").first()
        assert cached is not None
        assert cached.regatta_count == 1
        assert "Midwinters" in cached.results_json

    @patch("app.admin.routes._fetch_url_content")
    @patch("app.admin.routes.extract_regattas")
    def test_cache_hit_skips_ai(
        self, mock_extract, mock_fetch, app, logged_in_client, db
    ):
        """Repeat import of same URL should use cache (no AI call)."""
        # Pre-populate cache
        cache = ImportCache(
            url="https://example.com/cached",
            year=2026,
            results_json=json.dumps(
                [
                    {
                        "name": "Cached Regatta",
                        "start_date": "2026-12-01",
                        "location": "Test YC",
                    }
                ]
            ),
            regatta_count=1,
            extracted_at=datetime.now(timezone.utc),
        )
        db.session.add(cache)
        db.session.commit()

        resp = logged_in_client.post(
            "/admin/import-schedule/extract",
            data={"schedule_url": "https://example.com/cached", "year": "2026"},
        )
        events = self._consume_sse(resp)

        # AI should NOT have been called
        mock_extract.assert_not_called()
        mock_fetch.assert_not_called()

        # Should have a "cached" message
        messages = [e.get("message", "") for e in events]
        assert any("cached" in m.lower() for m in messages)

        # Should reach 'done'
        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) == 1

    @patch("app.admin.routes._fetch_url_content")
    @patch("app.admin.routes.extract_regattas")
    def test_force_extract_bypasses_cache(
        self, mock_extract, mock_fetch, app, logged_in_client, db
    ):
        """Force re-extract should call AI even with cached results."""
        # Pre-populate cache
        cache = ImportCache(
            url="https://example.com/force-test",
            year=2026,
            results_json=json.dumps(
                [
                    {
                        "name": "Old Regatta",
                        "start_date": "2026-12-01",
                        "location": "Test YC",
                    }
                ]
            ),
            regatta_count=1,
            extracted_at=datetime.now(timezone.utc),
        )
        db.session.add(cache)
        db.session.commit()

        mock_fetch.return_value = "page content"
        mock_extract.return_value = [
            {
                "name": "New Regatta",
                "start_date": "2026-12-15",
                "location": "Test YC",
            }
        ]

        resp = logged_in_client.post(
            "/admin/import-schedule/extract",
            data={
                "schedule_url": "https://example.com/force-test",
                "year": "2026",
                "force_extract": "1",
            },
        )
        self._consume_sse(resp)

        # AI SHOULD have been called
        mock_extract.assert_called_once()

        # Cache should be updated
        cached = ImportCache.query.filter_by(
            url="https://example.com/force-test"
        ).first()
        assert "New Regatta" in cached.results_json

    def test_pasted_text_not_cached(self, app, logged_in_client, db):
        """Pasted text imports should not create cache entries."""
        with patch("app.admin.routes.extract_regattas") as mock_extract:
            mock_extract.return_value = [
                {
                    "name": "Pasted Regatta",
                    "start_date": "2026-12-01",
                    "location": "Test YC",
                }
            ]

            resp = logged_in_client.post(
                "/admin/import-schedule/extract",
                data={"schedule_text": "Some regatta schedule text", "year": "2026"},
            )
            self._consume_sse(resp)

        assert ImportCache.query.count() == 0


class TestImportCacheSingle:
    """Tests for cache behavior in the single-regatta extract endpoint."""

    def _consume_sse(self, resp) -> list[dict]:
        events = []
        for line in resp.data.decode().splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
        return events

    @patch("app.admin.routes._fetch_url_content")
    @patch("app.admin.routes.extract_regattas")
    def test_single_cache_hit(
        self, mock_extract, mock_fetch, app, logged_in_client, db
    ):
        """Single import should use cache on repeat URL."""
        cache = ImportCache(
            url="https://example.com/single-cached",
            year=2026,
            results_json=json.dumps(
                [
                    {
                        "name": "Single Cached",
                        "start_date": "2026-12-01",
                        "location": "Test YC",
                    }
                ]
            ),
            regatta_count=1,
            extracted_at=datetime.now(timezone.utc),
        )
        db.session.add(cache)
        db.session.commit()

        resp = logged_in_client.post(
            "/admin/import-schedule/extract-single",
            data={
                "schedule_url": "https://example.com/single-cached",
                "year": "2026",
            },
        )
        events = self._consume_sse(resp)

        mock_extract.assert_not_called()
        mock_fetch.assert_not_called()

        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) == 1

    @patch("app.admin.routes._fetch_url_content")
    @patch("app.admin.routes.extract_regattas")
    def test_single_force_extract(
        self, mock_extract, mock_fetch, app, logged_in_client, db
    ):
        """Single import with force_extract should bypass cache."""
        cache = ImportCache(
            url="https://example.com/single-force",
            year=2026,
            results_json=json.dumps(
                [{"name": "Old", "start_date": "2026-12-01", "location": "YC"}]
            ),
            regatta_count=1,
            extracted_at=datetime.now(timezone.utc),
        )
        db.session.add(cache)
        db.session.commit()

        mock_fetch.return_value = "content"
        mock_extract.return_value = [
            {"name": "Fresh", "start_date": "2026-12-10", "location": "YC"}
        ]

        resp = logged_in_client.post(
            "/admin/import-schedule/extract-single",
            data={
                "schedule_url": "https://example.com/single-force",
                "year": "2026",
                "force_extract": "1",
            },
        )
        self._consume_sse(resp)

        mock_extract.assert_called_once()


class TestImportConfirmSourceUrl:
    """Tests that source_url is persisted during import confirm."""

    def test_imports_regatta_with_source_url(self, app, logged_in_client, db):
        resp = logged_in_client.post(
            "/admin/import-schedule/confirm",
            data={
                "selected": "0",
                "name_0": "Source URL Regatta",
                "location_0": "Test YC",
                "start_date_0": "2026-09-15",
                "end_date_0": "",
                "notes_0": "",
                "location_url_0": "",
                "detail_url_0": "https://example.com/regatta/detail",
                "doc_count_0": "0",
            },
            follow_redirects=True,
        )
        assert b"Successfully imported 1 regatta" in resp.data

        regatta = Regatta.query.filter_by(name="Source URL Regatta").first()
        assert regatta is not None
        assert regatta.source_url == "https://example.com/regatta/detail"

    def test_imports_regatta_without_source_url(self, app, logged_in_client, db):
        resp = logged_in_client.post(
            "/admin/import-schedule/confirm",
            data={
                "selected": "0",
                "name_0": "No Source Regatta",
                "location_0": "Test YC",
                "start_date_0": "2026-09-16",
                "end_date_0": "",
                "notes_0": "",
                "location_url_0": "",
                "doc_count_0": "0",
            },
            follow_redirects=True,
        )
        assert b"Successfully imported 1 regatta" in resp.data

        regatta = Regatta.query.filter_by(name="No Source Regatta").first()
        assert regatta is not None
        assert regatta.source_url is None


class TestDiscoverDocumentsForRegatta:
    """Tests for the discover-documents SSE endpoint."""

    def _consume_sse(self, resp) -> list[dict]:
        events = []
        for line in resp.data.decode().splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
        return events

    def test_no_source_url_returns_error(self, app, logged_in_client, db, admin_user):
        regatta = Regatta(
            name="No URL Regatta",
            location="Test YC",
            start_date=date(2026, 9, 20),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        resp = logged_in_client.post(
            f"/admin/regattas/{regatta.id}/discover-documents",
        )
        events = self._consume_sse(resp)
        assert any(e.get("type") == "error" for e in events)
        assert any("No source URL" in e.get("message", "") for e in events)

    @patch("app.admin.routes.discover_documents")
    @patch("app.admin.routes._fetch_url_content")
    def test_discover_documents_success(
        self, mock_fetch, mock_discover, app, logged_in_client, db, admin_user
    ):
        regatta = Regatta(
            name="Discover Test",
            location="Test YC",
            start_date=date(2026, 9, 21),
            source_url="https://example.com/regatta/test",
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        mock_fetch.return_value = "page content"
        mock_discover.return_value = [
            {"doc_type": "NOR", "url": "https://example.com/nor.pdf", "label": "NOR"},
        ]

        resp = logged_in_client.post(
            f"/admin/regattas/{regatta.id}/discover-documents",
        )
        events = self._consume_sse(resp)

        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) == 1
        assert "task_id" in done_events[0]


class TestReviewDocumentsForRegatta:
    """Tests for the review-documents page."""

    def test_missing_task_id_redirects(self, app, logged_in_client, db, admin_user):
        regatta = Regatta(
            name="Review Test",
            location="Test YC",
            start_date=date(2026, 9, 25),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        resp = logged_in_client.get(
            f"/admin/regattas/{regatta.id}/review-documents",
            follow_redirects=True,
        )
        assert b"Document discovery results not found" in resp.data

    def test_regatta_not_found_redirects(self, logged_in_client):
        resp = logged_in_client.get(
            "/admin/regattas/99999/review-documents?task_id=bogus",
            follow_redirects=True,
        )
        assert b"Regatta not found" in resp.data


class TestAttachDocumentsForRegatta:
    """Tests for the attach-documents endpoint."""

    def test_attach_documents(self, app, logged_in_client, db, admin_user):
        regatta = Regatta(
            name="Attach Test",
            location="Test YC",
            start_date=date(2026, 9, 28),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        resp = logged_in_client.post(
            f"/admin/regattas/{regatta.id}/attach-documents",
            data={
                "doc_count": "2",
                "doc_0": "1",
                "doc_type_0": "NOR",
                "doc_url_0": "https://example.com/nor.pdf",
                "doc_1": "1",
                "doc_type_1": "WWW",
                "doc_url_1": "https://example.com/regatta",
            },
            follow_redirects=True,
        )
        assert b"2 document(s) attached" in resp.data

        docs = Document.query.filter_by(regatta_id=regatta.id).all()
        assert len(docs) == 2
        doc_types = {d.doc_type for d in docs}
        assert doc_types == {"NOR", "WWW"}

    def test_attach_no_selection(self, app, logged_in_client, db, admin_user):
        regatta = Regatta(
            name="No Select Test",
            location="Test YC",
            start_date=date(2026, 9, 29),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        resp = logged_in_client.post(
            f"/admin/regattas/{regatta.id}/attach-documents",
            data={"doc_count": "1"},
            follow_redirects=True,
        )
        assert b"No documents selected" in resp.data

    def test_attach_replaces_duplicates(self, app, logged_in_client, db, admin_user):
        regatta = Regatta(
            name="Dup Replace Test",
            location="Test YC",
            start_date=date(2026, 9, 30),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        # Pre-attach a document as NOR
        existing = Document(
            regatta_id=regatta.id,
            doc_type="NOR",
            url="https://example.com/nor.pdf",
            uploaded_by=admin_user.id,
        )
        db.session.add(existing)
        db.session.commit()
        existing_id = existing.id

        # Attach same URL (updated type) plus a new one
        resp = logged_in_client.post(
            f"/admin/regattas/{regatta.id}/attach-documents",
            data={
                "doc_count": "2",
                "doc_0": "1",
                "doc_type_0": "SI",
                "doc_url_0": "https://example.com/nor.pdf",
                "doc_1": "1",
                "doc_type_1": "WWW",
                "doc_url_1": "https://example.com/regatta",
            },
            follow_redirects=True,
        )
        assert b"1 document(s) attached" in resp.data
        assert b"1 existing document(s) updated" in resp.data

        docs = Document.query.filter_by(regatta_id=regatta.id).all()
        assert len(docs) == 2  # updated existing + new WWW

        # Verify the existing doc was updated in place
        updated = db.session.get(Document, existing_id)
        assert updated.doc_type == "SI"

    def test_regatta_not_found(self, logged_in_client):
        resp = logged_in_client.post(
            "/admin/regattas/99999/attach-documents",
            data={"doc_count": "0"},
            follow_redirects=True,
        )
        assert b"Regatta not found" in resp.data
