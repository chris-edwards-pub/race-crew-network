import pytest

from app import create_app, db as _db
from app.models import User

TEST_CONFIG = {
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "WTF_CSRF_ENABLED": False,
    "SERVER_NAME": "localhost",
    "ANTHROPIC_API_KEY": "test-key",
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
    for table in reversed(_db.metadata.sorted_tables):
        _db.session.execute(table.delete())
    _db.session.commit()


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
