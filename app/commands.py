import secrets
import string

import click
from flask import Flask

from app import db
from app.models import User


def _generate_password(length: int = 16) -> str:
    """Generate a random secure password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    # Avoid problematic characters that might break shell/logs
    safe_chars = "".join(c for c in alphabet if c not in "'\"\\$`")
    return "".join(secrets.choice(safe_chars) for _ in range(length))


def register_commands(app: Flask) -> None:
    @app.cli.command("init-admin")
    def init_admin() -> None:
        """Initialize default admin account if none exists."""
        admin_exists = User.query.filter_by(is_admin=True).first()
        if admin_exists:
            click.echo("✓ Admin account already exists.")
            return

        # Generate credentials
        email = "admin@racecrew.net"
        password = _generate_password()
        display_name = "Administrator"
        initials = "AD"

        user = User(
            email=email,
            display_name=display_name,
            initials=initials,
            is_admin=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Print credentials in a clear format for log files
        click.echo("\n" + "=" * 60)
        click.echo("⚠️  INITIAL ADMIN ACCOUNT CREATED")
        click.echo("=" * 60)
        click.echo(f"Email:    {email}")
        click.echo(f"Password: {password}")
        click.echo(f"Name:     {display_name}")
        click.echo(f"Initials: {initials}")
        click.echo("\n⚠️  Save these credentials securely!")
        click.echo("=" * 60 + "\n")

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
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin user '{name}' ({initials.upper()}) created successfully.")
