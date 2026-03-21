"""Tests for AI usage logging, statistics, cost alerts, and the admin route."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.admin.ai_service import (INPUT_PRICE_PER_TOKEN,
                                  OUTPUT_PRICE_PER_TOKEN,
                                  _check_and_send_cost_alert, _log_ai_usage)
from app.admin.ai_stats import (check_cost_threshold, get_ai_usage_stats,
                                get_monthly_cost_limit)
from app.models import AIUsageLog, SiteSetting

# --- AIUsageLog Model ---


class TestAIUsageLogModel:
    def test_create_entry(self, app, db):
        with app.app_context():
            entry = AIUsageLog(
                function_name="extract_regattas",
                model="claude-sonnet-4-20250514",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0105,
            )
            db.session.add(entry)
            db.session.commit()

            saved = AIUsageLog.query.first()
            assert saved.function_name == "extract_regattas"
            assert saved.model == "claude-sonnet-4-20250514"
            assert saved.input_tokens == 1000
            assert saved.output_tokens == 500
            assert saved.cost_usd == pytest.approx(0.0105)
            assert saved.created_at is not None


# --- _log_ai_usage ---


class TestLogAIUsage:
    def test_logs_usage_correctly(self, app, db):
        with app.app_context():
            mock_msg = MagicMock()
            mock_msg.usage.input_tokens = 2000
            mock_msg.usage.output_tokens = 1000

            _log_ai_usage("extract_regattas", "claude-sonnet-4-20250514", mock_msg)

            entry = AIUsageLog.query.first()
            assert entry is not None
            assert entry.function_name == "extract_regattas"
            assert entry.input_tokens == 2000
            assert entry.output_tokens == 1000
            expected_cost = (2000 * INPUT_PRICE_PER_TOKEN) + (
                1000 * OUTPUT_PRICE_PER_TOKEN
            )
            assert entry.cost_usd == pytest.approx(expected_cost)

    def test_db_error_does_not_propagate(self, app, db):
        """Logging failures must never break AI operations."""
        with app.app_context():
            mock_msg = MagicMock()
            mock_msg.usage.input_tokens = 100
            mock_msg.usage.output_tokens = 50

            with patch(
                "app.admin.ai_service.db.session.commit",
                side_effect=Exception("DB down"),
            ):
                # Should not raise
                _log_ai_usage("extract_regattas", "test-model", mock_msg)

            # No entry saved due to error
            assert AIUsageLog.query.count() == 0


# --- Integration: AI functions log usage ---


class TestAIFunctionLogging:
    @patch("app.admin.ai_service.anthropic.Anthropic")
    def test_extract_regattas_logs_usage(self, mock_cls, app, db):
        from app.admin.ai_service import extract_regattas

        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='[{"name": "Test"}]')]
        mock_msg.usage.input_tokens = 500
        mock_msg.usage.output_tokens = 200
        mock_client.messages.create.return_value = mock_msg

        with app.app_context():
            extract_regattas("content", 2026)
            entry = AIUsageLog.query.first()
            assert entry is not None
            assert entry.function_name == "extract_regattas"

    @patch("app.admin.ai_service.anthropic.Anthropic")
    def test_discover_documents_logs_usage(self, mock_cls, app, db):
        from app.admin.ai_service import discover_documents

        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="[]")]
        mock_msg.usage.input_tokens = 300
        mock_msg.usage.output_tokens = 100
        mock_client.messages.create.return_value = mock_msg

        with app.app_context():
            discover_documents("content", "Test", "http://example.com")
            entry = AIUsageLog.query.first()
            assert entry is not None
            assert entry.function_name == "discover_documents"

    @patch("app.admin.ai_service.anthropic.Anthropic")
    def test_discover_documents_deep_logs_usage(self, mock_cls, app, db):
        from app.admin.ai_service import discover_documents_deep

        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="[]")]
        mock_msg.usage.input_tokens = 400
        mock_msg.usage.output_tokens = 150
        mock_client.messages.create.return_value = mock_msg

        with app.app_context():
            discover_documents_deep("content", "Test", "http://example.com")
            entry = AIUsageLog.query.first()
            assert entry is not None
            assert entry.function_name == "discover_documents_deep"


# --- Stats helpers ---


class TestGetMonthlyLimit:
    def test_default_value(self, app, db):
        with app.app_context():
            assert get_monthly_cost_limit() == 20.00

    def test_reads_from_site_setting(self, app, db):
        with app.app_context():
            db.session.add(SiteSetting(key="ai_monthly_cost_limit", value="50.00"))
            db.session.commit()
            assert get_monthly_cost_limit() == 50.00

    def test_invalid_value_returns_default(self, app, db):
        with app.app_context():
            db.session.add(SiteSetting(key="ai_monthly_cost_limit", value="abc"))
            db.session.commit()
            assert get_monthly_cost_limit() == 20.00


class TestGetAIUsageStats:
    def test_empty_stats_returns_zeros(self, app, db):
        with app.app_context():
            stats = get_ai_usage_stats()
            assert stats["today_cost"] == 0.0
            assert stats["month_cost"] == 0.0
            assert stats["all_time_cost"] == 0.0
            assert stats["today_calls"] == 0
            assert stats["month_calls"] == 0
            assert stats["all_time_calls"] == 0
            assert stats["month_input_tokens"] == 0
            assert stats["month_output_tokens"] == 0
            assert stats["by_function"] == []
            assert stats["budget_pct"] == 0.0

    def test_aggregation_with_data(self, app, db):
        with app.app_context():
            now = datetime.now(timezone.utc)
            entry1 = AIUsageLog(
                function_name="extract_regattas",
                model="test-model",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.01,
                created_at=now,
            )
            entry2 = AIUsageLog(
                function_name="discover_documents",
                model="test-model",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.02,
                created_at=now,
            )
            db.session.add_all([entry1, entry2])
            db.session.commit()

            stats = get_ai_usage_stats()
            assert stats["today_cost"] == pytest.approx(0.03)
            assert stats["month_cost"] == pytest.approx(0.03)
            assert stats["all_time_cost"] == pytest.approx(0.03)
            assert stats["today_calls"] == 2
            assert stats["month_calls"] == 2
            assert stats["all_time_calls"] == 2
            assert stats["month_input_tokens"] == 3000
            assert stats["month_output_tokens"] == 1500
            assert len(stats["by_function"]) == 2

    def test_budget_pct_calculation(self, app, db):
        with app.app_context():
            db.session.add(SiteSetting(key="ai_monthly_cost_limit", value="10.00"))
            db.session.add(
                AIUsageLog(
                    function_name="test",
                    model="m",
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=5.00,
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.session.commit()

            stats = get_ai_usage_stats()
            assert stats["budget_pct"] == pytest.approx(50.0)


# --- check_cost_threshold ---


class TestCheckCostThreshold:
    def test_below_threshold_returns_false(self, app, db):
        with app.app_context():
            # $1 of $20 limit = 5% — well below 80%
            db.session.add(
                AIUsageLog(
                    function_name="test",
                    model="m",
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=1.00,
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.session.commit()
            assert check_cost_threshold() is False

    def test_at_threshold_returns_true(self, app, db):
        with app.app_context():
            # $16 of $20 limit = 80%
            db.session.add(
                AIUsageLog(
                    function_name="test",
                    model="m",
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=16.00,
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.session.commit()
            assert check_cost_threshold() is True

    def test_already_alerted_returns_false(self, app, db):
        with app.app_context():
            now = datetime.now(timezone.utc)
            db.session.add(
                AIUsageLog(
                    function_name="test",
                    model="m",
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=16.00,
                    created_at=now,
                )
            )
            db.session.add(
                SiteSetting(
                    key="ai_cost_alert_sent_month",
                    value=now.strftime("%Y-%m"),
                )
            )
            db.session.commit()
            assert check_cost_threshold() is False


# --- Route tests ---


class TestAIStatsRoute:
    def test_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/admin/ai-stats")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_non_admin_denied(self, app, db, client):
        from app.models import User

        with app.app_context():
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

        client.post("/login", data={"email": "crew@test.com", "password": "password"})
        resp = client.get("/admin/ai-stats", follow_redirects=True)
        assert b"Access denied" in resp.data

    def test_admin_sees_page(self, logged_in_client):
        resp = logged_in_client.get("/admin/ai-stats")
        assert resp.status_code == 200
        assert b"AI Statistics" in resp.data
        assert b"Monthly Budget" in resp.data

    def test_post_updates_cost_limit(self, logged_in_client, app, db):
        resp = logged_in_client.post(
            "/admin/ai-stats",
            data={"cost_limit": "35.00"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"35.00" in resp.data

        with app.app_context():
            setting = SiteSetting.query.filter_by(key="ai_monthly_cost_limit").first()
            assert setting is not None
            assert setting.value == "35.0"

    def test_post_invalid_limit_shows_error(self, logged_in_client):
        resp = logged_in_client.post(
            "/admin/ai-stats",
            data={"cost_limit": "abc"},
            follow_redirects=True,
        )
        assert b"Invalid cost limit" in resp.data


# --- Alert email tests ---


class TestCostAlert:
    @patch("app.admin.email_service._send_via_ses")
    @patch("app.admin.email_service.load_email_settings")
    def test_alert_sent_at_threshold(self, mock_settings, mock_send, app, db):
        mock_settings.return_value = {"ses_sender": "admin@test.com"}

        with app.app_context():
            # Create usage at 80% of $20 limit
            db.session.add(
                AIUsageLog(
                    function_name="test",
                    model="m",
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=16.00,
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.session.commit()

            _check_and_send_cost_alert()

            mock_send.assert_called_once()
            call_kwargs = mock_send.call_args
            assert "80%" in call_kwargs.kwargs.get(
                "subject", call_kwargs[1].get("subject", "")
            ) or "80%" in str(call_kwargs)

    @patch("app.admin.email_service._send_via_ses")
    @patch("app.admin.email_service.load_email_settings")
    def test_alert_not_sent_twice(self, mock_settings, mock_send, app, db):
        mock_settings.return_value = {"ses_sender": "admin@test.com"}

        with app.app_context():
            now = datetime.now(timezone.utc)
            db.session.add(
                AIUsageLog(
                    function_name="test",
                    model="m",
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=16.00,
                    created_at=now,
                )
            )
            db.session.add(
                SiteSetting(
                    key="ai_cost_alert_sent_month",
                    value=now.strftime("%Y-%m"),
                )
            )
            db.session.commit()

            _check_and_send_cost_alert()
            mock_send.assert_not_called()

    @patch("app.admin.email_service._send_via_ses")
    @patch("app.admin.email_service.load_email_settings")
    def test_alert_below_threshold_not_sent(self, mock_settings, mock_send, app, db):
        mock_settings.return_value = {"ses_sender": "admin@test.com"}

        with app.app_context():
            db.session.add(
                AIUsageLog(
                    function_name="test",
                    model="m",
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=1.00,
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.session.commit()

            _check_and_send_cost_alert()
            mock_send.assert_not_called()
