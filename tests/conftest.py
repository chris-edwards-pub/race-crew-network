import pytest
from flask import g
from sqlalchemy.pool import StaticPool

from app import create_app
from app import db as _db
from app.models import User

TEST_CONFIG = {
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "WTF_CSRF_ENABLED": False,
    "SERVER_NAME": "localhost",
    "ANTHROPIC_API_KEY": "test-key",
    # Use StaticPool to keep a single connection alive for the in-memory
    # database.  Without this, the default QueuePool recycles connections
    # after ~5 tests, destroying the database and its tables.
    "SQLALCHEMY_ENGINE_OPTIONS": {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    },
}


@pytest.fixture(scope="session")
def app():
    """Create a Flask app and tables once per test session."""
    app = create_app(test_config=TEST_CONFIG)

    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(autouse=True)
def _clean_db(app):
    """Delete all rows after each test (no schema rebuild)."""
    yield
    _db.session.rollback()
    for table in reversed(_db.metadata.sorted_tables):
        _db.session.execute(table.delete())
    _db.session.commit()
    # Core SQL DELETE does not update the ORM identity map.  Expire all
    # cached attributes so the next access goes back to the database.
    _db.session.expire_all()
    # The app context is session-scoped, so Flask's `g` persists across
    # tests.  Clear Flask-Login's cached user to prevent login state from
    # leaking between tests.
    g.pop("_login_user", None)


@pytest.fixture()
def db(app):
    """Provide the database instance."""
    return _db


@pytest.fixture()
def client(app):
    """A Flask test client."""
    return app.test_client()


@pytest.fixture()
def admin_user(db):
    """Create and return an admin user."""
    user = User(
        email="admin@test.com",
        display_name="Admin",
        initials="AD",
        is_admin=True,
    )
    user.set_password("password")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def logged_in_client(client, admin_user):
    """A test client logged in as admin."""
    client.post(
        "/login",
        data={"email": "admin@test.com", "password": "password"},
        follow_redirects=True,
    )
    return client
