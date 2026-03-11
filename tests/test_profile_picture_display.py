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
