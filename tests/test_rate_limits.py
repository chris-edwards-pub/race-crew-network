"""Tests for email rate limiting, queue management, and email statistics."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models import EmailQueue, NotificationLog, SiteSetting, User

# --- Helpers ---


def _create_admin(db_session):
    """Create and return an admin user."""
    user = User(
        email="admin@test.com",
        display_name="Admin",
        initials="AD",
        is_admin=True,
        is_skipper=True,
    )
    user.set_password("password")
    db_session.session.add(user)
    db_session.session.commit()
    return user


def _set_rate_limit(db_session, value):
    """Set the rate limit site setting."""
    setting = SiteSetting.query.filter_by(key="rate_limit_emails_per_hour").first()
    if setting:
        setting.value = str(value)
    else:
        setting = SiteSetting(key="rate_limit_emails_per_hour", value=str(value))
        db_session.session.add(setting)
    db_session.session.commit()


def _create_notification_logs(db_session, user_id, count, minutes_ago=0):
    """Create notification log entries in the recent past."""
    for _ in range(count):
        log = NotificationLog(
            notification_type="notify_crew",
            user_id=user_id,
            sent_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        )
        db_session.session.add(log)
    db_session.session.commit()


def _login_admin(client):
    """Log in as admin."""
    client.post(
        "/login",
        data={"email": "admin@test.com", "password": "password"},
        follow_redirects=True,
    )


# --- TestEmailRateLimit ---


class TestEmailRateLimit:
    def test_email_sent_when_under_limit(self, app, db):
        """Normal send goes through when under rate limit."""
        _create_admin(db)
        _set_rate_limit(db, 50)

        with app.app_context():
            from app.notifications.rate_limits import is_within_email_rate_limit

            assert is_within_email_rate_limit() is True

    def test_email_queued_when_over_limit(self, app, db):
        """Over-limit email saved to EmailQueue."""
        admin = _create_admin(db)
        _set_rate_limit(db, 2)
        _create_notification_logs(db, admin.id, 3)

        with app.app_context():
            from app.notifications.rate_limits import (
                is_within_email_rate_limit,
                queue_email,
            )

            assert is_within_email_rate_limit() is False

            entry = queue_email("test@example.com", "Test", "Body text")
            assert entry.status == "pending"
            assert entry.to_email == "test@example.com"

            queued = EmailQueue.query.filter_by(status="pending").count()
            assert queued == 1

    @patch("app.admin.email_service._send_via_ses")
    def test_admin_alerted_on_rate_limit_hit(self, mock_send, app, db):
        """Alert sent via _send_via_ses() directly when rate limit hit."""
        _create_admin(db)

        with app.app_context():
            from app.notifications.rate_limits import send_rate_limit_alert

            send_rate_limit_alert()
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "admin@test.com"
            assert "Rate Limit" in call_args[0][1]

    @patch("app.admin.email_service._send_via_ses")
    def test_admin_alert_deduped_within_hour(self, mock_send, app, db):
        """No duplicate alerts within one hour."""
        _create_admin(db)

        with app.app_context():
            from app.notifications.rate_limits import send_rate_limit_alert

            send_rate_limit_alert()
            assert mock_send.call_count == 1

            # Second call should be deduped
            send_rate_limit_alert()
            assert mock_send.call_count == 1

    @patch("app.admin.email_service._send_via_ses")
    def test_admin_alert_bypasses_rate_limit(self, mock_send, app, db):
        """Alert never queued — uses _send_via_ses() directly."""
        admin = _create_admin(db)
        _set_rate_limit(db, 1)
        _create_notification_logs(db, admin.id, 5)

        with app.app_context():
            from app.notifications.rate_limits import (
                is_within_email_rate_limit,
                send_rate_limit_alert,
            )

            assert is_within_email_rate_limit() is False
            send_rate_limit_alert()
            mock_send.assert_called_once()

            # Alert should NOT be in the queue
            queued = EmailQueue.query.filter_by(status="pending").count()
            assert queued == 0

    def test_rate_limit_configurable(self, app, db):
        """SiteSetting overrides default."""
        _create_admin(db)

        with app.app_context():
            from app.notifications.rate_limits import get_hourly_email_limit

            assert get_hourly_email_limit() == 50  # default

            _set_rate_limit(db, 100)
            assert get_hourly_email_limit() == 100

    def test_send_email_queues_when_over_limit(self, app, db):
        """Integration: send_email() queues when rate limit exceeded."""
        admin = _create_admin(db)
        _set_rate_limit(db, 2)
        _create_notification_logs(db, admin.id, 3)

        # Create a non-opted-out user as recipient
        recipient = User(
            email="crew@test.com",
            display_name="Crew",
            initials="CR",
            email_opt_in=True,
        )
        recipient.set_password("password")
        db.session.add(recipient)
        db.session.commit()

        with app.app_context():
            with patch("app.admin.email_service._send_via_ses"):
                from app.admin.email_service import send_email

                send_email("crew@test.com", "Subject", "Body")

            queued = EmailQueue.query.filter_by(status="pending").count()
            assert queued == 1


# --- TestEmailQueue ---


class TestEmailQueue:
    @patch("app.admin.email_service._send_via_ses")
    def test_queue_processor_sends_pending(self, mock_send, app, db):
        """Drains queue, marks entries as sent."""
        _create_admin(db)

        with app.app_context():
            from app.notifications.rate_limits import process_email_queue, queue_email

            queue_email("a@test.com", "Sub A", "Body A")
            queue_email("b@test.com", "Sub B", "Body B")

            result = process_email_queue()
            assert result["sent"] == 2
            assert result["remaining"] == 0

            sent_count = EmailQueue.query.filter_by(status="sent").count()
            assert sent_count == 2

    @patch("app.admin.email_service._send_via_ses")
    def test_queue_processor_respects_rate_limit(self, mock_send, app, db):
        """Stops at hourly cap."""
        admin = _create_admin(db)
        _set_rate_limit(db, 2)
        _create_notification_logs(db, admin.id, 1)

        with app.app_context():
            from app.notifications.rate_limits import process_email_queue, queue_email

            queue_email("a@test.com", "Sub A", "Body A")
            queue_email("b@test.com", "Sub B", "Body B")
            queue_email("c@test.com", "Sub C", "Body C")

            result = process_email_queue()
            # Only 1 remaining capacity (limit=2, sent_this_hour=1)
            assert result["sent"] == 1
            assert result["remaining"] == 2

    @patch("app.admin.email_service._send_via_ses")
    def test_queue_processor_marks_failures(self, mock_send, app, db):
        """SES error marks entry as failed."""
        _create_admin(db)
        mock_send.side_effect = Exception("SES error")

        with app.app_context():
            from app.notifications.rate_limits import process_email_queue, queue_email

            queue_email("fail@test.com", "Sub", "Body")
            result = process_email_queue()
            assert result["sent"] == 0

            failed = EmailQueue.query.filter_by(status="failed").first()
            assert failed is not None
            assert "SES error" in failed.error_message

    def test_clear_queue_removes_pending(self, app, db):
        """Preserves sent/failed records."""
        _create_admin(db)

        with app.app_context():
            from app.notifications.rate_limits import clear_email_queue

            # Add pending, sent, and failed entries
            db.session.add(
                EmailQueue(
                    to_email="a@test.com", subject="A", body_text="A", status="pending"
                )
            )
            db.session.add(
                EmailQueue(
                    to_email="b@test.com", subject="B", body_text="B", status="sent"
                )
            )
            db.session.add(
                EmailQueue(
                    to_email="c@test.com", subject="C", body_text="C", status="failed"
                )
            )
            db.session.commit()

            count = clear_email_queue()
            assert count == 1

            remaining = EmailQueue.query.count()
            assert remaining == 2  # sent + failed preserved

    def test_queue_api_requires_token(self, app, db, client):
        """No token returns 403."""
        with app.app_context():
            resp = client.get("/admin/api/process-email-queue")
            assert resp.status_code == 403

            resp = client.get("/admin/api/process-email-queue?token=wrong")
            assert resp.status_code == 403

    @patch(
        "app.notifications.rate_limits.process_email_queue",
        return_value={"sent": 0, "remaining": 0},
    )
    def test_queue_api_with_valid_token(self, mock_process, app, db, client):
        """Valid token processes queue."""
        _create_admin(db)
        setting = SiteSetting(key="reminder_api_token", value="test-token-123")
        db.session.add(setting)
        db.session.commit()

        with app.app_context():
            resp = client.get("/admin/api/process-email-queue?token=test-token-123")
            assert resp.status_code == 200
            mock_process.assert_called_once()

    def test_queue_cli_command(self, app):
        """flask process-email-queue command exists and runs."""
        runner = app.test_cli_runner()
        with patch(
            "app.notifications.rate_limits.process_email_queue",
            return_value={"sent": 0, "remaining": 0},
        ):
            result = runner.invoke(args=["process-email-queue"])
            assert result.exit_code == 0
            assert '"sent"' in result.output

    def test_clear_queue_requires_admin(self, app, db, client):
        """Non-admin cannot clear queue."""
        # Create non-admin user
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
        resp = client.post("/admin/email-queue/clear", follow_redirects=True)
        assert b"Access denied" in resp.data


# --- TestEmailStats ---


class TestEmailStats:
    def test_stats_page_requires_admin(self, app, db, client):
        """Non-admin redirected."""
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
        resp = client.get("/admin/email-stats", follow_redirects=True)
        assert b"Access denied" in resp.data

    @patch("app.admin.routes.get_ses_cost", return_value=None)
    @patch("app.admin.routes.get_ses_statistics", return_value=None)
    @patch(
        "app.admin.routes.get_ses_quota",
        return_value={"max_24hr_send": 200, "max_send_rate": 1, "sent_last_24hrs": 10},
    )
    def test_stats_page_renders_with_ses_data(
        self, mock_quota, mock_stats, mock_cost, app, db, client
    ):
        """Mocked SES quota/stats displayed."""
        _create_admin(db)
        _login_admin(client)

        resp = client.get("/admin/email-stats")
        assert resp.status_code == 200
        assert b"200" in resp.data  # max_24hr_send
        assert b"Email Statistics" in resp.data

    @patch("app.admin.routes.get_ses_cost", return_value=None)
    @patch("app.admin.routes.get_ses_statistics", return_value=None)
    @patch("app.admin.routes.get_ses_quota", return_value=None)
    def test_stats_page_graceful_without_cost_explorer(
        self, mock_quota, mock_stats, mock_cost, app, db, client
    ):
        """Shows fallback message when ce:GetCostAndUsage denied."""
        _create_admin(db)
        _login_admin(client)

        resp = client.get("/admin/email-stats")
        assert resp.status_code == 200
        assert b"ce:GetCostAndUsage" in resp.data

    @patch("app.admin.routes.get_ses_cost", return_value=None)
    @patch("app.admin.routes.get_ses_statistics", return_value=None)
    @patch("app.admin.routes.get_ses_quota", return_value=None)
    def test_stats_page_shows_queue_status(
        self, mock_quota, mock_stats, mock_cost, app, db, client
    ):
        """Pending/sent/failed counts shown."""
        _create_admin(db)
        _login_admin(client)

        db.session.add(
            EmailQueue(
                to_email="a@test.com", subject="A", body_text="A", status="pending"
            )
        )
        db.session.add(
            EmailQueue(to_email="b@test.com", subject="B", body_text="B", status="sent")
        )
        db.session.commit()

        resp = client.get("/admin/email-stats")
        assert resp.status_code == 200
        assert b"Queue Status" in resp.data

    @patch("app.admin.routes.get_ses_cost", return_value=None)
    @patch("app.admin.routes.get_ses_statistics", return_value=None)
    @patch("app.admin.routes.get_ses_quota", return_value=None)
    def test_stats_page_shows_rate_limit_status(
        self, mock_quota, mock_stats, mock_cost, app, db, client
    ):
        """Current hour usage shown."""
        _create_admin(db)
        _login_admin(client)
        _set_rate_limit(db, 50)

        resp = client.get("/admin/email-stats")
        assert resp.status_code == 200
        assert b"Rate Limit Status" in resp.data
        assert b"50" in resp.data  # the limit value


# --- TestRateLimitSettings ---


class TestRateLimitSettings:
    def test_admin_can_view_setting(self, app, db, client):
        """Default (50) shown on email settings page."""
        _create_admin(db)
        _login_admin(client)

        resp = client.get("/admin/settings/email")
        assert resp.status_code == 200
        assert b"Rate Limiting" in resp.data
        assert b'value="50"' in resp.data

    def test_admin_can_save_setting(self, logged_in_client):
        """POST persists rate limit setting."""
        resp = logged_in_client.post(
            "/admin/settings/email",
            data={
                "ses_sender": "test@example.com",
                "ses_region": "us-east-1",
                "rate_limit_emails_per_hour": "100",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Email settings updated" in resp.data

        saved = SiteSetting.query.filter_by(key="rate_limit_emails_per_hour").first()
        assert saved is not None
        assert saved.value == "100"

    def test_rate_limit_clamped_to_range(self, logged_in_client):
        """Values outside 1-500 are clamped."""
        logged_in_client.post(
            "/admin/settings/email",
            data={"rate_limit_emails_per_hour": "1000"},
            follow_redirects=True,
        )

        saved = SiteSetting.query.filter_by(key="rate_limit_emails_per_hour").first()
        assert saved is not None
        assert saved.value == "500"
