# Version History

## 0.25.0
- Add `boat_class` column to Regatta model (free text, defaults to "TBD")
- Class column displayed on main schedule, PDF, and import preview tables
- iCal event summary includes boat class when set (e.g. "Thistle — Midwinters")
- Add/Edit regatta form includes Boat Class field
- AI extraction prompt updated to extract boat class from imported schedules
- Import flows (single, multiple, document review) pass boat_class through all steps

## 0.24.0
- Redesign import UI: split monolithic page into three focused pages (Single Regatta, Multiple Regattas, Paste Schedule Text)
- Navbar dropdown menu replaces single "Import" link for admin users
- Terminal output moved to Bootstrap modal overlay instead of inline div
- Single regatta flow shows editable preview before document discovery
- Shared SSE JavaScript extracted to `import-sse.js` for reuse across pages
- Reusable template partials: terminal modal, preview table
- Old `/admin/import-schedule` URL redirects to multiple regattas page
- Dynamic "Start Over" links return to the correct input page

## 0.23.0
- Two-level document crawl: follows WWW links from detail pages to find NOR/SI on regatta websites
- Clubspot integration: queries clubspot Parse API directly for NOR/SI documents
- Extract JSON data attributes from JS-rendered pages (Vue/React hydration data)
- "Import Single Regatta" button with combined extract + document discovery in one pass
- Separate URL fields for single regatta vs multi-regatta schedule import
- Improved document discovery prompt with explicit regatta portal domain recognition
- Past events shown with warning instead of silently filtered out
- Documents sorted alphabetically (NOR, SI, WWW) in all views
- Crew column wraps for 3+ crew members on main schedule page

## 0.22.0
- Auto-discover NOR/SI/WWW documents during AI schedule import
- AI extracts detail_url for each regatta's individual event page
- "Find Documents & Import" button fetches detail pages and discovers document links
- Live terminal shows real-time progress via SSE streaming as pages are fetched
- Document review page with checkboxes to select which documents to attach
- "Import Without Documents" button preserves original import flow
- Discovered documents created as URL-based Document records on import
- Link URLs preserved in fetched HTML so AI can see href targets

## 0.21.0
- Detect duplicate regattas during AI import preview with warning badges
- Case-insensitive duplicate matching (name + start date) against existing regattas
- Duplicate rows highlighted in yellow and unchecked by default in preview table
- Existing regatta details shown inline so admin can make informed decisions
- Improved confirm-step duplicate check to be case-insensitive

## 0.20.2
- Bulk delete regattas: admin can select multiple regattas via checkboxes and delete them at once
- Select-all checkbox and confirmation dialog for both upcoming and past tables

## 0.20.1
- Extract JSON-LD schema.org Event data from pages that load events via JavaScript
- Automatically filter out past events from import results

## 0.20.0
- AI-powered schedule import: admin page to paste text or URL, extract regattas via Claude API
- Editable preview table with select/deselect before bulk import
- SSRF protection for URL fetching (rejects private/loopback IPs)
- Duplicate detection (same name + start date) on import
- Auto-generates Google Maps links for imported locations
- New admin blueprint with `/admin/import-schedule` routes
- New dependencies: anthropic, requests, beautifulsoup4

## 0.19.0
- Add CloudFront distribution in front of S3 redirect bucket for apex domain HTTPS
- ACM certificate for racecrew.net with DNS validation
- Both https://racecrew.net and http://racecrew.net now redirect to https://www.racecrew.net
- Add ACM and CloudFront permissions to IAM policy
- Increase Terraform workflow timeout to 30 minutes for CloudFront deploys
- Remove stale TF_VAR_secret_key from Terraform workflow

## 0.18.1
- Require INIT_ADMIN_EMAIL and INIT_ADMIN_PASSWORD env vars for first deploy
- Remove random password generation from init-admin command (Lightsail logs not accessible)
- Add admin env vars to deploy workflow and .env.example
- Remove container deployment from Terraform — GitHub Actions owns deploys

## 0.18.0
- Migrate from Lightsail EC2 instance to Container Service for ephemeral deploys
- Add Lightsail Managed MySQL (micro) — automated backups, no container to manage
- Add Lightsail Object Storage (S3-compatible) for persistent file uploads
- File uploads/downloads now use S3 with presigned URLs instead of local disk
- New Terraform resources: container service, managed database, object storage, SSL cert
- Rewrite deploy workflow: AWS CLI container deployment replaces SSH-based deploys
- Remove nginx, certbot, SSH key pair, static IP — container service handles HTTPS
- Simplify docker-compose.yml to web + db for local development only

## 0.17.1
- Update README with GHCR deployment docs, rollback instructions, and emergency fallback

## 0.17.0
- Build and push Docker images to GHCR via GitHub Actions
- Deploy pulls pre-built images instead of building on server
- Zero-downtime deploys (no more stopping containers to free RAM)
- Images tagged with: latest, git SHA, semantic version
- GHA build cache for fast subsequent builds
- Trimmed .dockerignore to reduce build context size

## 0.16.1
- Revert Lightsail instance_name default to avoid destroying deployed instance
- Update IAM policy Route53 zone ID to racecrew.net hosted zone

## 0.16.0
- Rename project from "Thistle Regatta Schedule" to "Race Crew Network"
- Update all user-facing branding (templates, PDF, iCal, filenames)
- Rename database/user from `regatta` to `racecrew`
- Rename Terraform/AWS resources (S3 bucket, instance name, IAM user)
- Update default admin email to `admin@racecrew.net`
- Bump version to 0.16.0

## 0.15.1
- Upgrade Lightsail instance from micro_3_0 (1GB) to small_3_0 (2GB) to resolve OOM issues

## 0.15.0
- Add Let's Encrypt SSL/HTTPS via certbot Docker sidecar container
- Automatic certificate renewal every 12 hours with nginx reload every 6 hours
- HTTP to HTTPS redirect with HSTS header
- Custom nginx entrypoint with SSL auto-detection (HTTP-only mode when no certs)
- One-time `scripts/init-ssl.sh` for initial certificate provisioning
- DOMAIN_NAME environment variable added to deployment workflow

## 0.14.0
- Migrated non-sensitive GitHub Secrets to GitHub Variables
- Fixed deploy SSH timeout with keepalive settings
- Fixed buildx session timeout by pre-pulling base image
- Fixed deploy OOM by stopping containers before build
- Increased deploy workflow timeout to 15 minutes
- Added versioning requirements to CLAUDE.md
- Added branching workflow rules to CLAUDE.md (never push directly to master)

## 0.13.0
- Terraform infrastructure-as-code for AWS Lightsail (instance, static IP, firewall)
- GitHub Actions deploy workflow: auto-deploys on push to master via SSH
- GitHub Actions Terraform workflow: plans on PR, applies on merge to master
- Dedicated IAM user and policy with least-privilege permissions
- S3 backend for Terraform state with versioning and public access block
- User-data script bootstraps instance with Docker, Docker Compose, and git
- All secrets stored in GitHub Secrets, nothing hardcoded in code
- Updated README with full CI/CD setup, infrastructure, and deployment docs

## 0.12.0
- Replaced broken Print button with server-side PDF generation using WeasyPrint
- PDF button opens a clean, print-ready PDF of the regatta schedule in a new tab
- PDF includes upcoming and past sections with crew RSVP status
- Added WeasyPrint system dependencies to Dockerfile

## 0.11.0
- Crew RSVP sorting: Yes first, No second, Maybe last, then alphabetically within each group
- Custom Jinja2 template filter (sort_rsvps) for consistent ordering
- Home button in navbar
- Version number displayed in footer on all pages
- Location links styled black

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
