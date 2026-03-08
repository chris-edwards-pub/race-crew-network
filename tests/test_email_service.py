"""Tests for email service (SES integration)."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.admin.email_service import (generate_unsubscribe_token,
                                     generate_unsubscribe_url,
                                     is_email_configured, load_email_settings,
                                     send_email, verify_unsubscribe_token)
from app.models import SiteSetting, User


class TestLoadEmailSettings:
    def test_returns_defaults_when_empty(self, app, db):
        settings = load_email_settings()
        assert settings["ses_sender"] == ""
        assert settings["ses_sender_to"] == ""
        assert settings["ses_region"] == "us-east-1"

    def test_loads_stored_settings(self, app, db):
        db.session.add(SiteSetting(key="ses_sender", value="test@example.com"))
        db.session.add(SiteSetting(key="ses_sender_to", value="admin@example.com"))
        db.session.add(SiteSetting(key="ses_region", value="us-west-2"))
        db.session.commit()

        settings = load_email_settings()
        assert settings["ses_sender"] == "test@example.com"
        assert settings["ses_sender_to"] == "admin@example.com"
        assert settings["ses_region"] == "us-west-2"


class TestIsEmailConfigured:
    def test_false_when_no_sender(self, app, db):
        assert is_email_configured() is False

    def test_false_when_sender_empty(self, app, db):
        db.session.add(SiteSetting(key="ses_sender", value=""))
        db.session.commit()
        assert is_email_configured() is False

    def test_false_when_sender_whitespace(self, app, db):
        db.session.add(SiteSetting(key="ses_sender", value="   "))
        db.session.commit()
        assert is_email_configured() is False

    def test_true_when_sender_set(self, app, db):
        db.session.add(SiteSetting(key="ses_sender", value="noreply@example.com"))
        db.session.commit()
        assert is_email_configured() is True


class TestUnsubscribeToken:
    def test_generate_and_verify(self, app):
        token = generate_unsubscribe_token("user@example.com")
        assert isinstance(token, str)
        assert len(token) == 64  # SHA-256 hex digest

    def test_verify_valid_token(self, app):
        token = generate_unsubscribe_token("user@example.com")
        assert verify_unsubscribe_token("user@example.com", token) is True

    def test_verify_invalid_token(self, app):
        assert verify_unsubscribe_token("user@example.com", "badtoken") is False

    def test_case_insensitive_email(self, app):
        token = generate_unsubscribe_token("User@Example.COM")
        assert verify_unsubscribe_token("user@example.com", token) is True

    def test_different_emails_different_tokens(self, app):
        token1 = generate_unsubscribe_token("user1@example.com")
        token2 = generate_unsubscribe_token("user2@example.com")
        assert token1 != token2

    def test_generate_unsubscribe_url(self, app):
        url = generate_unsubscribe_url("user@example.com")
        assert "/unsubscribe" in url
        assert "email=user%40example.com" in url or "email=user@example.com" in url
        assert "token=" in url


class TestSendEmail:
    def test_raises_when_not_configured(self, app, db):
        with pytest.raises(ValueError, match="not configured"):
            send_email("to@example.com", "Subject", "Body")

    @patch("app.admin.email_service._get_ses_client")
    def test_sends_raw_email(self, mock_get_client, app, db):
        db.session.add(SiteSetting(key="ses_sender", value="from@example.com"))
        db.session.commit()

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        send_email("to@example.com", "Test Subject", "Text body")

        mock_client.send_raw_email.assert_called_once()
        call_kwargs = mock_client.send_raw_email.call_args[1]
        assert call_kwargs["Source"] == "from@example.com"
        assert call_kwargs["Destinations"] == ["to@example.com"]
        raw_data = call_kwargs["RawMessage"]["Data"]
        assert "List-Unsubscribe:" in raw_data
        assert "List-Unsubscribe-Post:" in raw_data
        assert "Test Subject" in raw_data

    @patch("app.admin.email_service._get_ses_client")
    def test_sends_html_with_footer(self, mock_get_client, app, db):
        import base64

        db.session.add(SiteSetting(key="ses_sender", value="from@example.com"))
        db.session.commit()

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        send_email("to@example.com", "Subject", "Text body", body_html="<p>HTML</p>")

        raw_data = mock_client.send_raw_email.call_args[1]["RawMessage"]["Data"]
        # HTML body is base64-encoded in the MIME message; decode to verify
        assert "text/html" in raw_data
        # Extract and decode the base64 HTML part
        parts = raw_data.split("text/html")
        b64_content = parts[1].split("\n\n", 1)[1].split("\n--")[0].strip()
        decoded_html = base64.b64decode(b64_content).decode("utf-8")
        assert "<p>HTML</p>" in decoded_html
        assert "Unsubscribe" in decoded_html

    @patch("app.admin.email_service._get_ses_client")
    def test_uses_configured_region(self, mock_get_client, app, db):
        db.session.add(SiteSetting(key="ses_sender", value="from@example.com"))
        db.session.add(SiteSetting(key="ses_region", value="eu-west-1"))
        db.session.commit()

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        send_email("to@example.com", "Subject", "Body")

        mock_get_client.assert_called_once_with("eu-west-1")

    @patch("app.admin.email_service._get_ses_client")
    def test_propagates_client_error(self, mock_get_client, app, db):
        db.session.add(SiteSetting(key="ses_sender", value="from@example.com"))
        db.session.commit()

        mock_client = MagicMock()
        mock_client.send_raw_email.side_effect = ClientError(
            {
                "Error": {
                    "Code": "MessageRejected",
                    "Message": "Email address not verified.",
                }
            },
            "SendRawEmail",
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(ClientError):
            send_email("to@example.com", "Subject", "Body")

    @patch("app.admin.email_service._get_ses_client")
    def test_skips_opted_out_user(self, mock_get_client, app, db):
        user = User(
            email="optout@example.com",
            display_name="Opted Out",
            initials="OO",
            email_opt_in=False,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.add(SiteSetting(key="ses_sender", value="from@example.com"))
        db.session.commit()

        send_email("optout@example.com", "Subject", "Body")

        mock_get_client.return_value.send_raw_email.assert_not_called()

    @patch("app.admin.email_service._get_ses_client")
    def test_sends_to_opted_in_user(self, mock_get_client, app, db):
        user = User(
            email="optin@example.com",
            display_name="Opted In",
            initials="OI",
            email_opt_in=True,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.add(SiteSetting(key="ses_sender", value="from@example.com"))
        db.session.commit()

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        send_email("optin@example.com", "Subject", "Body")

        mock_client.send_raw_email.assert_called_once()
