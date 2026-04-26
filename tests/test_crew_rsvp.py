"""Tests for skipper crew RSVP management, enhanced invite, and resend invitation."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from app.models import RSVP, Regatta, User
from app.notifications.service import notify_crew_rsvp_changed


def _make_regatta(db, skipper):
    """Helper to create a future regatta owned by the given skipper."""
    r = Regatta(
        name="Test Regatta",
        location="Test Location",
        start_date=date.today() + timedelta(days=7),
        created_by=skipper.id,
    )
    db.session.add(r)
    db.session.commit()
    return r


def _login(client, email):
    client.post(
        "/login", data={"email": email, "password": "password"}, follow_redirects=True
    )


# ── Crew RSVP route tests ────────────────────────────────────────────


class TestSkipperCrewRsvp:

    def test_skipper_sets_crew_rsvp_yes(
        self, app, db, logged_in_skipper, skipper_user, crew_user
    ):
        regatta = _make_regatta(db, skipper_user)
        resp = logged_in_skipper.post(
            f"/regattas/{regatta.id}/crew-rsvp",
            data={"crew_user_id": crew_user.id, "status": "yes"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        rsvp = RSVP.query.filter_by(regatta_id=regatta.id, user_id=crew_user.id).first()
        assert rsvp is not None
        assert rsvp.status == "yes"

    def test_skipper_sets_crew_rsvp_no(
        self, app, db, logged_in_skipper, skipper_user, crew_user
    ):
        regatta = _make_regatta(db, skipper_user)
        logged_in_skipper.post(
            f"/regattas/{regatta.id}/crew-rsvp",
            data={"crew_user_id": crew_user.id, "status": "no"},
            follow_redirects=True,
        )
        rsvp = RSVP.query.filter_by(regatta_id=regatta.id, user_id=crew_user.id).first()
        assert rsvp is not None
        assert rsvp.status == "no"

    def test_skipper_sets_crew_rsvp_maybe(
        self, app, db, logged_in_skipper, skipper_user, crew_user
    ):
        regatta = _make_regatta(db, skipper_user)
        logged_in_skipper.post(
            f"/regattas/{regatta.id}/crew-rsvp",
            data={"crew_user_id": crew_user.id, "status": "maybe"},
            follow_redirects=True,
        )
        rsvp = RSVP.query.filter_by(regatta_id=regatta.id, user_id=crew_user.id).first()
        assert rsvp is not None
        assert rsvp.status == "maybe"

    def test_skipper_clears_crew_rsvp(
        self, app, db, logged_in_skipper, skipper_user, crew_user
    ):
        regatta = _make_regatta(db, skipper_user)
        # Create initial RSVP
        rsvp = RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="yes")
        db.session.add(rsvp)
        db.session.commit()
        # Clear it
        logged_in_skipper.post(
            f"/regattas/{regatta.id}/crew-rsvp",
            data={"crew_user_id": crew_user.id, "status": ""},
            follow_redirects=True,
        )
        assert (
            RSVP.query.filter_by(regatta_id=regatta.id, user_id=crew_user.id).first()
            is None
        )

    def test_skipper_updates_existing_crew_rsvp(
        self, app, db, logged_in_skipper, skipper_user, crew_user
    ):
        regatta = _make_regatta(db, skipper_user)
        rsvp = RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="yes")
        db.session.add(rsvp)
        db.session.commit()
        logged_in_skipper.post(
            f"/regattas/{regatta.id}/crew-rsvp",
            data={"crew_user_id": crew_user.id, "status": "no"},
            follow_redirects=True,
        )
        rsvp = RSVP.query.filter_by(regatta_id=regatta.id, user_id=crew_user.id).first()
        assert rsvp.status == "no"

    def test_skipper_sets_rsvp_for_pending_crew(
        self, app, db, logged_in_skipper, skipper_user
    ):
        # Create a pending (invited) crew member
        pending = User(
            email="pending@test.com",
            password_hash="pending",
            display_name="Pending Sailor",
            initials="PS",
            invite_token="test-token-123",
            invited_by=skipper_user.id,
        )
        db.session.add(pending)
        db.session.flush()
        skipper_user.crew_members.append(pending)
        db.session.commit()

        regatta = _make_regatta(db, skipper_user)
        logged_in_skipper.post(
            f"/regattas/{regatta.id}/crew-rsvp",
            data={"crew_user_id": pending.id, "status": "yes"},
            follow_redirects=True,
        )
        rsvp = RSVP.query.filter_by(regatta_id=regatta.id, user_id=pending.id).first()
        assert rsvp is not None
        assert rsvp.status == "yes"

    def test_crew_rsvp_denied_for_non_skipper(
        self, app, db, logged_in_crew, skipper_user, crew_user
    ):
        regatta = _make_regatta(db, skipper_user)
        resp = logged_in_crew.post(
            f"/regattas/{regatta.id}/crew-rsvp",
            data={"crew_user_id": crew_user.id, "status": "yes"},
            follow_redirects=True,
        )
        assert b"Access denied" in resp.data
        assert (
            RSVP.query.filter_by(regatta_id=regatta.id, user_id=crew_user.id).first()
            is None
        )

    def test_crew_rsvp_denied_for_wrong_skipper(
        self, app, db, skipper_user, crew_user, client
    ):
        # Create another skipper
        other_skipper = User(
            email="other@test.com",
            display_name="Other Skipper",
            initials="OS",
            is_skipper=True,
        )
        other_skipper.set_password("password")
        db.session.add(other_skipper)
        db.session.commit()

        regatta = _make_regatta(db, skipper_user)
        _login(client, "other@test.com")
        resp = client.post(
            f"/regattas/{regatta.id}/crew-rsvp",
            data={"crew_user_id": crew_user.id, "status": "yes"},
            follow_redirects=True,
        )
        assert b"Access denied" in resp.data

    def test_crew_rsvp_denied_for_non_crew_member(
        self, app, db, logged_in_skipper, skipper_user
    ):
        # Create a user who is NOT on skipper's crew
        outsider = User(
            email="outsider@test.com",
            display_name="Outsider",
            initials="OU",
        )
        outsider.set_password("password")
        db.session.add(outsider)
        db.session.commit()

        regatta = _make_regatta(db, skipper_user)
        resp = logged_in_skipper.post(
            f"/regattas/{regatta.id}/crew-rsvp",
            data={"crew_user_id": outsider.id, "status": "yes"},
            follow_redirects=True,
        )
        assert b"Access denied" in resp.data

    def test_crew_rsvp_invalid_status_rejected(
        self, app, db, logged_in_skipper, skipper_user, crew_user
    ):
        regatta = _make_regatta(db, skipper_user)
        resp = logged_in_skipper.post(
            f"/regattas/{regatta.id}/crew-rsvp",
            data={"crew_user_id": crew_user.id, "status": "invalid"},
            follow_redirects=True,
        )
        assert b"Invalid RSVP status" in resp.data

    def test_crew_rsvp_preserves_redirect_params(
        self, app, db, logged_in_skipper, skipper_user, crew_user
    ):
        regatta = _make_regatta(db, skipper_user)
        resp = logged_in_skipper.post(
            f"/regattas/{regatta.id}/crew-rsvp",
            data={
                "crew_user_id": crew_user.id,
                "status": "yes",
                "redirect_skipper": str(skipper_user.id),
            },
        )
        assert resp.status_code == 302
        assert f"skipper={skipper_user.id}" in resp.location

    @patch("app.regattas.routes.notify_crew_rsvp_changed")
    def test_crew_rsvp_notifies_crew_member(
        self, mock_notify, app, db, logged_in_skipper, skipper_user, crew_user
    ):
        regatta = _make_regatta(db, skipper_user)
        logged_in_skipper.post(
            f"/regattas/{regatta.id}/crew-rsvp",
            data={"crew_user_id": crew_user.id, "status": "yes"},
            follow_redirects=True,
        )
        mock_notify.assert_called_once()
        args = mock_notify.call_args[0]
        assert args[0].id == crew_user.id
        assert args[1].id == regatta.id
        assert args[2] == "yes"
        assert args[3].id == skipper_user.id

    @patch("app.regattas.routes.notify_crew_rsvp_changed")
    def test_crew_rsvp_notifies_on_clear(
        self, mock_notify, app, db, logged_in_skipper, skipper_user, crew_user
    ):
        regatta = _make_regatta(db, skipper_user)
        rsvp = RSVP(regatta_id=regatta.id, user_id=crew_user.id, status="yes")
        db.session.add(rsvp)
        db.session.commit()
        logged_in_skipper.post(
            f"/regattas/{regatta.id}/crew-rsvp",
            data={"crew_user_id": crew_user.id, "status": ""},
            follow_redirects=True,
        )
        mock_notify.assert_called_once()
        args = mock_notify.call_args[0]
        assert args[0].id == crew_user.id
        assert args[1].id == regatta.id
        assert args[2] == ""
        assert args[3].id == skipper_user.id

    @patch("app.regattas.routes.notify_crew_rsvp_changed")
    def test_crew_rsvp_no_skipper_notification(
        self, mock_notify, app, db, logged_in_skipper, skipper_user, crew_user
    ):
        """Verify notify_rsvp_to_skipper is NOT called (skipper doesn't notify themselves)."""
        regatta = _make_regatta(db, skipper_user)
        with patch("app.regattas.routes.notify_rsvp_to_skipper") as mock_skipper:
            logged_in_skipper.post(
                f"/regattas/{regatta.id}/crew-rsvp",
                data={"crew_user_id": crew_user.id, "status": "yes"},
                follow_redirects=True,
            )
            mock_skipper.assert_not_called()


# ── Enhanced invite tests ─────────────────────────────────────────────


class TestEnhancedInvite:

    def test_invite_crew_with_name_and_initials(
        self, app, db, logged_in_skipper, skipper_user
    ):
        logged_in_skipper.post(
            "/my-crew/invite",
            data={
                "email": "newcrew@test.com",
                "display_name": "New Crew",
                "initials": "NC",
            },
            follow_redirects=True,
        )
        user = User.query.filter_by(email="newcrew@test.com").first()
        assert user is not None
        assert user.display_name == "New Crew"
        assert user.initials == "NC"
        assert user.invite_token is not None

    def test_invite_crew_with_phone(self, app, db, logged_in_skipper, skipper_user):
        logged_in_skipper.post(
            "/my-crew/invite",
            data={
                "email": "phonecrew@test.com",
                "display_name": "Phone Crew",
                "initials": "PC",
                "phone": "555-123-4567",
            },
            follow_redirects=True,
        )
        user = User.query.filter_by(email="phonecrew@test.com").first()
        assert user is not None
        assert user.phone == "555-123-4567"

    def test_invite_crew_requires_name(self, app, db, logged_in_skipper, skipper_user):
        resp = logged_in_skipper.post(
            "/my-crew/invite",
            data={
                "email": "noname@test.com",
                "display_name": "",
                "initials": "NN",
            },
            follow_redirects=True,
        )
        assert b"Name is required" in resp.data
        assert User.query.filter_by(email="noname@test.com").first() is None

    def test_invite_crew_requires_initials(
        self, app, db, logged_in_skipper, skipper_user
    ):
        resp = logged_in_skipper.post(
            "/my-crew/invite",
            data={
                "email": "noinit@test.com",
                "display_name": "No Init",
                "initials": "",
            },
            follow_redirects=True,
        )
        assert b"Initials are required" in resp.data
        assert User.query.filter_by(email="noinit@test.com").first() is None


# ── Resend invitation tests ──────────────────────────────────────────


class TestResendInvite:

    def _make_pending_crew(self, db, skipper):
        user = User(
            email="resend@test.com",
            password_hash="pending",
            display_name="Resend Crew",
            initials="RC",
            invite_token="resend-token-abc",
            invited_by=skipper.id,
        )
        db.session.add(user)
        db.session.flush()
        skipper.crew_members.append(user)
        db.session.commit()
        return user

    @patch("app.auth.routes._send_invite_email")
    @patch("app.auth.routes.is_email_configured", return_value=True)
    def test_resend_invite_success(
        self, mock_configured, mock_send, app, db, logged_in_skipper, skipper_user
    ):
        pending = self._make_pending_crew(db, skipper_user)
        resp = logged_in_skipper.post(
            f"/my-crew/{pending.id}/resend-invite",
            follow_redirects=True,
        )
        assert b"Invite resent" in resp.data
        mock_send.assert_called_once()
        db.session.refresh(pending)
        assert pending.invite_sent_at is not None

    @patch("app.auth.routes.is_email_configured", return_value=True)
    def test_resend_invite_rate_limited(
        self, mock_configured, app, db, logged_in_skipper, skipper_user
    ):
        pending = self._make_pending_crew(db, skipper_user)
        pending.invite_sent_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.session.commit()

        resp = logged_in_skipper.post(
            f"/my-crew/{pending.id}/resend-invite",
            follow_redirects=True,
        )
        assert b"already sent today" in resp.data

    def test_resend_invite_not_pending(
        self, app, db, logged_in_skipper, skipper_user, crew_user
    ):
        resp = logged_in_skipper.post(
            f"/my-crew/{crew_user.id}/resend-invite",
            follow_redirects=True,
        )
        assert b"not found or already registered" in resp.data

    def test_resend_invite_not_own_crew(self, app, db, skipper_user, client):
        # Create a pending user on skipper's crew
        pending = User(
            email="notmine@test.com",
            password_hash="pending",
            display_name="Not Mine",
            initials="NM",
            invite_token="notmine-token",
            invited_by=skipper_user.id,
        )
        db.session.add(pending)
        db.session.flush()
        skipper_user.crew_members.append(pending)
        db.session.commit()

        # Log in as a different skipper
        other = User(
            email="other2@test.com",
            display_name="Other2",
            initials="O2",
            is_skipper=True,
        )
        other.set_password("password")
        db.session.add(other)
        db.session.commit()
        _login(client, "other2@test.com")

        resp = client.post(
            f"/my-crew/{pending.id}/resend-invite",
            follow_redirects=True,
        )
        assert b"not on your crew" in resp.data


# ── Notification service tests ────────────────────────────────────────


class TestNotifyCrewRsvpChanged:

    def _make_crew_and_regatta(self, db, skipper):
        crew = User(
            email="notifycrew@test.com",
            display_name="Notify Crew",
            initials="NC",
            invited_by=skipper.id,
        )
        crew.set_password("password")
        db.session.add(crew)
        db.session.flush()
        skipper.crew_members.append(crew)
        db.session.commit()
        regatta = _make_regatta(db, skipper)
        return crew, regatta

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.render_template", return_value="mocked")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_notifies_active_crew(
        self, mock_configured, mock_render, mock_send, app, db, skipper_user
    ):
        crew, regatta = self._make_crew_and_regatta(db, skipper_user)
        notify_crew_rsvp_changed(crew, regatta, "yes", skipper_user)
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        assert call_kwargs[1]["to"] == "notifycrew@test.com"
        assert "yes" in call_kwargs[1]["subject"]

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.render_template", return_value="mocked")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_notifies_on_clear(
        self, mock_configured, mock_render, mock_send, app, db, skipper_user
    ):
        crew, regatta = self._make_crew_and_regatta(db, skipper_user)
        notify_crew_rsvp_changed(crew, regatta, "", skipper_user)
        mock_send.assert_called_once()
        assert "cleared" in mock_send.call_args[1]["subject"]

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_skips_pending_crew(
        self, mock_configured, mock_send, app, db, skipper_user
    ):
        pending = User(
            email="pendingnotify@test.com",
            password_hash="pending",
            display_name="Pending Notify",
            initials="PN",
            invite_token="pending-notify-token",
            invited_by=skipper_user.id,
        )
        db.session.add(pending)
        db.session.flush()
        skipper_user.crew_members.append(pending)
        db.session.commit()
        regatta = _make_regatta(db, skipper_user)
        notify_crew_rsvp_changed(pending, regatta, "yes", skipper_user)
        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=True)
    def test_skips_opted_out_crew(
        self, mock_configured, mock_send, app, db, skipper_user
    ):
        crew, regatta = self._make_crew_and_regatta(db, skipper_user)
        crew.email_opt_in = False
        db.session.commit()
        notify_crew_rsvp_changed(crew, regatta, "yes", skipper_user)
        mock_send.assert_not_called()

    @patch("app.notifications.service.send_email")
    @patch("app.notifications.service.is_email_configured", return_value=False)
    def test_skips_when_email_not_configured(
        self, mock_configured, mock_send, app, db, skipper_user
    ):
        crew, regatta = self._make_crew_and_regatta(db, skipper_user)
        notify_crew_rsvp_changed(crew, regatta, "yes", skipper_user)
        mock_send.assert_not_called()


# ── Permission helper tests ───────────────────────────────────────────


class TestCanSetCrewRsvp:

    def test_skipper_can_set_own_crew(self, app, db, skipper_user, crew_user):
        from app.permissions import can_set_crew_rsvp

        regatta = _make_regatta(db, skipper_user)
        assert can_set_crew_rsvp(skipper_user, regatta, crew_user) is True

    def test_skipper_cannot_set_non_crew(self, app, db, skipper_user):
        from app.permissions import can_set_crew_rsvp

        outsider = User(
            email="perm_outsider@test.com",
            display_name="Outsider",
            initials="OU",
        )
        outsider.set_password("password")
        db.session.add(outsider)
        db.session.commit()
        regatta = _make_regatta(db, skipper_user)
        assert can_set_crew_rsvp(skipper_user, regatta, outsider) is False

    def test_wrong_skipper_denied(self, app, db, skipper_user, crew_user):
        from app.permissions import can_set_crew_rsvp

        other = User(
            email="perm_other@test.com",
            display_name="Other",
            initials="OT",
            is_skipper=True,
        )
        other.set_password("password")
        db.session.add(other)
        db.session.commit()
        regatta = _make_regatta(db, skipper_user)
        assert can_set_crew_rsvp(other, regatta, crew_user) is False

    def test_admin_can_set(self, app, db, admin_user, skipper_user, crew_user):
        from app.permissions import can_set_crew_rsvp

        regatta = _make_regatta(db, skipper_user)
        assert can_set_crew_rsvp(admin_user, regatta, crew_user) is True
