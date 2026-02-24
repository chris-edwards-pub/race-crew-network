# Race Crew Network — Project Standards

## Python Standards
- Python 3.11+
- Type hints encouraged on function signatures
- f-strings over `.format()` or `%` formatting
- Use pathlib for file paths where practical

## Code Style
- **Formatter:** Black (line length 88)
- **Imports:** isort (Black-compatible profile)
- **Linting:** flake8
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
- Run: `pytest`

## Docker
- Local dev: `docker compose up --build`
- Production: AWS Lightsail container service
- 3 containers: web (Flask/Gunicorn), db (MySQL 8), nginx (reverse proxy)

## Security
- This is a public repo, store all sensitive information in GitHub secrets and variables
- Check each PR for known security issues
- When planning take security into consideration
