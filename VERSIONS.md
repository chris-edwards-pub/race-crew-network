# Version History

## 0.10.0
- RSVP symbols moved to front of initials with space (e.g. "&#10003; CE" instead of "CE&#10003;")
- Crew initials are clickable links to crew member profile page
- Hover over initials shows crew member's full name
- Phone number field added to user profiles
- Phone number editable in self profile and admin edit user
- Profile view page shows name, email, phone, and role
- Version 0.10.0

## 0.9.0
- Added VERSIONS.md with full version history
- RSVP display: checkmark for Yes, X for No, ? for Maybe next to crew initials
- Print button on main page with print-friendly stylesheet

## 0.8.1
- iCal subscribe link is now clickable in the flash message
- Google Maps link auto-generated from location text when left blank (override by pasting custom URL)
- Documents support URL or file upload (NOR, SI, WWW types)
- URL-based docs open directly in new tab

## 0.8.0
- iCal calendar subscription feed for iPhone/calendar apps
- Per-user secret token for unauthenticated calendar access
- Events include location, notes, crew RSVP status
- "iCal" link in navbar generates subscription URL

## 0.7.1
- Admin can edit any user (name, initials, email, password, admin role)
- Edit button on crew management page
- Profile settings dropdown under initials in navbar
- Users can change their own name, initials, email, and password
- Renamed "Date" column to "Date(s)"

## 0.7.0
- README with local development and testing instructions
- AWS Lightsail deployment instructions (Container Service and Instance options)
- Backup instructions for database and uploaded documents

## 0.6.0
- Dockerfile with Python 3.11-slim and MySQL client libraries
- docker-compose.yml with web (Flask/Gunicorn), db (MySQL 8), and nginx services
- Nginx reverse proxy configuration
- Gunicorn configuration (2 workers)
- Entrypoint script runs database migrations before starting
- Initial Alembic migration for all tables

## 0.4.0
- Upload NOR/SI PDFs to local disk with UUID-based filenames
- Download documents with original filename preserved
- Admin-only upload and delete; all authenticated users can download

## 0.3.0
- Main page with regatta table sorted by date (upcoming and past sections)
- Admin: add, edit, delete regattas
- Crew: Yes/No/Maybe RSVP dropdown per regatta
- Color-coded crew initials badges
- Location links to Google Maps
- Past regattas shown grayed out

## 0.2.0
- Login and logout with Flask-Login
- Invite-based crew registration (admin generates link, crew sets name/initials/password)
- Admin user management page (invite, view, delete crew)
- CSRF protection via Flask-WTF
- Base template with Bootstrap 5 navbar

## 0.1.0
- Flask app factory with SQLAlchemy and Flask-Migrate
- MySQL database models: users, regattas, documents, rsvps
- Configuration from environment variables
- `flask create-admin` CLI command for initial setup
- Project standards in CLAUDE.md
- Git repository initialized with .gitignore
