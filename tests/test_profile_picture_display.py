"""Tests for profile picture display in navbar and profile pages (#69)."""

from unittest.mock import patch

from app.models import User


class TestNavbarProfileImage:
    @patch("app.storage.get_file_url", return_value="https://s3.example.com/pic.jpg")
    def test_navbar_shows_profile_image_when_set(self, mock_url, app, client, db):
        app.config["BUCKET_NAME"] = "test-bucket"

        user = User(
            email="user@test.com",
            display_name="Test User",
            initials="TU",
            is_admin=False,
            is_skipper=False,
            profile_image_key="profile-images/pic.jpg",
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
        assert "nav-avatar-img" in html
        assert 'alt="TU"' in html

    def test_navbar_shows_initials_when_no_image(self, app, client, db):
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
        assert "nav-avatar-img" not in html
        assert ">TU</a>" in html


class TestViewProfileImage:
    @patch(
        "app.auth.routes.storage.get_file_url",
        return_value="https://s3.example.com/pic.jpg",
    )
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
        assert 'alt="Target User"' in html

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
        assert "rounded-circle" not in html
