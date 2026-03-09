import os

import click
from flask import Flask

from app import db
from app.models import User


def register_commands(app: Flask) -> None:
    @app.cli.command("init-admin")
    def init_admin() -> None:
        """Initialize default admin account if none exists."""
        admin_exists = User.query.filter_by(is_admin=True).first()
        if admin_exists:
            click.echo("Admin account already exists.")
            return

        email = os.environ.get("INIT_ADMIN_EMAIL")
        password = os.environ.get("INIT_ADMIN_PASSWORD")
        if not email or not password:
            raise SystemExit(
                "ERROR: INIT_ADMIN_EMAIL and INIT_ADMIN_PASSWORD must be set "
                "for first deploy. Add them to your environment or .env file."
            )

        user = User(
            email=email,
            display_name="Administrator",
            initials="AD",
            is_admin=True,
            is_skipper=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin account created for {email}.")

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    @click.option("--name", prompt="Display name")
    @click.option("--initials", prompt="Initials (2-3 chars)")
    def create_admin(email: str, password: str, name: str, initials: str) -> None:
        """Create an admin user account."""
        if User.query.filter_by(email=email).first():
            click.echo(f"Error: User with email {email} already exists.")
            raise SystemExit(1)

        user = User(
            email=email,
            display_name=name,
            initials=initials.upper(),
            is_admin=True,
            is_skipper=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin user '{name}' ({initials.upper()}) created successfully.")
