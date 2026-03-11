from unittest.mock import MagicMock, patch

import pytest


class TestBackendSelection:
    """_use_s3() returns True when BUCKET_NAME is set, False otherwise."""

    def test_s3_when_bucket_name_set(self, app):
        with app.app_context():
            app.config["BUCKET_NAME"] = "my-bucket"
            from app.storage import _use_s3

            assert _use_s3() is True

    def test_local_when_bucket_name_empty(self, app):
        with app.app_context():
            app.config["BUCKET_NAME"] = ""
            from app.storage import _use_s3

            assert _use_s3() is False

    def test_local_when_bucket_name_missing(self, app):
        with app.app_context():
            app.config.pop("BUCKET_NAME", None)
            from app.storage import _use_s3

            assert _use_s3() is False


class TestLocalUpload:
    """upload_file() saves to disk when BUCKET_NAME is empty."""

    def test_creates_file_on_disk(self, app, tmp_path):
        with app.app_context():
            app.config["BUCKET_NAME"] = ""
            app.config["UPLOAD_FOLDER"] = str(tmp_path)
            from app.storage import upload_file

            fake_file = MagicMock()
            upload_file(fake_file, "test.txt")

            expected = tmp_path / "test.txt"
            fake_file.save.assert_called_once_with(expected)

    def test_creates_subdirectories(self, app, tmp_path):
        with app.app_context():
            app.config["BUCKET_NAME"] = ""
            app.config["UPLOAD_FOLDER"] = str(tmp_path)
            from app.storage import upload_file

            fake_file = MagicMock()
            upload_file(fake_file, "profile-images/abc.png")

            expected = tmp_path / "profile-images" / "abc.png"
            fake_file.save.assert_called_once_with(expected)
            assert (tmp_path / "profile-images").is_dir()

    def test_rejects_path_traversal(self, app, tmp_path):
        with app.app_context():
            app.config["BUCKET_NAME"] = ""
            app.config["UPLOAD_FOLDER"] = str(tmp_path)
            from app.storage import upload_file

            fake_file = MagicMock()
            with pytest.raises(ValueError, match="Invalid file path"):
                upload_file(fake_file, "../../../etc/passwd")


class TestLocalGetFileUrl:
    """get_file_url() returns a /uploads/... URL when BUCKET_NAME is empty."""

    def test_returns_upload_route_url(self, app):
        with app.app_context():
            app.config["BUCKET_NAME"] = ""
            from app.storage import get_file_url

            url = get_file_url("profile-images/abc.png")
            assert url.endswith("/uploads/profile-images/abc.png")


class TestLocalDeleteFile:
    """delete_file() removes file from disk when BUCKET_NAME is empty."""

    def test_deletes_existing_file(self, app, tmp_path):
        with app.app_context():
            app.config["BUCKET_NAME"] = ""
            app.config["UPLOAD_FOLDER"] = str(tmp_path)
            from app.storage import delete_file

            target = tmp_path / "test.txt"
            target.write_text("hello")
            assert target.exists()

            delete_file("test.txt")
            assert not target.exists()

    def test_no_error_on_missing_file(self, app, tmp_path):
        with app.app_context():
            app.config["BUCKET_NAME"] = ""
            app.config["UPLOAD_FOLDER"] = str(tmp_path)
            from app.storage import delete_file

            # Should not raise
            delete_file("nonexistent.txt")


class TestS3Backend:
    """S3 functions are called when BUCKET_NAME is set."""

    @patch("app.storage._get_client")
    def test_upload_uses_s3(self, mock_get_client, app):
        with app.app_context():
            app.config["BUCKET_NAME"] = "my-bucket"
            from app.storage import upload_file

            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            fake_file = MagicMock()
            upload_file(fake_file, "test.txt")

            mock_client.upload_fileobj.assert_called_once_with(
                fake_file, "my-bucket", "test.txt"
            )

    @patch("app.storage._get_client")
    def test_get_file_url_uses_s3(self, mock_get_client, app):
        with app.app_context():
            app.config["BUCKET_NAME"] = "my-bucket"
            from app.storage import get_file_url

            mock_client = MagicMock()
            mock_client.generate_presigned_url.return_value = (
                "https://s3.example.com/test.txt"
            )
            mock_get_client.return_value = mock_client

            url = get_file_url("test.txt")

            assert url == "https://s3.example.com/test.txt"
            mock_client.generate_presigned_url.assert_called_once()

    @patch("app.storage._get_client")
    def test_delete_uses_s3(self, mock_get_client, app):
        with app.app_context():
            app.config["BUCKET_NAME"] = "my-bucket"
            from app.storage import delete_file

            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            delete_file("test.txt")

            mock_client.delete_object.assert_called_once_with(
                Bucket="my-bucket", Key="test.txt"
            )


class TestServeRoute:
    """The /uploads/<path:filename> route serves local files."""

    def test_serves_file_when_logged_in(self, app, tmp_path, db):
        app.config["UPLOAD_FOLDER"] = str(tmp_path)
        target = tmp_path / "test.txt"
        target.write_text("file content")

        from app.models import User

        user = User(
            email="storage@test.com",
            display_name="Storage Tester",
            initials="ST",
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client = app.test_client()
        client.post(
            "/login",
            data={"email": "storage@test.com", "password": "password"},
            follow_redirects=True,
        )
        resp = client.get("/uploads/test.txt")
        assert resp.status_code == 200
        assert resp.data == b"file content"

    def test_redirects_anonymous_to_login(self, client):
        resp = client.get("/uploads/test.txt")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_404_for_missing_file(self, app, tmp_path, db):
        app.config["UPLOAD_FOLDER"] = str(tmp_path)

        from app.models import User

        user = User(
            email="storage404@test.com",
            display_name="Storage 404",
            initials="S4",
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client = app.test_client()
        client.post(
            "/login",
            data={"email": "storage404@test.com", "password": "password"},
            follow_redirects=True,
        )
        resp = client.get("/uploads/nonexistent.txt")
        assert resp.status_code == 404

    def test_serves_nested_path(self, app, tmp_path, db):
        app.config["UPLOAD_FOLDER"] = str(tmp_path)
        subdir = tmp_path / "profile-images"
        subdir.mkdir()
        target = subdir / "abc.png"
        target.write_bytes(b"\x89PNG")

        from app.models import User

        user = User(
            email="nested@test.com",
            display_name="Nested Tester",
            initials="NT",
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client = app.test_client()
        client.post(
            "/login",
            data={"email": "nested@test.com", "password": "password"},
            follow_redirects=True,
        )
        resp = client.get("/uploads/profile-images/abc.png")
        assert resp.status_code == 200
        assert resp.data == b"\x89PNG"
