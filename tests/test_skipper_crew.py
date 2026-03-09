"""Tests for skipper-crew management routes and multi-user access control."""

from datetime import date

from app.models import Document, Regatta, RSVP, User, skipper_crew


class TestCrewManagementPage:
    def test_my_crew_requires_login(self, client):
        resp = client.get("/my-crew")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_my_crew_denied_for_crew(self, logged_in_crew):
        resp = logged_in_crew.get("/my-crew", follow_redirects=True)
        assert b"Access denied" in resp.data

    def test_my_crew_accessible_for_skipper(self, logged_in_skipper, crew_user):
        resp = logged_in_skipper.get("/my-crew")
        assert resp.status_code == 200
        assert b"My Crew" in resp.data
        assert crew_user.display_name.encode() in resp.data

    def test_my_crew_accessible_for_admin(self, logged_in_client):
        resp = logged_in_client.get("/my-crew")
        assert resp.status_code == 200
        assert b"My Crew" in resp.data


class TestInviteCrew:
    def test_invite_crew_creates_user(self, app, logged_in_skipper, db, skipper_user):
        resp = logged_in_skipper.post(
            "/my-crew/invite",
            data={"email": "newcrew@test.com"},
            follow_redirects=True,
        )
        assert b"Invite link:" in resp.data

        new_user = User.query.filter_by(email="newcrew@test.com").first()
        assert new_user is not None
        assert new_user.invite_token is not None
        assert new_user.invited_by == skipper_user.id
        assert new_user in skipper_user.crew_members.all()

    def test_invite_existing_user_adds_to_crew(
        self, app, logged_in_skipper, db, skipper_user
    ):
        # Create a standalone user
        other = User(
            email="other@test.com",
            display_name="Other",
            initials="OT",
            is_admin=False,
        )
        other.set_password("password")
        db.session.add(other)
        db.session.commit()

        resp = logged_in_skipper.post(
            "/my-crew/invite",
            data={"email": "other@test.com"},
            follow_redirects=True,
        )
        assert b"added to your crew" in resp.data
        assert other in skipper_user.crew_members.all()

    def test_invite_duplicate_warns(self, logged_in_skipper, crew_user):
        resp = logged_in_skipper.post(
            "/my-crew/invite",
            data={"email": crew_user.email},
            follow_redirects=True,
        )
        assert b"already on your crew" in resp.data

    def test_invite_crew_denied_for_crew_role(self, logged_in_crew):
        resp = logged_in_crew.post(
            "/my-crew/invite",
            data={"email": "nope@test.com"},
            follow_redirects=True,
        )
        assert b"Access denied" in resp.data


class TestRemoveCrew:
    def test_remove_crew_member(
        self, app, logged_in_skipper, db, skipper_user, crew_user
    ):
        resp = logged_in_skipper.post(
            f"/my-crew/{crew_user.id}/remove",
            follow_redirects=True,
        )
        assert b"removed from your crew" in resp.data
        assert crew_user not in skipper_user.crew_members.all()

    def test_remove_nonmember_warns(self, app, logged_in_skipper, db):
        other = User(
            email="stranger@test.com",
            display_name="Stranger",
            initials="ST",
        )
        other.set_password("password")
        db.session.add(other)
        db.session.commit()

        resp = logged_in_skipper.post(
            f"/my-crew/{other.id}/remove",
            follow_redirects=True,
        )
        assert b"not on your crew" in resp.data


class TestSkipperRegattaAccess:
    def test_skipper_can_create_regatta(self, app, logged_in_skipper, db):
        resp = logged_in_skipper.post(
            "/regattas/new",
            data={
                "name": "Skipper Regatta",
                "boat_class": "Thistle",
                "location": "Test YC",
                "start_date": "2026-07-01",
            },
            follow_redirects=True,
        )
        assert b"Skipper Regatta" in resp.data
        assert Regatta.query.filter_by(name="Skipper Regatta").first() is not None

    def test_skipper_can_edit_own_regatta(
        self, app, logged_in_skipper, db, skipper_user
    ):
        regatta = Regatta(
            name="Edit Me",
            location="Test YC",
            start_date=date(2026, 7, 1),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        resp = logged_in_skipper.get(f"/regattas/{regatta.id}/edit")
        assert resp.status_code == 200

    def test_skipper_cannot_edit_others_regatta(
        self, app, logged_in_skipper, db, admin_user
    ):
        regatta = Regatta(
            name="Not Mine",
            location="Test YC",
            start_date=date(2026, 7, 1),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        resp = logged_in_skipper.get(
            f"/regattas/{regatta.id}/edit", follow_redirects=True
        )
        assert b"Access denied" in resp.data

    def test_skipper_can_delete_own_regatta(
        self, app, logged_in_skipper, db, skipper_user
    ):
        regatta = Regatta(
            name="Delete Me",
            location="Test YC",
            start_date=date(2026, 7, 1),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.commit()
        rid = regatta.id

        resp = logged_in_skipper.post(f"/regattas/{rid}/delete", follow_redirects=True)
        assert b"deleted" in resp.data
        assert db.session.get(Regatta, rid) is None


class TestCrewRegattaAccess:
    def test_crew_cannot_create_regatta(self, logged_in_crew):
        resp = logged_in_crew.get("/regattas/new", follow_redirects=True)
        assert b"Access denied" in resp.data

    def test_crew_sees_skippers_regattas(self, app, logged_in_crew, db, skipper_user):
        regatta = Regatta(
            name="Visible Regatta",
            location="Test YC",
            start_date=date(2026, 8, 1),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        resp = logged_in_crew.get("/")
        assert b"Visible Regatta" in resp.data

    def test_crew_cannot_see_unrelated_regattas(
        self, app, logged_in_crew, db, admin_user
    ):
        regatta = Regatta(
            name="Hidden Regatta",
            location="Test YC",
            start_date=date(2026, 8, 1),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        resp = logged_in_crew.get("/")
        assert b"Hidden Regatta" not in resp.data

    def test_crew_can_rsvp_to_skippers_regatta(
        self, app, logged_in_crew, db, skipper_user
    ):
        regatta = Regatta(
            name="RSVP Test",
            location="Test YC",
            start_date=date(2026, 8, 1),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        resp = logged_in_crew.post(
            f"/regattas/{regatta.id}/rsvp",
            data={"status": "yes"},
            follow_redirects=True,
        )
        assert resp.status_code == 200

    def test_crew_cannot_rsvp_to_unrelated_regatta(
        self, app, logged_in_crew, db, admin_user
    ):
        regatta = Regatta(
            name="Blocked RSVP",
            location="Test YC",
            start_date=date(2026, 8, 1),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        resp = logged_in_crew.post(
            f"/regattas/{regatta.id}/rsvp",
            data={"status": "yes"},
            follow_redirects=True,
        )
        assert b"Access denied" in resp.data


class TestAdminInviteWithSkipperFlag:
    def test_admin_invite_as_skipper(self, app, logged_in_client, db):
        logged_in_client.post(
            "/admin/users/invite",
            data={"email": "newskip@test.com", "is_skipper": "on"},
            follow_redirects=True,
        )
        user = User.query.filter_by(email="newskip@test.com").first()
        assert user is not None
        assert user.is_skipper is True

    def test_admin_invite_without_skipper(self, app, logged_in_client, db):
        logged_in_client.post(
            "/admin/users/invite",
            data={"email": "newcrew@test.com"},
            follow_redirects=True,
        )
        user = User.query.filter_by(email="newcrew@test.com").first()
        assert user is not None
        assert user.is_skipper is False


class TestEditUserSkipperFlag:
    def test_admin_can_set_skipper(self, app, logged_in_client, db):
        user = User(
            email="toedit@test.com",
            display_name="Edit Me",
            initials="EM",
            is_admin=False,
            is_skipper=False,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        resp = logged_in_client.post(
            f"/admin/users/{user.id}/edit",
            data={
                "display_name": "Edit Me",
                "initials": "EM",
                "email": "toedit@test.com",
                "is_skipper": "on",
            },
            follow_redirects=True,
        )
        assert b"updated" in resp.data
        db.session.refresh(user)
        assert user.is_skipper is True


class TestRegistrationComplete:
    def test_admin_can_activate_pending_user(self, app, logged_in_client, db):
        user = User(
            email="pending@test.com",
            password_hash="pending",
            display_name="Pending",
            initials="PE",
            invite_token="some-token",
        )
        db.session.add(user)
        db.session.commit()

        resp = logged_in_client.post(
            f"/admin/users/{user.id}/edit",
            data={
                "display_name": "Now Active",
                "initials": "NA",
                "email": "pending@test.com",
                "password": "newpass123",
                "registration_complete": "on",
            },
            follow_redirects=True,
        )
        assert b"updated" in resp.data
        db.session.refresh(user)
        assert user.invite_token is None
        assert user.check_password("newpass123")

    def test_activation_requires_password(self, app, logged_in_client, db):
        user = User(
            email="pending2@test.com",
            password_hash="pending",
            display_name="Pending2",
            initials="P2",
            invite_token="another-token",
        )
        db.session.add(user)
        db.session.commit()

        resp = logged_in_client.post(
            f"/admin/users/{user.id}/edit",
            data={
                "display_name": "Pending2",
                "initials": "P2",
                "email": "pending2@test.com",
                "registration_complete": "on",
            },
            follow_redirects=True,
        )
        assert b"password is required" in resp.data
        db.session.refresh(user)
        assert user.invite_token is not None


class TestRegistrationAutoLink:
    def test_register_links_to_inviting_skipper(self, app, db, skipper_user):
        """When a user registers via invite from a skipper, they join the crew."""
        import secrets

        token = secrets.token_urlsafe(32)
        invited = User(
            email="invited@test.com",
            password_hash="pending",
            display_name="invited@test.com",
            initials="??",
            invite_token=token,
            invited_by=skipper_user.id,
        )
        db.session.add(invited)
        db.session.flush()
        skipper_user.crew_members.append(invited)
        db.session.commit()

        client = app.test_client()
        resp = client.post(
            f"/register/{token}",
            data={
                "display_name": "New Crew",
                "initials": "NC",
                "password": "password123",
                "password2": "password123",
            },
            follow_redirects=True,
        )
        assert b"Welcome aboard" in resp.data

        db.session.refresh(invited)
        assert invited.invite_token is None
        assert invited in skipper_user.crew_members.all()


class TestSkipperImportAccess:
    def test_skipper_can_access_import_url(self, logged_in_skipper):
        resp = logged_in_skipper.get("/admin/import-url")
        assert resp.status_code == 200
        assert b"Import from URL" in resp.data

    def test_skipper_can_access_import_file(self, logged_in_skipper):
        resp = logged_in_skipper.get("/admin/import-file")
        assert resp.status_code == 200

    def test_skipper_can_access_import_paste(self, logged_in_skipper):
        resp = logged_in_skipper.get("/admin/import-paste")
        assert resp.status_code == 200

    def test_crew_denied_import_url(self, logged_in_crew):
        resp = logged_in_crew.get("/admin/import-url", follow_redirects=True)
        assert b"Access denied" in resp.data

    def test_crew_denied_import_file(self, logged_in_crew):
        resp = logged_in_crew.get("/admin/import-file", follow_redirects=True)
        assert b"Access denied" in resp.data

    def test_skipper_denied_admin_settings(self, logged_in_skipper):
        resp = logged_in_skipper.get("/admin/settings/analytics", follow_redirects=True)
        assert b"Access denied" in resp.data

    def test_skipper_denied_email_settings(self, logged_in_skipper):
        resp = logged_in_skipper.get("/admin/settings/email", follow_redirects=True)
        assert b"Access denied" in resp.data


class TestCreateSchedule:
    def test_crew_can_create_schedule(self, app, logged_in_crew, db, crew_user):
        resp = logged_in_crew.post("/create-schedule", follow_redirects=True)
        assert b"Your schedule has been created!" in resp.data
        db.session.refresh(crew_user)
        assert crew_user.is_skipper is True

    def test_existing_crew_relationships_preserved(
        self, app, logged_in_crew, db, crew_user, skipper_user
    ):
        """After promoting to skipper, user is still crew for their existing skipper."""
        logged_in_crew.post("/create-schedule", follow_redirects=True)
        db.session.refresh(crew_user)
        assert crew_user.is_skipper is True
        assert crew_user in skipper_user.crew_members.all()

    def test_already_skipper_is_noop(self, logged_in_skipper, db, skipper_user):
        resp = logged_in_skipper.post("/create-schedule", follow_redirects=True)
        assert b"Your schedule has been created!" not in resp.data
        db.session.refresh(skipper_user)
        assert skipper_user.is_skipper is True

    def test_unauthenticated_redirects_to_login(self, client):
        resp = client.post("/create-schedule")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


class TestDeleteSchedule:
    def test_skipper_can_delete_schedule(self, app, logged_in_skipper, db, skipper_user):
        resp = logged_in_skipper.post("/delete-schedule", follow_redirects=True)
        assert b"Your schedule has been deleted." in resp.data
        db.session.refresh(skipper_user)
        assert skipper_user.is_skipper is False

    def test_delete_removes_regattas(
        self, app, logged_in_skipper, db, skipper_user
    ):
        regatta = Regatta(
            name="Gone Regatta",
            location="Test YC",
            start_date=date(2026, 8, 1),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.commit()
        rid = regatta.id

        logged_in_skipper.post("/delete-schedule", follow_redirects=True)
        assert db.session.get(Regatta, rid) is None

    def test_delete_unlinks_crew(
        self, app, logged_in_skipper, db, skipper_user, crew_user
    ):
        logged_in_skipper.post("/delete-schedule", follow_redirects=True)
        rows = db.session.execute(
            skipper_crew.select().where(
                skipper_crew.c.skipper_id == skipper_user.id
            )
        ).fetchall()
        assert len(rows) == 0

    def test_former_crew_can_create_own_schedule(
        self, app, logged_in_skipper, db, skipper_user, crew_user
    ):
        """After skipper deletes schedule, orphaned crew can still self-promote."""
        # Skipper deletes their schedule, orphaning crew
        logged_in_skipper.post("/delete-schedule", follow_redirects=True)
        db.session.refresh(crew_user)
        assert crew_user not in skipper_user.crew_members.all()

        # Switch to crew user on the same client
        logged_in_skipper.get("/logout", follow_redirects=True)
        logged_in_skipper.post(
            "/login",
            data={"email": "crew@test.com", "password": "password"},
            follow_redirects=True,
        )
        resp = logged_in_skipper.post("/create-schedule", follow_redirects=True)
        assert b"Your schedule has been created!" in resp.data
        db.session.expire_all()
        updated = db.session.get(User, crew_user.id)
        assert updated.is_skipper is True

    def test_admin_cannot_delete_schedule(self, logged_in_client):
        resp = logged_in_client.post("/delete-schedule", follow_redirects=True)
        assert b"Admins cannot delete their schedule" in resp.data

    def test_non_skipper_gets_error(self, logged_in_crew):
        resp = logged_in_crew.post("/delete-schedule", follow_redirects=True)
        assert b"don&#39;t have a schedule" in resp.data
