"""Tests for app.models."""

from datetime import date

import pytest

from app.models import RSVP, Document, ImportCache, Regatta, SiteSetting, User


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


class TestSkipperCrewRelationship:
    def test_skipper_crew_link(self, app, db, skipper_user, crew_user):
        assert crew_user in skipper_user.crew_members.all()
        assert skipper_user in crew_user.skippers

    def test_is_crew_property(self, app, db, crew_user):
        assert crew_user.is_crew is True

    def test_is_crew_false_for_skipper(self, app, db, skipper_user):
        assert skipper_user.is_crew is False

    def test_visible_regattas_admin_sees_all(self, app, db, admin_user, skipper_user):
        r1 = Regatta(
            name="Admin Regatta",
            location="YC",
            start_date=date(2026, 7, 1),
            created_by=admin_user.id,
        )
        r2 = Regatta(
            name="Skipper Regatta",
            location="YC",
            start_date=date(2026, 7, 2),
            created_by=skipper_user.id,
        )
        db.session.add_all([r1, r2])
        db.session.commit()

        visible = admin_user.visible_regattas().all()
        assert len(visible) == 2

    def test_visible_regattas_skipper_sees_own(self, app, db, admin_user, skipper_user):
        r1 = Regatta(
            name="Admin Regatta",
            location="YC",
            start_date=date(2026, 7, 1),
            created_by=admin_user.id,
        )
        r2 = Regatta(
            name="Skipper Regatta",
            location="YC",
            start_date=date(2026, 7, 2),
            created_by=skipper_user.id,
        )
        db.session.add_all([r1, r2])
        db.session.commit()

        visible = skipper_user.visible_regattas().all()
        assert len(visible) == 1
        assert visible[0].name == "Skipper Regatta"

    def test_visible_regattas_crew_sees_skippers(
        self, app, db, admin_user, skipper_user, crew_user
    ):
        r1 = Regatta(
            name="Admin Regatta",
            location="YC",
            start_date=date(2026, 7, 1),
            created_by=admin_user.id,
        )
        r2 = Regatta(
            name="Skipper Regatta",
            location="YC",
            start_date=date(2026, 7, 2),
            created_by=skipper_user.id,
        )
        db.session.add_all([r1, r2])
        db.session.commit()

        visible = crew_user.visible_regattas().all()
        assert len(visible) == 1
        assert visible[0].name == "Skipper Regatta"

    def test_visible_regattas_no_role_empty(self, app, db, admin_user):
        norole = User(
            email="norole@test.com",
            display_name="No Role",
            initials="NR",
        )
        norole.set_password("password")
        db.session.add(norole)
        db.session.flush()

        r = Regatta(
            name="Test",
            location="YC",
            start_date=date(2026, 7, 1),
            created_by=admin_user.id,
        )
        db.session.add(r)
        db.session.commit()

        assert norole.visible_regattas().all() == []


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

    def test_boat_class_defaults_to_blank(self, app, db, admin_user):
        regatta = Regatta(
            name="Default Class Test",
            location="Test YC",
            start_date=date(2026, 6, 20),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        assert regatta.boat_class == ""

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

    def test_source_url_nullable(self, app, db, admin_user):
        regatta = Regatta(
            name="No Source URL",
            location="Test YC",
            start_date=date(2026, 6, 22),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        assert regatta.source_url is None

    def test_source_url_explicit_value(self, app, db, admin_user):
        regatta = Regatta(
            name="With Source URL",
            location="Test YC",
            start_date=date(2026, 6, 23),
            source_url="https://example.com/regatta/123",
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        assert regatta.source_url == "https://example.com/regatta/123"

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


class TestImportCacheModel:
    def test_create_cache_entry(self, app, db):
        cache = ImportCache(
            url="https://example.com/schedule",
            year=2026,
            results_json='[{"name": "Test Regatta"}]',
            regatta_count=1,
        )
        db.session.add(cache)
        db.session.commit()

        assert cache.id is not None
        assert cache.url == "https://example.com/schedule"
        assert cache.regatta_count == 1
        assert cache.extracted_at is not None

    def test_url_unique_constraint(self, app, db):
        cache1 = ImportCache(
            url="https://example.com/unique",
            year=2026,
            results_json="[]",
            regatta_count=0,
        )
        db.session.add(cache1)
        db.session.commit()

        cache2 = ImportCache(
            url="https://example.com/unique",
            year=2026,
            results_json="[]",
            regatta_count=0,
        )
        db.session.add(cache2)
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()


class TestSiteSettingModel:
    def test_create_setting(self, app, db):
        setting = SiteSetting(key="ga_measurement_id", value="G-TEST123")
        db.session.add(setting)
        db.session.commit()

        assert setting.id is not None
        assert setting.key == "ga_measurement_id"
        assert setting.value == "G-TEST123"
        assert setting.updated_at is not None

    def test_key_unique_constraint(self, app, db):
        first = SiteSetting(key="ga_measurement_id", value="G-ONE")
        db.session.add(first)
        db.session.commit()

        duplicate = SiteSetting(key="ga_measurement_id", value="G-TWO")
        db.session.add(duplicate)
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()
