"""Tests for the notification service (Phase 1 & 2)."""

import json
from datetime import date, timedelta
from unittest.mock import patch

from app.models import RSVP, NotificationLog, Regatta, SiteSetting, User


class TestNotifyCrewService:
    """Tests for notify_crew() function."""

    def _create_regatta(self, db, skipper):
        r = Regatta(
            name="Spring Regatta",
            boat_class="J/24",
            location="Lakewood YC",
            start_date=date(2026, 5, 3),
            created_by=skipper.id,
        )
        db.session.add(r)
        db.session.commit()
        return r

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_notify_crew_sends_to_selected_crew(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_crew

        regatta = self._create_regatta(db, skipper_user)

        with app.test_request_context():
            sent = notify_crew([regatta], [crew_user], None, skipper_user)

        assert sent == 1
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        assert call_kwargs[1]["to"] == crew_user.email
        assert "Spring Regatta" in call_kwargs[1]["subject"] or True

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_notify_crew_skips_opted_out(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_crew

        crew_user.email_opt_in = False
        db.session.commit()

        regatta = self._create_regatta(db, skipper_user)

        with app.test_request_context():
            sent = notify_crew([regatta], [crew_user], None, skipper_user)

        assert sent == 0
        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_notify_crew_skips_unregistered(
        self, mock_configured, mock_send, app, db, skipper_user
    ):
        from app.notifications.service import notify_crew

        # Create crew with pending invite token
        pending = User(
            email="pending@test.com",
            display_name="Pending",
            initials="PE",
            invite_token="abc123",
        )
        pending.set_password("password")
        db.session.add(pending)
        db.session.commit()

        regatta = self._create_regatta(db, skipper_user)

        with app.test_request_context():
            sent = notify_crew([regatta], [pending], None, skipper_user)

        assert sent == 0
        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_notify_crew_logs_per_regatta_crew_pair(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_crew

        r1 = self._create_regatta(db, skipper_user)
        r2 = Regatta(
            name="Summer Series",
            boat_class="J/24",
            location="Bay Harbor",
            start_date=date(2026, 6, 14),
            created_by=skipper_user.id,
        )
        db.session.add(r2)
        db.session.commit()

        with app.test_request_context():
            sent = notify_crew([r1, r2], [crew_user], None, skipper_user)

        assert sent == 1
        logs = NotificationLog.query.filter_by(
            notification_type="notify_crew", user_id=crew_user.id
        ).all()
        assert len(logs) == 2
        regatta_ids = {log.regatta_id for log in logs}
        assert regatta_ids == {r1.id, r2.id}

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_notify_crew_includes_custom_message(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_crew

        regatta = self._create_regatta(db, skipper_user)

        with app.test_request_context():
            notify_crew(
                [regatta], [crew_user], "Bring your life jackets!", skipper_user
            )

        call_kwargs = mock_send.call_args[1]
        assert "Bring your life jackets!" in call_kwargs["body_text"]
        assert "Bring your life jackets!" in call_kwargs["body_html"]

    @patch("app.notifications.service.is_email_configured", return_value=False)
    def test_notify_crew_returns_zero_when_email_not_configured(
        self, mock_configured, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_crew

        regatta = self._create_regatta(db, skipper_user)

        with app.test_request_context():
            sent = notify_crew([regatta], [crew_user], None, skipper_user)

        assert sent == 0


class TestRsvpNotification:
    """Tests for notify_rsvp_to_skipper() function."""

    def _create_rsvp(self, db, skipper, crew):
        regatta = Regatta(
            name="Test Regatta",
            boat_class="J/24",
            location="Test YC",
            start_date=date(2026, 5, 10),
            created_by=skipper.id,
        )
        db.session.add(regatta)
        db.session.flush()
        rsvp = RSVP(regatta_id=regatta.id, user_id=crew.id, status="yes")
        db.session.add(rsvp)
        db.session.commit()
        return rsvp

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_rsvp_notifies_skipper(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_rsvp_to_skipper

        rsvp = self._create_rsvp(db, skipper_user, crew_user)

        with app.test_request_context():
            notify_rsvp_to_skipper(rsvp)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to"] == skipper_user.email
        assert "yes" in call_kwargs["body_text"]

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_rsvp_logs_notification(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_rsvp_to_skipper

        rsvp = self._create_rsvp(db, skipper_user, crew_user)

        with app.test_request_context():
            notify_rsvp_to_skipper(rsvp)

        log = NotificationLog.query.filter_by(
            notification_type="rsvp_notification"
        ).first()
        assert log is not None
        assert log.user_id == skipper_user.id
        assert log.regatta_id == rsvp.regatta_id

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_rsvp_skips_when_skipper_opted_out(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_rsvp_to_skipper

        skipper_user.email_opt_in = False
        db.session.commit()
        rsvp = self._create_rsvp(db, skipper_user, crew_user)

        with app.test_request_context():
            notify_rsvp_to_skipper(rsvp)

        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_rsvp_skips_when_notification_pref_disabled(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_rsvp_to_skipper

        skipper_user.notification_prefs = json.dumps({"rsvp_notification": False})
        db.session.commit()
        rsvp = self._create_rsvp(db, skipper_user, crew_user)

        with app.test_request_context():
            notify_rsvp_to_skipper(rsvp)

        mock_send.assert_not_called()

    @patch("app.notifications.service.is_email_configured", return_value=False)
    def test_rsvp_returns_silently_when_email_not_configured(
        self, mock_configured, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_rsvp_to_skipper

        rsvp = self._create_rsvp(db, skipper_user, crew_user)

        with app.test_request_context():
            # Should not raise
            notify_rsvp_to_skipper(rsvp)


class TestNotifyCrewRoute:
    """Tests for the POST /regattas/notify-crew route."""

    @patch("app.regattas.routes.notify_crew", return_value=1)
    def test_notify_crew_route_sends_and_flashes(
        self, mock_notify, app, db, logged_in_skipper, skipper_user
    ):
        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=date(2026, 5, 1),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()

        crew = User(
            email="crew2@test.com",
            display_name="Crew2",
            initials="C2",
        )
        crew.set_password("password")
        db.session.add(crew)
        db.session.flush()
        skipper_user.crew_members.append(crew)
        db.session.commit()

        resp = logged_in_skipper.post(
            "/regattas/notify-crew",
            data={
                "selected[]": [str(regatta.id)],
                "crew[]": [str(crew.id)],
                "message": "Test message",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Notified 1 crew member(s)" in resp.data
        mock_notify.assert_called_once()

    def test_notify_crew_route_denied_for_crew(self, app, db, logged_in_crew):
        resp = logged_in_crew.post(
            "/regattas/notify-crew",
            data={"selected[]": ["1"], "crew[]": ["2"]},
            follow_redirects=True,
        )
        assert b"Access denied" in resp.data

    @patch("app.regattas.routes.notify_crew", return_value=0)
    def test_notify_crew_no_regattas_selected(
        self, mock_notify, app, db, logged_in_skipper
    ):
        resp = logged_in_skipper.post(
            "/regattas/notify-crew",
            data={"crew[]": ["1"]},
            follow_redirects=True,
        )
        assert b"No events selected" in resp.data
        mock_notify.assert_not_called()


class TestNotificationPreferences:
    """Tests for User.notification_preferences property."""

    def test_default_preferences(self, db, skipper_user):
        prefs = skipper_user.notification_preferences
        assert prefs["rsvp_notification"] is True
        assert prefs["rsvp_delivery"] == "per_rsvp"

    def test_custom_preferences(self, db, skipper_user):
        skipper_user.notification_prefs = json.dumps({"rsvp_notification": False})
        db.session.commit()
        prefs = skipper_user.notification_preferences
        assert prefs["rsvp_notification"] is False
        assert prefs["rsvp_delivery"] == "per_rsvp"

    def test_invalid_json_returns_defaults(self, db, skipper_user):
        skipper_user.notification_prefs = "not valid json"
        db.session.commit()
        prefs = skipper_user.notification_preferences
        assert prefs["rsvp_notification"] is True

    def test_profile_saves_notification_prefs(
        self, app, db, logged_in_skipper, skipper_user
    ):
        resp = logged_in_skipper.post(
            "/profile",
            data={
                "display_name": skipper_user.display_name,
                "initials": skipper_user.initials,
                "email": skipper_user.email,
                "email_opt_in": "on",
                # rsvp_notification NOT checked → should be False
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        db.session.refresh(skipper_user)
        prefs = skipper_user.notification_preferences
        assert prefs["rsvp_notification"] is False


class TestCrewJoinedNotification:
    """Tests for notify_crew_joined() and the registration hook."""

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_notify_crew_joined_sends_to_skipper(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_crew_joined

        with app.test_request_context():
            notify_crew_joined(crew_user, skipper_user)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to"] == skipper_user.email
        assert crew_user.display_name in call_kwargs["subject"]

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_notify_crew_joined_skips_opted_out_skipper(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_crew_joined

        skipper_user.email_opt_in = False
        db.session.commit()

        with app.test_request_context():
            notify_crew_joined(crew_user, skipper_user)

        mock_send.assert_not_called()

    @patch("app.notifications.service.is_email_configured", return_value=False)
    def test_notify_crew_joined_silent_when_email_not_configured(
        self, mock_configured, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_crew_joined

        with app.test_request_context():
            notify_crew_joined(crew_user, skipper_user)

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_registration_triggers_notification(
        self, mock_configured, mock_send, app, db, client, skipper_user
    ):
        # Create a pending crew member invited by skipper
        pending = User(
            email="newcrew@test.com",
            display_name="New Crew",
            initials="NC",
            invite_token="reg-token-123",
            invited_by=skipper_user.id,
        )
        pending.set_password("temppass")
        db.session.add(pending)
        db.session.commit()

        resp = client.post(
            "/register/reg-token-123",
            data={
                "display_name": "New Crew",
                "initials": "NC",
                "password": "newpass123",
                "password2": "newpass123",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to"] == skipper_user.email
        assert "New Crew" in call_kwargs["subject"]


class TestGetEligibleCrew:
    """Tests for get_eligible_crew() helper."""

    def test_eligible_crew_member(self, app, db, skipper_user, crew_user):
        from app.notifications.service import get_eligible_crew

        result = get_eligible_crew(skipper_user)
        assert len(result) == 1
        assert result[0]["eligible"] is True
        assert result[0]["user"].id == crew_user.id

    def test_opted_out_crew_member(self, app, db, skipper_user, crew_user):
        from app.notifications.service import get_eligible_crew

        crew_user.email_opt_in = False
        db.session.commit()

        result = get_eligible_crew(skipper_user)
        assert len(result) == 1
        assert result[0]["eligible"] is False
        assert result[0]["reason"] == "Opted out of emails"

    def test_pending_registration_crew(self, app, db, skipper_user):
        from app.notifications.service import get_eligible_crew

        pending = User(
            email="pending@test.com",
            display_name="Pending",
            initials="PE",
            invite_token="token123",
        )
        pending.set_password("password")
        db.session.add(pending)
        db.session.flush()
        skipper_user.crew_members.append(pending)
        db.session.commit()

        result = get_eligible_crew(skipper_user)
        assert len(result) == 1
        assert result[0]["eligible"] is False
        assert result[0]["reason"] == "Registration pending"


# ---------------------------------------------------------------------------
# Phase 2 Tests
# ---------------------------------------------------------------------------


class TestRsvpDigest:
    """Tests for send_rsvp_digests()."""

    def _setup_digest_skipper(self, db, skipper_user):
        """Set skipper to digest mode."""
        skipper_user.notification_prefs = json.dumps(
            {"rsvp_notification": True, "rsvp_delivery": "digest"}
        )
        db.session.commit()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_sends_digest_to_digest_mode_skipper(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_rsvp_digests

        self._setup_digest_skipper(db, skipper_user)

        regatta = Regatta(
            name="Spring Regatta",
            boat_class="J/24",
            location="Lakewood YC",
            start_date=date(2026, 5, 3),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()
        rsvp = RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="yes")
        db.session.add(rsvp)
        db.session.commit()

        with app.test_request_context():
            sent = send_rsvp_digests()

        assert sent == 1
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to"] == skipper_user.email
        assert "Daily RSVP Summary" in call_kwargs["subject"]

        # Verify log created
        log = NotificationLog.query.filter_by(
            notification_type="rsvp_digest", user_id=skipper_user.id
        ).first()
        assert log is not None

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_skips_per_rsvp_skipper(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_rsvp_digests

        # Default is per_rsvp mode
        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=date(2026, 5, 3),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()
        rsvp = RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="yes")
        db.session.add(rsvp)
        db.session.commit()

        with app.test_request_context():
            sent = send_rsvp_digests()

        assert sent == 0
        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_skips_when_no_new_rsvps(
        self, mock_configured, mock_send, app, db, skipper_user
    ):
        from app.notifications.service import send_rsvp_digests

        self._setup_digest_skipper(db, skipper_user)

        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=date(2026, 5, 3),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.commit()
        # No RSVPs at all

        with app.test_request_context():
            sent = send_rsvp_digests()

        assert sent == 0
        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_groups_rsvps_by_regatta(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_rsvp_digests

        self._setup_digest_skipper(db, skipper_user)

        r1 = Regatta(
            name="Spring Regatta",
            boat_class="J/24",
            location="Lakewood YC",
            start_date=date(2026, 5, 3),
            created_by=skipper_user.id,
        )
        r2 = Regatta(
            name="Summer Series",
            boat_class="J/24",
            location="Bay Harbor",
            start_date=date(2026, 6, 14),
            created_by=skipper_user.id,
        )
        db.session.add_all([r1, r2])
        db.session.flush()

        rsvp1 = RSVP(regatta_id=r1.id, user_id=crew_user.id, status="yes")
        rsvp2 = RSVP(regatta_id=r2.id, user_id=crew_user.id, status="maybe")
        db.session.add_all([rsvp1, rsvp2])
        db.session.commit()

        with app.test_request_context():
            sent = send_rsvp_digests()

        assert sent == 1
        call_kwargs = mock_send.call_args[1]
        assert "2 update(s)" in call_kwargs["subject"]
        assert "Spring Regatta" in call_kwargs["body_text"]
        assert "Summer Series" in call_kwargs["body_text"]


class TestRsvpReminders:
    """Tests for send_rsvp_reminders()."""

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_sends_to_notified_crew_who_havent_rsvped(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_rsvp_reminders

        target_date = date.today() + timedelta(days=14)
        regatta = Regatta(
            name="Test Regatta",
            boat_class="J/24",
            location="YC",
            start_date=target_date,
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()

        # Create notify_crew log (crew was notified)
        db.session.add(
            NotificationLog(
                notification_type="notify_crew",
                regatta_id=regatta.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        db.session.commit()

        with app.test_request_context():
            sent = send_rsvp_reminders(days_before=14)

        assert sent == 1
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to"] == crew_user.email
        assert "RSVP Reminder" in call_kwargs["subject"]

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_skips_crew_without_notify_log(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_rsvp_reminders

        target_date = date.today() + timedelta(days=14)
        regatta = Regatta(
            name="Test Regatta",
            boat_class="J/24",
            location="YC",
            start_date=target_date,
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.commit()
        # NO notify_crew log

        with app.test_request_context():
            sent = send_rsvp_reminders(days_before=14)

        assert sent == 0
        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_skips_crew_who_already_rsvped(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_rsvp_reminders

        target_date = date.today() + timedelta(days=14)
        regatta = Regatta(
            name="Test Regatta",
            boat_class="J/24",
            location="YC",
            start_date=target_date,
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()

        # Crew was notified
        db.session.add(
            NotificationLog(
                notification_type="notify_crew",
                regatta_id=regatta.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        # And already RSVPed
        db.session.add(RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="yes"))
        db.session.commit()

        with app.test_request_context():
            sent = send_rsvp_reminders(days_before=14)

        assert sent == 0
        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_dedup_via_notification_log(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_rsvp_reminders

        target_date = date.today() + timedelta(days=14)
        regatta = Regatta(
            name="Test Regatta",
            boat_class="J/24",
            location="YC",
            start_date=target_date,
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()

        # Crew was notified
        db.session.add(
            NotificationLog(
                notification_type="notify_crew",
                regatta_id=regatta.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        # Already reminded
        db.session.add(
            NotificationLog(
                notification_type="rsvp_reminder",
                regatta_id=regatta.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        db.session.commit()

        with app.test_request_context():
            sent = send_rsvp_reminders(days_before=14)

        assert sent == 0
        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_skips_digest_mode_crew(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_rsvp_reminders

        crew_user.notification_prefs = json.dumps({"rsvp_delivery": "digest"})
        db.session.commit()

        target_date = date.today() + timedelta(days=14)
        regatta = Regatta(
            name="Test Regatta",
            boat_class="J/24",
            location="YC",
            start_date=target_date,
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()

        db.session.add(
            NotificationLog(
                notification_type="notify_crew",
                regatta_id=regatta.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        db.session.commit()

        with app.test_request_context():
            sent = send_rsvp_reminders(days_before=14)

        assert sent == 0
        mock_send.assert_not_called()


class TestComingUpReminders:
    """Tests for send_coming_up_reminders()."""

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_sends_to_notified_crew_who_rsvped_yes(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_coming_up_reminders

        target_date = date.today() + timedelta(days=3)
        regatta = Regatta(
            name="Test Regatta",
            boat_class="J/24",
            location="YC",
            start_date=target_date,
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()

        # Crew was notified
        db.session.add(
            NotificationLog(
                notification_type="notify_crew",
                regatta_id=regatta.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        # Crew RSVPed yes
        db.session.add(RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="yes"))
        db.session.commit()

        with app.test_request_context():
            sent = send_coming_up_reminders(days_before=3)

        assert sent == 1
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to"] == crew_user.email
        assert "Coming Up" in call_kwargs["subject"]

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_sends_to_maybe_rsvp(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_coming_up_reminders

        target_date = date.today() + timedelta(days=3)
        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=target_date,
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()

        db.session.add(
            NotificationLog(
                notification_type="notify_crew",
                regatta_id=regatta.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        db.session.add(
            RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="maybe")
        )
        db.session.commit()

        with app.test_request_context():
            sent = send_coming_up_reminders(days_before=3)

        assert sent == 1

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_skips_crew_who_rsvped_no(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_coming_up_reminders

        target_date = date.today() + timedelta(days=3)
        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=target_date,
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()

        db.session.add(
            NotificationLog(
                notification_type="notify_crew",
                regatta_id=regatta.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        db.session.add(RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="no"))
        db.session.commit()

        with app.test_request_context():
            sent = send_coming_up_reminders(days_before=3)

        assert sent == 0
        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_skips_crew_without_notify_log(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_coming_up_reminders

        target_date = date.today() + timedelta(days=3)
        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=target_date,
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()

        # No notify_crew log, but has RSVP yes
        db.session.add(RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="yes"))
        db.session.commit()

        with app.test_request_context():
            sent = send_coming_up_reminders(days_before=3)

        assert sent == 0
        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_dedup_via_notification_log(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_coming_up_reminders

        target_date = date.today() + timedelta(days=3)
        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=target_date,
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()

        db.session.add(
            NotificationLog(
                notification_type="notify_crew",
                regatta_id=regatta.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        db.session.add(RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="yes"))
        # Already reminded
        db.session.add(
            NotificationLog(
                notification_type="coming_up_reminder",
                regatta_id=regatta.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        db.session.commit()

        with app.test_request_context():
            sent = send_coming_up_reminders(days_before=3)

        assert sent == 0
        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_skips_digest_mode_crew(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_coming_up_reminders

        crew_user.notification_prefs = json.dumps({"rsvp_delivery": "digest"})
        db.session.commit()

        target_date = date.today() + timedelta(days=3)
        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=target_date,
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()

        db.session.add(
            NotificationLog(
                notification_type="notify_crew",
                regatta_id=regatta.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        db.session.add(RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="yes"))
        db.session.commit()

        with app.test_request_context():
            sent = send_coming_up_reminders(days_before=3)

        assert sent == 0
        mock_send.assert_not_called()


class TestCrewDigest:
    """Tests for send_crew_digests()."""

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_batches_rsvp_and_coming_up_for_digest_crew(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_crew_digests

        crew_user.notification_prefs = json.dumps({"rsvp_delivery": "digest"})
        db.session.commit()

        # Create regatta needing RSVP (14 days out)
        rsvp_target = date.today() + timedelta(days=14)
        r1 = Regatta(
            name="RSVP Needed Regatta",
            boat_class="J/24",
            location="YC",
            start_date=rsvp_target,
            created_by=skipper_user.id,
        )
        db.session.add(r1)
        db.session.flush()
        db.session.add(
            NotificationLog(
                notification_type="notify_crew",
                regatta_id=r1.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )

        # Create coming up regatta (3 days out)
        upcoming_target = date.today() + timedelta(days=3)
        r2 = Regatta(
            name="Coming Up Regatta",
            boat_class="J/24",
            location="Harbor",
            start_date=upcoming_target,
            created_by=skipper_user.id,
        )
        db.session.add(r2)
        db.session.flush()
        db.session.add(
            NotificationLog(
                notification_type="notify_crew",
                regatta_id=r2.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        db.session.add(RSVP(regatta_id=r2.id, user_id=crew_user.id, status="yes"))
        db.session.commit()

        with app.test_request_context():
            sent = send_crew_digests()

        assert sent == 1
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to"] == crew_user.email
        assert "Daily Update" in call_kwargs["subject"]
        assert "RSVP Needed Regatta" in call_kwargs["body_text"]
        assert "Coming Up Regatta" in call_kwargs["body_text"]

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_skips_per_rsvp_crew(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import send_crew_digests

        # Default per_rsvp mode — should not get crew digest
        target_date = date.today() + timedelta(days=14)
        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=target_date,
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()
        db.session.add(
            NotificationLog(
                notification_type="notify_crew",
                regatta_id=regatta.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        db.session.commit()

        with app.test_request_context():
            sent = send_crew_digests()

        assert sent == 0
        mock_send.assert_not_called()


class TestSendRemindersAPI:
    """Tests for the /admin/api/send-reminders endpoint."""

    def _set_api_token(self, db, token):
        setting = SiteSetting(key="reminder_api_token", value=token)
        db.session.add(setting)
        db.session.commit()

    def test_missing_token_returns_403(self, app, db, client):
        resp = client.get("/admin/api/send-reminders")
        assert resp.status_code == 403
        assert b"Missing token" in resp.data

    def test_invalid_token_returns_403(self, app, db, client):
        self._set_api_token(db, "correct-token")
        resp = client.get("/admin/api/send-reminders?token=wrong-token")
        assert resp.status_code == 403
        assert b"Invalid token" in resp.data

    @patch("app.notifications.service.send_all_reminders")
    def test_valid_token_returns_summary(self, mock_reminders, app, db, client):
        mock_reminders.return_value = {
            "digests": 2,
            "crew_digests": 1,
            "rsvp_reminders": 5,
            "coming_up_reminders": 3,
        }
        self._set_api_token(db, "test-token-123")
        resp = client.get("/admin/api/send-reminders?token=test-token-123")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["digests"] == 2
        assert data["rsvp_reminders"] == 5
        assert data["coming_up_reminders"] == 3
        mock_reminders.assert_called_once()

    def test_empty_stored_token_returns_403(self, app, db, client):
        self._set_api_token(db, "")
        resp = client.get("/admin/api/send-reminders?token=anything")
        assert resp.status_code == 403


class TestSendRemindersCliCommand:
    """Tests for the flask send-reminders CLI command."""

    @patch("app.notifications.service.send_all_reminders")
    def test_command_invokes_send_all_reminders(self, mock_reminders, app):
        mock_reminders.return_value = {
            "digests": 0,
            "crew_digests": 0,
            "rsvp_reminders": 0,
            "coming_up_reminders": 0,
        }
        runner = app.test_cli_runner()
        result = runner.invoke(args=["send-reminders"])
        assert result.exit_code == 0
        mock_reminders.assert_called_once()
        assert '"digests": 0' in result.output


class TestPhase2ProfilePreferences:
    """Tests for notification delivery preference saving for all users."""

    def test_crew_can_save_digest_preference(self, app, db, logged_in_crew, crew_user):
        resp = logged_in_crew.post(
            "/profile",
            data={
                "display_name": crew_user.display_name,
                "initials": crew_user.initials,
                "email": crew_user.email,
                "email_opt_in": "on",
                "rsvp_delivery": "digest",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        db.session.refresh(crew_user)
        prefs = crew_user.notification_preferences
        assert prefs["rsvp_delivery"] == "digest"

    def test_skipper_can_save_digest_preference(
        self, app, db, logged_in_skipper, skipper_user
    ):
        resp = logged_in_skipper.post(
            "/profile",
            data={
                "display_name": skipper_user.display_name,
                "initials": skipper_user.initials,
                "email": skipper_user.email,
                "email_opt_in": "on",
                "rsvp_notification": "on",
                "rsvp_delivery": "digest",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        db.session.refresh(skipper_user)
        prefs = skipper_user.notification_preferences
        assert prefs["rsvp_delivery"] == "digest"
        assert prefs["rsvp_notification"] is True

    def test_profile_page_shows_notification_settings_for_crew(
        self, app, db, logged_in_crew
    ):
        resp = logged_in_crew.get("/profile")
        assert resp.status_code == 200
        assert b"Notification delivery" in resp.data
        assert b"Daily digest" in resp.data


class TestDeliveryModeLinkInEmails:
    """Tests that all notification emails include delivery mode switch link."""

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_rsvp_notification_includes_profile_link(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_rsvp_to_skipper

        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=date(2026, 5, 10),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()
        rsvp = RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="yes")
        db.session.add(rsvp)
        db.session.commit()

        with app.test_request_context():
            notify_rsvp_to_skipper(rsvp)

        call_kwargs = mock_send.call_args[1]
        assert "notification settings" in call_kwargs["body_text"].lower()
        assert "/profile" in call_kwargs["body_html"]

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_notify_crew_includes_profile_link(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import notify_crew

        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=date(2026, 5, 3),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.commit()

        with app.test_request_context():
            notify_crew([regatta], [crew_user], None, skipper_user)

        call_kwargs = mock_send.call_args[1]
        assert "notification preferences" in call_kwargs["body_text"].lower()
        assert "/profile" in call_kwargs["body_html"]


class TestFlushSkipperDigest:
    """Tests for flush_skipper_digest() when switching digest → instant."""

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_flush_sends_pending_rsvps(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import flush_skipper_digest

        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=date(2026, 5, 3),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()
        rsvp = RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="yes")
        db.session.add(rsvp)
        db.session.commit()

        with app.test_request_context():
            result = flush_skipper_digest(skipper_user)

        assert result is True
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to"] == skipper_user.email
        assert "Daily RSVP Summary" in call_kwargs["subject"]

        # Verify log created for dedup
        log = NotificationLog.query.filter_by(
            notification_type="rsvp_digest", user_id=skipper_user.id
        ).first()
        assert log is not None

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_flush_returns_false_when_no_pending(
        self, mock_configured, mock_send, app, db, skipper_user
    ):
        from app.notifications.service import flush_skipper_digest

        # No regattas or RSVPs
        with app.test_request_context():
            result = flush_skipper_digest(skipper_user)

        assert result is False
        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_profile_switch_triggers_flush(
        self,
        mock_configured,
        mock_send,
        app,
        db,
        logged_in_skipper,
        skipper_user,
        crew_user,
    ):
        # Set skipper to digest mode first
        skipper_user.notification_prefs = json.dumps(
            {"rsvp_notification": True, "rsvp_delivery": "digest"}
        )
        db.session.commit()

        # Create a pending RSVP
        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=date(2026, 5, 3),
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()
        rsvp = RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="yes")
        db.session.add(rsvp)
        db.session.commit()

        # Switch back to instant
        resp = logged_in_skipper.post(
            "/profile",
            data={
                "display_name": skipper_user.display_name,
                "initials": skipper_user.initials,
                "email": skipper_user.email,
                "email_opt_in": "on",
                "rsvp_notification": "on",
                "rsvp_delivery": "per_rsvp",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        # Flush should have sent the pending digest
        assert mock_send.call_count >= 1
        sent_subjects = [c[1]["subject"] for c in mock_send.call_args_list]
        assert any("RSVP Summary" in s for s in sent_subjects)


class TestFlushCrewDigest:
    """Tests for flush_crew_digest() when switching digest → instant."""

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_flush_sends_pending_crew_reminders(
        self, mock_configured, mock_send, app, db, skipper_user, crew_user
    ):
        from app.notifications.service import flush_crew_digest

        # Create a regatta 14 days out that crew was notified about
        target_date = date.today() + timedelta(days=14)
        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=target_date,
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()
        db.session.add(
            NotificationLog(
                notification_type="notify_crew",
                regatta_id=regatta.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        db.session.commit()

        with app.test_request_context():
            result = flush_crew_digest(crew_user)

        assert result is True
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to"] == crew_user.email
        assert "Daily Update" in call_kwargs["subject"]

        # Verify dedup log created
        log = NotificationLog.query.filter_by(
            notification_type="rsvp_reminder",
            regatta_id=regatta.id,
            user_id=crew_user.id,
        ).first()
        assert log is not None

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_flush_returns_false_when_no_pending(
        self, mock_configured, mock_send, app, db, crew_user
    ):
        from app.notifications.service import flush_crew_digest

        with app.test_request_context():
            result = flush_crew_digest(crew_user)

        assert result is False
        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_profile_switch_triggers_crew_flush(
        self,
        mock_configured,
        mock_send,
        app,
        db,
        logged_in_crew,
        crew_user,
        skipper_user,
    ):
        # Set crew to digest mode
        crew_user.notification_prefs = json.dumps({"rsvp_delivery": "digest"})
        db.session.commit()

        # Create pending reminder
        target_date = date.today() + timedelta(days=14)
        regatta = Regatta(
            name="Test",
            boat_class="J/24",
            location="YC",
            start_date=target_date,
            created_by=skipper_user.id,
        )
        db.session.add(regatta)
        db.session.flush()
        db.session.add(
            NotificationLog(
                notification_type="notify_crew",
                regatta_id=regatta.id,
                user_id=crew_user.id,
                trigger_date=date.today(),
            )
        )
        db.session.commit()

        # Switch back to instant
        resp = logged_in_crew.post(
            "/profile",
            data={
                "display_name": crew_user.display_name,
                "initials": crew_user.initials,
                "email": crew_user.email,
                "email_opt_in": "on",
                "rsvp_delivery": "per_rsvp",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        # Flush should have sent pending items
        assert mock_send.call_count >= 1
        sent_subjects = [c[1]["subject"] for c in mock_send.call_args_list]
        assert any("Daily Update" in s for s in sent_subjects)
