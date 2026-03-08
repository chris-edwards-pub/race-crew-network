"""Tests for email blueprint (unsubscribe and SES webhook)."""

import json
from unittest.mock import patch

from app.admin.email_service import generate_unsubscribe_token
from app.models import User


class TestUnsubscribeGet:
    def test_valid_token_unsubscribes(self, app, db, client):
        user = User(
            email="crew@example.com",
            display_name="Crew",
            initials="CR",
            email_opt_in=True,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        token = generate_unsubscribe_token("crew@example.com")
        resp = client.get(f"/unsubscribe?email=crew@example.com&token={token}")

        assert resp.status_code == 200
        assert b"unsubscribed" in resp.data.lower()

        db.session.refresh(user)
        assert user.email_opt_in is False

    def test_missing_email_returns_400(self, app, client):
        resp = client.get("/unsubscribe?token=abc")
        assert resp.status_code == 400

    def test_missing_token_returns_400(self, app, client):
        resp = client.get("/unsubscribe?email=crew@example.com")
        assert resp.status_code == 400

    def test_invalid_token_returns_400(self, app, client):
        resp = client.get("/unsubscribe?email=crew@example.com&token=invalid")
        assert resp.status_code == 400

    def test_unknown_user_returns_404(self, app, db, client):
        token = generate_unsubscribe_token("unknown@example.com")
        resp = client.get(f"/unsubscribe?email=unknown@example.com&token={token}")
        assert resp.status_code == 404


class TestUnsubscribePost:
    def test_one_click_unsubscribe(self, app, db, client):
        user = User(
            email="crew@example.com",
            display_name="Crew",
            initials="CR",
            email_opt_in=True,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        token = generate_unsubscribe_token("crew@example.com")
        resp = client.post(f"/unsubscribe?email=crew@example.com&token={token}")

        assert resp.status_code == 204

        db.session.refresh(user)
        assert user.email_opt_in is False

    def test_invalid_token_post_returns_400(self, app, client):
        resp = client.post("/unsubscribe?email=crew@example.com&token=badtoken")
        assert resp.status_code == 400


class TestSesWebhook:
    def test_subscription_confirmation(self, app, db, client):
        payload = {
            "Type": "SubscriptionConfirmation",
            "SubscribeURL": "https://sns.example.com/confirm?token=abc",
        }
        with patch("app.email.routes.requests.get") as mock_get:
            resp = client.post(
                "/webhooks/ses",
                data=json.dumps(payload),
                content_type="application/json",
            )
        assert resp.status_code == 200
        mock_get.assert_called_once_with(payload["SubscribeURL"], timeout=10)

    def test_hard_bounce_opts_out_user(self, app, db, client):
        user = User(
            email="bounce@example.com",
            display_name="Bouncer",
            initials="BO",
            email_opt_in=True,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        payload = {
            "Type": "Notification",
            "Message": json.dumps(
                {
                    "notificationType": "Bounce",
                    "bounce": {
                        "bounceType": "Permanent",
                        "bouncedRecipients": [{"emailAddress": "bounce@example.com"}],
                    },
                }
            ),
        }
        resp = client.post(
            "/webhooks/ses",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200

        db.session.refresh(user)
        assert user.email_opt_in is False

    def test_soft_bounce_does_not_opt_out(self, app, db, client):
        user = User(
            email="soft@example.com",
            display_name="Soft",
            initials="SF",
            email_opt_in=True,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        payload = {
            "Type": "Notification",
            "Message": json.dumps(
                {
                    "notificationType": "Bounce",
                    "bounce": {
                        "bounceType": "Transient",
                        "bouncedRecipients": [{"emailAddress": "soft@example.com"}],
                    },
                }
            ),
        }
        resp = client.post(
            "/webhooks/ses",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200

        db.session.refresh(user)
        assert user.email_opt_in is True

    def test_complaint_opts_out_user(self, app, db, client):
        user = User(
            email="complain@example.com",
            display_name="Complainer",
            initials="CO",
            email_opt_in=True,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        payload = {
            "Type": "Notification",
            "Message": json.dumps(
                {
                    "notificationType": "Complaint",
                    "complaint": {
                        "complainedRecipients": [
                            {"emailAddress": "complain@example.com"}
                        ],
                    },
                }
            ),
        }
        resp = client.post(
            "/webhooks/ses",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200

        db.session.refresh(user)
        assert user.email_opt_in is False

    def test_invalid_json_returns_400(self, app, client):
        resp = client.post(
            "/webhooks/ses",
            data="not json",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_unknown_type_returns_200(self, app, client):
        payload = {"Type": "UnknownType"}
        resp = client.post(
            "/webhooks/ses",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
