from io import BytesIO
from unittest.mock import patch

from app.models import User


class TestProfilePicture:
    @patch("app.auth.routes.storage.upload_file")
    def test_upload_profile_picture(self, mock_upload, app, client, db):
        app.config["BUCKET_NAME"] = "test-bucket"

        user = User(
            email="crew@test.com",
            display_name="Crew",
            initials="CR",
            is_admin=False,
            is_skipper=False,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "crew@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.post(
            "/profile",
            data={
                "display_name": "Crew",
                "initials": "CR",
                "email": "crew@test.com",
                "email_opt_in": "on",
                "profile_image": (BytesIO(b"fake-image"), "avatar.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        assert resp.status_code == 200
        db.session.refresh(user)
        assert user.profile_image_key is not None
        assert user.profile_image_key.startswith("profile-images/")
        assert user.profile_image_key.endswith(".png")
        mock_upload.assert_called_once()

    @patch("app.auth.routes.storage.upload_file")
    def test_rejects_invalid_profile_picture_extension(
        self, mock_upload, app, client, db
    ):
        app.config["BUCKET_NAME"] = "test-bucket"

        user = User(
            email="crew@test.com",
            display_name="Crew",
            initials="CR",
            is_admin=False,
            is_skipper=False,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "crew@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.post(
            "/profile",
            data={
                "display_name": "Crew",
                "initials": "CR",
                "email": "crew@test.com",
                "email_opt_in": "on",
                "profile_image": (BytesIO(b"not-an-image"), "avatar.txt"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        assert resp.status_code == 200
        assert (
            b"Profile picture must be a JPG, JPEG, PNG, GIF, or WEBP file." in resp.data
        )
        db.session.refresh(user)
        assert user.profile_image_key is None
        mock_upload.assert_not_called()

    @patch("app.auth.routes.storage.delete_file")
    def test_remove_profile_picture(self, mock_delete, app, client, db):
        user = User(
            email="crew@test.com",
            display_name="Crew",
            initials="CR",
            is_admin=False,
            is_skipper=False,
            profile_image_key="profile-images/old.png",
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "crew@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.post(
            "/profile",
            data={
                "display_name": "Crew",
                "initials": "CR",
                "email": "crew@test.com",
                "email_opt_in": "on",
                "remove_profile_image": "on",
            },
            follow_redirects=True,
        )

        assert resp.status_code == 200
        db.session.refresh(user)
        assert user.profile_image_key is None
        mock_delete.assert_called_once_with("profile-images/old.png")

    @patch("app.auth.routes.storage.upload_file")
    def test_rejects_oversized_profile_picture(self, mock_upload, app, client, db):
        app.config["BUCKET_NAME"] = "test-bucket"
        app.config["PROFILE_IMAGE_MAX_BYTES"] = 1 * 1024 * 1024
        app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024

        user = User(
            email="crew@test.com",
            display_name="Crew",
            initials="CR",
            is_admin=False,
            is_skipper=False,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "crew@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.post(
            "/profile",
            data={
                "display_name": "Crew",
                "initials": "CR",
                "email": "crew@test.com",
                "email_opt_in": "on",
                "profile_image": (BytesIO(b"x" * (2 * 1024 * 1024)), "avatar.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        assert resp.status_code == 200
        assert b"Profile picture must be 1 MB or smaller." in resp.data
        db.session.refresh(user)
        assert user.profile_image_key is None
        mock_upload.assert_not_called()

    @patch("app.auth.routes.storage.upload_file")
    def test_handles_request_entity_too_large_for_profile_upload(
        self, mock_upload, app, client, db
    ):
        app.config["BUCKET_NAME"] = "test-bucket"
        app.config["PROFILE_IMAGE_MAX_BYTES"] = 1 * 1024 * 1024
        app.config["MAX_CONTENT_LENGTH"] = 128

        user = User(
            email="crew@test.com",
            display_name="Crew",
            initials="CR",
            is_admin=False,
            is_skipper=False,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "crew@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.post(
            "/profile",
            data={
                "display_name": "Crew",
                "initials": "CR",
                "email": "crew@test.com",
                "profile_image": (BytesIO(b"x" * 2048), "avatar.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        assert resp.status_code == 200
        assert b"Profile picture must be 1 MB or smaller." in resp.data
        mock_upload.assert_not_called()
