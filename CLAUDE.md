# Race Crew Network — Project Standards

## Python Standards
- Python 3.11+
- Type hints encouraged on function signatures
- f-strings over `.format()` or `%` formatting
- Use pathlib for file paths where practical
- The local dev enviroment uses .venv

## Code Style
- **Formatter:** Black (line length 88)
- **Imports:** isort (Black-compatible profile)
- **Linting:** flake8 (max line length 120, configured in `.flake8`)
- Run: `black . && isort . && flake8`

## Project Conventions
- Flask app factory pattern (`create_app()` in `app/__init__.py`)
- Blueprints for route organization (`auth`, `regattas`)
- SQLAlchemy models in `app/models.py`
- Config from environment variables via `app/config.py`
- All secrets in `.env` — **never committed**

## Version Schema
Semantic Versioning (SemVer): `MAJOR.MINOR.PATCH`
- **MAJOR:** breaking changes (auth overhaul, DB schema rewrite)
- **MINOR:** new features (new page, new functionality)
- **PATCH:** bug fixes, small tweaks
- Version tracked in `app/__init__.py` as `__version__`
- **Every `feature/` or `fix/` branch must bump the version and update `VERSIONS.md` before merging**
  - `feature/` branches bump MINOR (e.g. 0.13.0 → 0.14.0)
  - `fix/` branches bump PATCH (e.g. 0.14.0 → 0.14.1)
- **After merging, tag the merge commit:** `git tag v<version>` and `git push origin --tags`

## Git Workflow
- `master` branch is production-ready — **never push directly to master**
- All work must be on a branch: `feature/<name>` for new work, `fix/<name>` for bug fixes
- Merge to `master` via PR when complete and tested
- Commit messages: imperative mood, concise ("Add regatta CRUD routes")

## Testing
- Framework: pytest
- Tests in `tests/` directory
- Run: `pytest` (or `.venv/bin/pytest` outside venv)
- **Fixtures** (`tests/conftest.py`):
  - `app` — Flask app with SQLite in-memory DB, CSRF disabled, `TESTING=True`
  - `db` — SQLAlchemy database instance
  - `client` — Flask test client
  - `admin_user` — pre-created admin user (admin@test.com / password)
  - `logged_in_client` — test client already authenticated as admin
- **Test files**:
  - `test_app_factory.py` — app creation, config, blueprints, version
  - `test_models.py` — User, Regatta, Document, RSVP models and cascades
  - `test_admin_routes.py` — access control, import preview/confirm, document review
  - `test_admin_helpers.py` — helper functions (_is_private_ip, _parse_clubspot_regatta_id, etc.)
  - `test_ai_service.py` — AI extraction/discovery with mocked Anthropic API
- **Patterns**: use `unittest.mock.patch` for external APIs (Anthropic, requests); all fixtures are function-scoped
- **All new features and bug fixes MUST include tests** — write and run tests for every code change before considering it complete
- **Run the full test suite (`pytest`) after every change** to ensure nothing is broken

## Docker
- Local dev: `docker compose up --build`
- Production: AWS Lightsail container service
- 3 containers: web (Flask/Gunicorn), db (MySQL 8), nginx (reverse proxy)

## Security
- This is a public repo, store all sensitive information in GitHub secrets and variables
- Check each PR for known security issues
- When planning take security into consideration

## Documentation
- Keep the README.md file up to date with each PR

## Local testing
- Testing can be done locally.  Docker and Mysql are both locally installed.
- Testing should be done with each PR
- Local admin credentials are set via `INIT_ADMIN_EMAIL` and `INIT_ADMIN_PASSWORD` in `.env`