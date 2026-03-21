"""Tests for the help page and contact form."""

import time
from unittest.mock import patch

from app.models import SiteSetting


class TestHelpPage:
    def test_help_page_accessible_anonymous(self, client):
        resp = client.get("/help")
        assert resp.status_code == 200
        assert b"Help" in resp.data

    def test_help_page_accessible_logged_in(self, logged_in_client):
        resp = logged_in_client.get("/help")
        assert resp.status_code == 200
        assert b"Help" in resp.data

    def test_help_page_contains_sections(self, client):
        resp = client.get("/help")
        html = resp.data.decode()
        assert "Getting Started" in html
        assert "How to Request Access" in html
        assert "Viewing the Schedule" in html
        assert "Calendar Subscription" in html
        assert "Documents" in html
        assert "Profile &amp; Notifications" in html
        assert "For Skippers" in html
        assert "For Developers" in html
        assert "Contact Support" in html

    def test_navbar_help_link_anonymous(self, client):
        resp = client.get("/help")
        html = resp.data.decode()
        assert 'href="/help"' in html

    def test_navbar_help_link_logged_in(self, logged_in_client):
        resp = logged_in_client.get("/help")
        html = resp.data.decode()
        assert 'href="/help"' in html


class TestContactForm:
    @patch("app.admin.email_service._send_via_ses")
    def test_contact_form_sends_email(self, mock_ses, client, db):
        # Configure SES sender
        db.session.add(SiteSetting(key="ses_sender", value="noreply@example.com"))
        db.session.add(SiteSetting(key="ses_sender_to", value="admin@example.com"))
        db.session.commit()

        ts = str(int(time.time()) - 5)  # 5 seconds ago
        resp = client.post(
            "/help/contact",
            data={
                "name": "Test User",
                "email": "test@example.com",
                "message": "Hello, need help!",
                "form_timestamp": ts,
            },
            follow_redirects=True,
        )

        assert resp.status_code == 200
        assert b"Your message has been sent" in resp.data
        mock_ses.assert_called_once()
        call_args = mock_ses.call_args
        assert call_args[0][0] == "admin@example.com"
        assert "[Contact Form]" in call_args[0][1]
        assert "Test User" in call_args[0][1]
        assert call_args[1]["reply_to"] == "test@example.com"

    @patch("app.admin.email_service._send_via_ses")
    def test_contact_form_honeypot_rejects(self, mock_ses, client):
        ts = str(int(time.time()) - 5)
        resp = client.post(
            "/help/contact",
            data={
                "name": "Bot",
                "email": "bot@spam.com",
                "message": "Buy stuff",
                "form_timestamp": ts,
                "website": "http://spam.com",  # honeypot filled
            },
            follow_redirects=True,
        )

        assert resp.status_code == 200
        mock_ses.assert_not_called()

    @patch("app.admin.email_service._send_via_ses")
    def test_contact_form_timestamp_rejects(self, mock_ses, client):
        ts = str(int(time.time()))  # submitted "right now" = too fast
        resp = client.post(
            "/help/contact",
            data={
                "name": "Bot",
                "email": "bot@spam.com",
                "message": "Spam",
                "form_timestamp": ts,
            },
            follow_redirects=True,
        )

        assert resp.status_code == 200
        mock_ses.assert_not_called()

    def test_contact_form_missing_fields(self, client):
        ts = str(int(time.time()) - 5)
        resp = client.post(
            "/help/contact",
            data={
                "name": "",
                "email": "test@example.com",
                "message": "Hello",
                "form_timestamp": ts,
            },
            follow_redirects=True,
        )

        assert resp.status_code == 200
        assert b"Please fill in all required fields" in resp.data

    def test_contact_form_no_email_configured(self, client):
        # No SiteSetting records → no sender configured → ValueError caught
        ts = str(int(time.time()) - 5)
        resp = client.post(
            "/help/contact",
            data={
                "name": "Test",
                "email": "test@example.com",
                "message": "Help!",
                "form_timestamp": ts,
            },
            follow_redirects=True,
        )

        assert resp.status_code == 200
        assert b"try again later" in resp.data

    @patch("app.admin.email_service._send_via_ses")
    def test_contact_form_falls_back_to_ses_sender(self, mock_ses, client, db):
        # Only ses_sender configured, no ses_sender_to
        db.session.add(SiteSetting(key="ses_sender", value="fallback@example.com"))
        db.session.commit()

        ts = str(int(time.time()) - 5)
        client.post(
            "/help/contact",
            data={
                "name": "Test",
                "email": "test@example.com",
                "message": "Hello",
                "form_timestamp": ts,
            },
            follow_redirects=True,
        )

        mock_ses.assert_called_once()
        assert mock_ses.call_args[0][0] == "fallback@example.com"
