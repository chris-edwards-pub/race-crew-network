# Version History

## 0.57.0
- Add daily vulnerability scan workflow (GitHub Actions) that scans the latest GHCR image with Trivy
- Automatically creates/updates GitHub Issues when CRITICAL/HIGH vulnerabilities are found
- Uploads SARIF results to GitHub Security tab
- Auto-closes issues when scans come back clean

## 0.56.1
- Fix CVE-2026-32274: bump black minimum version to 26.3.1 (arbitrary file writes via cache)
- Fix CVE-2026-0861, CVE-2025-71238: add `apt-get upgrade` to Dockerfile to pick up patched glibc and kernel packages

## 0.56.0
- Add calendar subscribe links to all email footers (notify crew, RSVP reminder, coming-up reminder, crew digest)
- Add calendar subscription banner on home page for users without a subscription
- Add calendar subscription section on profile page with URL copy or generate button

## 0.55.0
- Replace flash+redirect calendar subscribe flow with dedicated subscription page
- Add "Open in Calendar App" button using webcal:// protocol for one-tap subscribe (Apple Calendar, Outlook)
- Add step-by-step setup instructions for Apple Calendar (iPhone/iPad/Mac), Google Calendar, and Outlook
- Subscription URL with copy button for manual setup
- Rename navbar link from "iCal" to "Calendar"
- Add comprehensive tests for subscribe page

## 0.54.1
- Add 30-second timeout to all Anthropic API calls in document discovery and regatta extraction (#77)
- Catch `APITimeoutError` explicitly with clear error message instead of hanging indefinitely
- Existing error handling for connection, rate-limit, and status errors unchanged

## 0.54.0
- Add scheduled email reminders (Phase 2): RSVP daily digest, RSVP reminders (14 days before), and coming-up reminders (3 days before)
- Skippers can switch to daily digest mode for batched RSVP summary emails
- Crew members can choose between immediate and daily digest notification delivery
- RSVP and coming-up reminders only sent to crew previously notified about that regatta
- Crew daily digest batches RSVP reminders and coming-up reminders into one email
- Secured API endpoint (`/admin/api/send-reminders?token=...`) for AWS EventBridge scheduling
- `flask send-reminders` CLI command for local dev/testing
- Admin email settings page adds reminder timing configuration and API token management
- Notification settings section on profile page now available to all users (not just skippers)
- All notification emails include link to switch delivery mode on profile page
- Deduplication via NotificationLog prevents duplicate reminder emails on re-run

## 0.53.0
- Add email notification system (Phase 1)
- Skipper-initiated "Notify Crew" bulk action: select regattas and crew members, send one summary email per crew member
- Automatic RSVP-to-skipper notifications: skipper receives an email when crew RSVPs
- Notification preferences on profile page: skippers can toggle RSVP notifications on/off
- NotificationLog model tracks all sent notifications per regatta-crew pair
- New email templates for crew notifications and RSVP alerts
- Notify Crew modal with crew selection, optional custom message, and regatta summary

## 0.52.1
- Fix PDF title/content mismatch for crew members viewing a single skipper's schedule
- PDF link now includes skipper param when only one schedule context exists, matching the page title
- Fix PDF crew column showing full names instead of initials when profile pictures can't load
- Use inline avatar SVGs instead of profile image URLs in PDF for reliable rendering
- Add month divider rows to PDF schedule matching the web view's month labels
- Prevent crew badge line wrapping in PDF (check + initials + avatar stay on one line)

## 0.52.0
- Add local filesystem storage fallback when BUCKET_NAME is not set
- Uploads automatically use local disk (UPLOAD_FOLDER) in local dev, S3 in production
- New storage blueprint serves locally stored files at /uploads/ (login required)
- Remove BUCKET_NAME guards so profile pictures and documents work without S3
- Zero configuration needed for local development — just leave BUCKET_NAME empty

## 0.51.0
- Auto-assign random Multiavatar to every new user at creation time
- All user creation points (admin invite, crew invite, registration, CLI commands) generate a unique avatar seed
- Data migration backfills existing users with their email as avatar seed to preserve current avatars
- Profile page preview shows uploaded profile picture when present instead of always showing avatar SVG
- File selection preview in profile settings shows chosen image before saving
- Regenerate button clears file input to avoid conflicting selections

## 0.50.1
- Prioritize uploaded profile pictures over generated avatars across navbar, schedules, user lists, and PDF
- Keep generated avatar visible on crew profile pages while restoring a large top profile icon section
- Update Profile Settings so Regenerate replaces uploaded profile pictures on save and removes old S3 image
- Simplify Profile Settings copy and align avatar preview sizing with crew profile display

## 0.50.0
- Add unique Multiavatar icons to user profiles for visual crew disambiguation (#73)
- Each user gets a deterministic avatar generated from their email address
- Avatars displayed alongside initials in schedule crew badges, PDF, navbar, and all user lists
- Regenerate avatar button in Profile Settings with live preview
- Navbar shows initials + avatar instead of profile picture
- New `avatar_seed` column on User model with database migration

## 0.49.2
- Add month labels centered in the existing schedule divider treatment for Upcoming and Past sections (#56)
- Apply month divider labels in both desktop table and mobile card views
- Emphasize the modified divider line and month label text with bold styling

## 0.49.1
- Clarify profile picture limits in Profile Settings (accepted formats + 10 MB maximum)
- Add explicit profile upload size validation with a clear error message
- Handle oversized profile upload requests gracefully instead of generic failure (`Request Entity Too Large`) (#79)

## 0.49.0
- Add GNU Affero General Public License v3.0 (AGPL-3.0)

## 0.48.1
- Fix profile picture not displaying in navbar avatar and crew profile pages (#69)
- Fix PDF print to only include regattas matching current schedule and RSVP filters (#71)
- Add Skipper column and dynamic title to PDF when viewing All Schedules
- Fix RSVP filter to match any crew member's RSVP, not just the current user's (#72)
- Link skipper names to their profile in Combined Schedules view (#70)
- Rename "All Schedules" to "Combined Schedules" throughout UI and PDF

## 0.48.0
- Add profile picture support in Profile Settings with image upload and preview
- Add optional remove-profile-picture action from Profile Settings
- Validate profile image types (JPG, JPEG, PNG, GIF, WEBP)
- Persist uploaded profile image key on users via new database migration
- Delete user profile image object from storage when an admin deletes that user
- Unified schedule switcher dropdown for skipper+crew users with multiple contexts
- Dropdown shows "All Schedules", "My Schedule", and each skipper's name
- Per-row Edit/checkbox scoped to own regattas (not all skipper regattas)
- Add Regatta and Delete Schedule buttons hidden when viewing another skipper's schedule
- Page title reflects selected schedule context
- Append "'s Schedule" to other skipper names in schedule switcher dropdown
- Add Skipper column to desktop table and mobile cards in "All Schedules" view
- Add RSVP attendance filter with Yes/Maybe/No toggle buttons
- RSVP filter supports multi-select; all checked or none means no filter
- Preserve skipper and RSVP filter state across RSVP submissions

## 0.45.0
- Multi-user skipper/crew model with three roles: Admin, Skipper, Crew
- Skippers own their regatta schedule and can import regattas
- Skippers invite and manage their own crew via "My Crew" page
- Crew members see only their skippers' regattas and can RSVP
- Admins see all regattas across all skippers
- Role-aware navbar: Skippers see "My Crew" + "Import"; Admins see "Users" + "Admin"
- Skipper filter dropdown on home page for users with multiple skippers
- Scoped regatta visibility in iCal feeds and PDF export
- Permission-based access control for regatta CRUD, imports, and RSVP
- New `skipper_crew` association table and `is_skipper`/`invited_by` fields on User
- Registration auto-links new users to their inviting skipper's crew
- Admin can mark invitees as Skippers and toggle `is_skipper` on user edit

## 0.44.1
- Personalize invite email body with inviter's name ("{name}'s crew")
- Set From display name to "Race Crew Network" on all outgoing emails

## 0.44.0
- Add email invite option for crew members on Manage Crew page
- "Send invite via email" checkbox on invite form (when SES is configured)
- Bulk "Resend Invites" for pending users with select-all support
- Graceful fallback to invite link flash if email send fails

## 0.43.3
- Remove TODO.md
- Widen SES IAM policy to allow sending from all verified identities

## 0.43.2
- Fix "Extraction results not found or expired" error in multi-worker deployments (#55)
- Replace in-memory task result dicts with database-backed TaskResult model
- Add automatic cleanup of orphaned task results older than 1 hour

## 0.43.1
- Add dedicated IAM user for SES with Terraform-managed credentials
- Support separate SES_ACCESS_KEY_ID / SES_SECRET_ACCESS_KEY env vars

## 0.43.0
- Add one-click email unsubscribe (RFC 8058) with HMAC-signed links
- Add SES bounce and complaint handling via SNS webhook
- Add email_opt_in field to User model with profile page toggle
- Switch email service to send_raw_email for custom List-Unsubscribe headers
- Add Terraform resources for SNS topic and SES notification config
- Skip sending email to users who have opted out

## 0.42.0
- Add admin email settings page for configuring AWS SES sender address and region
- Add email service module with SES integration (send_email, load/save settings)
- Add test email endpoint to verify SES configuration from admin UI
- Add "Email Settings" link in Admin navigation dropdown

## 0.41.0
- Cache file import results by content hash (SHA-256) to skip AI re-extraction for identical files
- Add "Force re-extract (bypass cache)" checkbox to file import page

## 0.40.0
- Add file upload import: admins can upload PDF, DOCX, or TXT schedule files for AI extraction
- New "Import from File" page with file picker and year input
- Text extraction utilities for PDF (pypdf), DOCX (python-docx), and plain text files
- SSE streaming endpoint for file-based extraction with same preview/confirm flow
- Rename navigation links: "Import from URL" and "Import from File" replace old entries
- Legacy import URLs (import-single, import-multiple, import-schedule) redirect to import-url

## 0.39.0
- Show day(s) of week below regatta dates in schedule views
- Format day ranges as: single day `Sat`, two-day `Sat & Sun`, multi-day `Sat thru Mon`
- Apply day-of-week display in both the main schedule and printable PDF schedule

## 0.38.1
- Moved the Google Analyics tag from the footer below the head

## 0.38.0
- Fix Google Analytics environment gating to disable only for local hosts and tests
- Add warning log when analytics setting cannot be loaded from database
- Add Analytics Settings status banner showing whether GA is enabled or why it is disabled

## 0.37.0
- Remove "TBD" placeholder behavior for regatta boat class and leave class blank when unknown
- Update regatta create/edit and admin import flows to preserve blank boat class values
- Add migration to convert existing `TBD` boat class values to blank and set DB default to blank
- Update calendar summary logic and tests for blank boat class behavior

## 0.36.0
- Add database-backed site settings table for runtime configuration values
- Add admin analytics settings page to manage Google Analytics Measurement ID
- Add Admin navbar dropdown with Analytics Settings menu item
- Inject GA script in base template only when configured and not in development/testing
- Add migration and test coverage for site settings model, admin route access, and GA render behavior

## 0.35.1
- Convert training files from ASCII-formatted text to Markdown (.txt → .md)
- Replace old project name references (thistle-regatta-schedule → race-crew-network)
- Update internal cross-references to use .md file extensions

## 0.35.0
- Add 10-day Flask training curriculum (training/) with 12 text files
- Training materials cover app architecture, models, auth, CRUD, RSVP, file uploads, iCal, Docker, and deployment
- All lessons updated to reflect current codebase at v0.34.2 (Race Crew Network branding, 5 models, 4 blueprints, S3 storage, Lightsail deployment, CI/CD)

## 0.34.2
- Extract JSON-LD description, organizer, address, and URLs for richer AI extraction (fixes missing notes)
- Duplicate detection on document discovery review page with yellow warning rows
- Attaching a duplicate document replaces the existing one instead of creating a copy
- Add responsive design requirement to CLAUDE.md

## 0.34.1
- Fix detail_url fallback to apply to all regattas in multi-regatta imports (source_url was not being saved)
- Fix flaky test cleanup with gc.collect() for SQLAlchemy identity map stale weakrefs

## 0.34.0
- Store source URL on regattas during AI import (detail_url persisted as source_url)
- Source URL field on regatta edit form allows admins to view and update the import source
- "Find Documents" button on edit page discovers NOR/SI/WWW documents via AI from the source URL
- SSE streaming progress in terminal modal during document discovery
- Review page with checkboxes to select which discovered documents to attach
- "Force re-extract" checkbox bypasses cached content for fresh discovery

## 0.33.0
- Cache AI import extraction results per URL to eliminate redundant AI calls on repeat imports
- Cache hit serves instant results with zero token usage and no URL fetch
- "Force re-extract" checkbox on import forms to bypass cache when source page has been updated
- Preview page shows cache info banner with extraction date and re-extract link
- New `ImportCache` database model stores URL, extracted JSON, and timestamp

## 0.32.2
- Add continue-on-error to SARIF steps so transient GitHub outages don't block deployment

## 0.32.1
- Upgrade cryptography 44.0.0 → 46.0.5 (CVE-2026-26007, HIGH)
- Upgrade weasyprint 63.1 → 68.1 (CVE-2025-68616, HIGH, SSRF)

## 0.32.0
- Append Trivy vulnerability scan results to GitHub Actions job summary via $GITHUB_STEP_SUMMARY

## 0.31.2
- Use GHCR as Trivy vulnerability DB source instead of broken mirror.gcr.io default

## 0.31.1
- Update trivy-action from 0.33.1 to 0.34.2 to fix binary install failure

## 0.31.0
- Add container vulnerability scanning with Trivy between build and deploy stages
- Block deployment of images with CRITICAL or HIGH severity vulnerabilities
- Scan results uploaded as GitHub Actions artifact and to GitHub Security tab (SARIF)
- Upgrade base Docker image from python:3.11-slim to python:3.13-slim for fewer CVEs

## 0.30.0
- Enable automated daily database backups with 7-day retention and point-in-time recovery
- Set preferred backup window to 06:00–06:30 UTC (2:00–2:30 AM ET)
- Add final snapshot on database deletion as a safety net
- Enable versioning on Lightsail upload bucket to protect against accidental file deletion

## 0.29.0
- Add SVG favicon with PNG fallbacks for all devices (16x16, 32x32, 180x180 apple-touch-icon, 192x192 and 512x512 android-chrome)
- Remove legacy favicon.ico, consolidate all favicon assets into img/ directory
- Update base.html with proper icon link tags (SVG primary, PNG fallback, apple-touch-icon)
- Fix avatar badge overflow for long initials (min-width, padding, smaller font)
- Add nowrap to crew badges to prevent mid-badge line breaks

## 0.28.0
- Add site summary with feature list to login page (two-column layout, stacks on mobile)
- Serve login page at `/` for anonymous users instead of redirecting to `/login?next=%2F`
- Remove Flask-Login "Please log in" flash message
- Login form wrapped in a Bootstrap card with shadow for visual separation

## 0.27.0
- Make website fully responsive for phone, tablet, and desktop
- Add hamburger menu toggler and collapsible navbar (collapses below 768px)
- Responsive logo sizing: 80px (phone), 120px (tablet), 160px (desktop)
- Mobile card layout for regatta schedule (replaces table on small screens)
- Responsive admin users table with progressive column hiding
- Stack form inputs on small screens (regatta dates, document upload, invite form)
- Wrap button groups with flex-wrap to prevent overflow on narrow screens

## 0.26.1
- Make favicon background transparent using edge flood fill

## 0.26.0
- Navbar redesign: teal pill-shaped buttons for nav links (Home, iCal, Crew, Import)
- Circular teal avatar badge for user initials dropdown
- Nav menu positioned at 2/3 height of header, vertically aligned with logo
- White text on pill buttons with light teal hover effect
- Add logo image and favicon to navbar branding

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
