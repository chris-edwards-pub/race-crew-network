"""Tests for profile picture display in navbar and profile pages (#69)."""

from unittest.mock import patch

from app.models import User


class TestNavbarAvatar:
    def test_navbar_shows_avatar_and_initials(self, app, client, db):
        user = User(
            email="user@test.com",
            display_name="Test User",
            initials="TU",
            is_admin=False,
            is_skipper=False,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "user@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.get("/")
        html = resp.data.decode()
        assert "avatar-icon" in html
        assert "TU</a>" in html

    @patch(
        "app.storage.get_file_url",
        return_value="https://s3.example.com/navbar.jpg",
    )
    def test_navbar_prefers_uploaded_profile_picture(self, mock_url, app, client, db):
        app.config["BUCKET_NAME"] = "test-bucket"

        user = User(
            email="user@test.com",
            display_name="Test User",
            initials="TU",
            profile_image_key="profile-images/user.jpg",
            is_admin=False,
            is_skipper=False,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "user@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.get("/")
        html = resp.data.decode()
        assert "https://s3.example.com/navbar.jpg" in html
        assert "avatar-photo" in html
        mock_url.assert_called()


class TestViewProfileImage:
    @patch("app.storage.get_file_url", return_value="https://s3.example.com/pic.jpg")
    def test_view_profile_shows_image(self, mock_url, app, client, db):
        app.config["BUCKET_NAME"] = "test-bucket"

        viewer = User(
            email="viewer@test.com",
            display_name="Viewer",
            initials="VW",
        )
        viewer.set_password("password")
        db.session.add(viewer)

        target = User(
            email="target@test.com",
            display_name="Target User",
            initials="TG",
            profile_image_key="profile-images/target.jpg",
        )
        target.set_password("password")
        db.session.add(target)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "viewer@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.get(f"/crew/{target.id}")
        html = resp.data.decode()
        assert "https://s3.example.com/pic.jpg" in html
        assert "avatar-photo" in html
        assert "<svg" in html
        assert "Profile picture" in html

    def test_view_profile_no_image_no_img_tag(self, app, client, db):
        viewer = User(
            email="viewer@test.com",
            display_name="Viewer",
            initials="VW",
        )
        viewer.set_password("password")
        db.session.add(viewer)

        target = User(
            email="target@test.com",
            display_name="Target User",
            initials="TG",
        )
        target.set_password("password")
        db.session.add(target)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "viewer@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.get(f"/crew/{target.id}")
        html = resp.data.decode()
        assert "avatar-photo" not in html
        assert "avatar-icon" in html


class TestProfilePagePreview:
    @patch("app.storage.get_file_url", return_value="https://s3.example.com/pic.jpg")
    def test_profile_preview_shows_uploaded_picture(self, mock_url, app, client, db):
        """Profile page preview should show uploaded picture, not avatar SVG."""
        app.config["BUCKET_NAME"] = "test-bucket"

        user = User(
            email="picuser@test.com",
            display_name="Pic User",
            initials="PU",
            profile_image_key="profile-images/pic.jpg",
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "picuser@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.get("/profile")
        html = resp.data.decode()
        # The avatar-preview div should contain an img tag, not an SVG
        assert "avatar-photo" in html
        assert "https://s3.example.com/pic.jpg" in html

    def test_profile_preview_shows_avatar_when_no_picture(self, app, client, db):
        """Profile page preview should show avatar SVG when no picture uploaded."""
        user = User(
            email="nopic@test.com",
            display_name="No Pic",
            initials="NP",
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "nopic@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.get("/profile")
        html = resp.data.decode()
        assert "<svg" in html
        assert "avatar-icon" in html


class TestViewProfileEditButton:
    def test_edit_button_shown_on_own_profile(self, app, client, db):
        user = User(
            email="self@test.com",
            display_name="Self",
            initials="SE",
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "self@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.get(f"/crew/{user.id}")
        html = resp.data.decode()
        assert "Edit Profile" in html
        assert "/profile" in html

    def test_edit_button_hidden_on_other_profile(self, app, client, db):
        viewer = User(
            email="viewer@test.com",
            display_name="Viewer",
            initials="VW",
        )
        viewer.set_password("password")
        db.session.add(viewer)

        other = User(
            email="other@test.com",
            display_name="Other",
            initials="OT",
        )
        other.set_password("password")
        db.session.add(other)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "viewer@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.get(f"/crew/{other.id}")
        html = resp.data.decode()
        assert "Edit Profile" not in html


class TestPendingCrewProfile:
    def test_skipper_can_view_pending_crew_profile(self, app, db, client):
        skipper = User(
            email="skipper@test.com",
            display_name="Skipper",
            initials="SK",
            is_skipper=True,
        )
        skipper.set_password("password")
        db.session.add(skipper)

        pending = User(
            email="pending@test.com",
            display_name="Pending Crew",
            initials="PC",
            password_hash="pending",
            invite_token="abc123",
            invited_by=skipper.id,
            phone="555-1234",
        )
        db.session.add(pending)
        db.session.flush()
        skipper.crew_members.append(pending)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "skipper@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.get(f"/crew/{pending.id}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Pending Crew" in html
        assert "Pending Invite" in html
        assert "555-1234" in html

    def test_other_user_cannot_view_pending_crew_profile(self, app, db, client):
        skipper = User(
            email="skipper@test.com",
            display_name="Skipper",
            initials="SK",
            is_skipper=True,
        )
        skipper.set_password("password")
        db.session.add(skipper)

        other = User(
            email="other@test.com",
            display_name="Other",
            initials="OT",
        )
        other.set_password("password")
        db.session.add(other)

        pending = User(
            email="pending@test.com",
            display_name="Pending Crew",
            initials="PC",
            password_hash="pending",
            invite_token="abc123",
            invited_by=skipper.id,
        )
        db.session.add(pending)
        db.session.flush()
        skipper.crew_members.append(pending)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "other@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.get(f"/crew/{pending.id}", follow_redirects=True)
        html = resp.data.decode()
        assert "User not found" in html
