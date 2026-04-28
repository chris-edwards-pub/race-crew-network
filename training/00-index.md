# Race Crew Network - Flask Application Training: 18-Day Curriculum

## Course Overview

This training program teaches you how to build and deploy a production-ready
Flask web application through the study of the Race Crew Network app.
Over 18 days across 4 phases, you'll learn Flask fundamentals, database
management with SQLAlchemy, multi-user role-based access control, email
notifications via AWS SES (with a queued/batch sender), AI-powered data import
with usage tracking and budget caps, calendar integration, public per-skipper
schedule pages, responsive UI design, infrastructure as code, and containerized
cloud deployment.

## Target Audience

IT professionals with:
- Basic Python knowledge (variables, functions, classes)
- Docker familiarity (containers, images, compose)
- Interest in web application development
- Little to no Flask experience (we'll teach you!)

## What You'll Build Understanding of

A complete web application for managing sailing regatta events:
- Multi-user role system: Admin, Skipper, and Crew roles
- Invite-based registration with email invites via AWS SES
- Forgot/reset password flow with email tokens (1-hour expiry)
- Enhanced crew invite (name, initials, optional phone) with resend (rate-limited)
- CRUD operations for regatta events with owner-based permissions
- RSVP system with Yes/No/Maybe; skipper can also set RSVPs on behalf of crew
- Document upload/management with S3/local storage abstraction
- AI-powered schedule import from URLs and files (PDF, DOCX, TXT, XLSX) via Anthropic Claude API
- AI usage logging with cost tracking, monthly budget cap, and 80% alert email
- Document discovery with SSE streaming progress
- Email notifications: manual crew notify, RSVP alerts, scheduled reminders, queued sender
- iCal calendar feed with scoped subscriptions
- PDF schedule generation with WeasyPrint
- Profile pictures, Multiavatar SVG avatars, optional Yacht Club and About Me fields
- Public per-skipper schedule pages (anonymous access via slug)
- Crew view of skipper's crew (contextual nav per schedule)
- Admin impersonation for debugging user views
- Public Help & Documentation page with contact form (honeypot + timestamp anti-spam)
- AI Statistics admin page (token usage, cost, per-function breakdown)
- Email Statistics admin page (SES send stats, Cost Explorer integration)
- Site settings for runtime configuration (GA, email, AI budget, reminders)
- Polished email layout with light-gray page + white card (slate logo panel)
- Responsive design with Bootstrap 5
- Terraform-managed AWS infrastructure
- Trivy vulnerability scanning in CI/CD pipeline (deploy gate + daily scan with auto-issue)
- Weekly GHCR retention workflow (keeps `:latest`, last 5 semver tags, recent SHA tags)
- Production deployment on AWS Lightsail Container Service

## Technical Stack You'll Master

- Python 3.13 & Flask 3.x web framework
- SQLAlchemy ORM (10 models + association table)
- Flask-Login for authentication
- Flask-Migrate for database schema management
- MySQL 8.0 database
- Gunicorn WSGI server
- Docker Compose orchestration (local dev)
- AWS Lightsail Container Service (production)
- AWS SES for transactional email (with queue-based sender)
- S3-compatible object storage (Lightsail buckets)
- Anthropic Claude API for AI-powered imports (with cost tracking)
- WeasyPrint for PDF generation
- Bootstrap 5 for responsive frontend
- Terraform for infrastructure as code
- GitHub Actions for CI/CD (deploy, daily vuln scan, weekly GHCR retention, terraform)
- Trivy for container vulnerability scanning

## Prerequisites

Before starting, ensure you have:
1. Docker and Docker Compose installed
2. Text editor or IDE (VS Code, PyCharm, etc.)
3. Terminal/command line access
4. Git (optional, for version control)
5. Web browser for testing

## Daily Session Structure

Each session includes:
- Learning Objectives (what you'll achieve)
- Concepts Covered (technical topics)
- File Focus (which code files to examine)
- Code Walkthrough (detailed explanations with line numbers)
- Architecture Diagrams (visual representations)
- Key Takeaways (summary and next steps)

## Recommended Approach

1. Read each session sequentially (Day 1 through Day 18)
2. Have the code repository open while reading
3. Follow along by examining the referenced files
4. Take notes on concepts that are new to you
5. Pause to explore code sections in detail
6. Return to earlier sessions as needed for review

## Time Commitment

Each session: 1-2 hours of focused reading and code exploration
Total course: ~25-35 hours spread over 18 workdays
Best pace: One session per day with hands-on exploration

# Session Roadmap

## Phase 1: Foundations (Days 1-4)

### Day 1: Introduction and Environment Setup
File: 01-day1.md
Topics:
  - Application overview and feature tour (3 roles, 7 blueprints)
  - Docker Compose setup (web, db containers)
  - Running the application locally
  - Creating your first admin account
  - Flask basics: routes, templates, blueprints

### Day 2: Flask Application Factory Pattern
File: 02-day2.md
Topics:
  - The create_app() factory pattern
  - Flask extensions initialization
  - Configuration management with environment variables
  - Blueprint registration (7 blueprints: admin, auth, calendar, email, help, regattas, storage)
  - Context processors and template filters
  - Application context and lifecycle

### Day 3: Database Models and SQLAlchemy
File: 03-day3.md
Topics:
  - Object-Relational Mapping (ORM) concepts
  - 10 models + skipper_crew association table
  - User model with roles, profile fields, password reset tokens, public schedule slug, notification preferences
  - Database relationships (1:N, M:N self-referential)
  - Password hashing with bcrypt
  - Permission scoping with visible_regattas()

### Day 4: Authentication and User Management
File: 04-day4.md
Topics:
  - Flask-Login integration
  - Login/logout implementation
  - Invite-based registration with email invites
  - Forgot/reset password flow with HMAC token + 1-hour expiry
  - Strong password requirements (8+ chars, upper/lower/digit) and strength meter
  - Enhanced crew invite (name, initials required, optional phone) + resend rate limit
  - Auto-link crew to inviting skipper
  - Avatar seed generation
  - User profile (image, yacht_club, about_me/bio)
  - Admin user administration and impersonation

## Phase 2: Core Features (Days 5-9)

### Day 5: Multi-User Role System and Permissions
File: 05-day5.md
Topics:
  - Three roles: Admin, Skipper, Crew
  - permissions.py helper functions and decorators
  - Admin impersonation via session
  - Role-based UI visibility in templates
  - Permission checks in route handlers

### Day 6: Event Management (CRUD Operations)
File: 06-day6.md
Topics:
  - RESTful route design in Flask
  - Create, Read, Update, Delete operations
  - Owner-based permission model
  - Bulk delete with checkbox selection
  - Schedule filtering by skipper and RSVP status
  - Auto-generated Google Maps links

### Day 7: RSVP System and Schedule View
File: 07-day7.md
Topics:
  - Schedule switcher (My Schedule / All Schedules)
  - RSVP with filter state preservation and scroll-position preservation
  - Skipper-set RSVP on behalf of crew (clickable badges + "+" column)
  - Bulk delete with type-to-confirm modal
  - PDF schedule generation with WeasyPrint
  - Notification triggers on RSVP changes (own-RSVP self-notify suppressed)
  - Custom template filters (sort_rsvps, regatta_days)

### Day 8: Document Upload and Storage
File: 08-day8.md
Topics:
  - File upload processing with Flask
  - S3/local storage abstraction layer
  - Profile image uploads and validation
  - Path traversal protection
  - Presigned URLs for secure downloads
  - Storage blueprint for local file serving

### Day 9: Skipper and Crew Management
File: 09-day9.md
Topics:
  - My Crew page (alphabetical, skipper pinned) and crew listing
  - Invite crew (new user or existing) — name, initials, optional phone
  - Resend invitation (rate-limited to once per day)
  - Remove crew members
  - Self-service schedule creation/deletion
  - Leave skipper (crew self-service)
  - Crew view: read-only "<Skipper>'s Crew" page with profile links
  - Public per-skipper schedule page (`/schedule/<slug>`) with PDF
  - skipper_crew association table

## Phase 3: Communication and Integration (Days 10-13)

### Day 10: Email Service with AWS SES
File: 10-day10.md
Topics:
  - AWS SES integration via boto3
  - HMAC-SHA256 unsubscribe tokens (RFC 8058)
  - One-click unsubscribe handling
  - Bounce and complaint webhook processing
  - EmailQueue model and queued sender (status, retries, error tracking)
  - Email opt-in/opt-out model and rate limits
  - SiteSetting-based email configuration
  - Email Statistics admin page (SES stats + AWS Cost Explorer)
  - Modern card layout (light gray page + white card + slate logo panel)

### Day 11: Notification System
File: 11-day11.md
Topics:
  - Manual crew notification (events + crew selection)
  - RSVP-to-skipper notifications (per-RSVP and digest)
  - Scheduled reminders (RSVP reminder, coming-up)
  - Crew digest emails
  - NotificationLog for deduplication
  - Digest flush on preference switch

### Day 12: Calendar Integration
File: 12-day12.md
Topics:
  - iCalendar format (RFC 5545)
  - Token-based feed authentication
  - Subscribe via webcal:// URLs
  - Scoped feeds (only yes/maybe RSVPs)
  - RSVP status in event descriptions
  - Calendar links in notification emails

### Day 13: AI-Powered Schedule Import
File: 13-day13.md
Topics:
  - Claude API integration via anthropic SDK
  - Extraction and discovery prompt engineering (city/state inference)
  - File import (PDF, DOCX, TXT, XLSX)
  - ImportCache, TaskResult, and AIUsageLog models
  - SSE streaming for progress updates
  - SSRF protection for URL fetching
  - Two-level document discovery
  - AI usage logging (tokens + cost), monthly budget cap, 80% alert email
  - AI Statistics admin page (per-function breakdown, budget progress)

## Phase 4: Operations and Advanced Topics (Days 14-18)

### Day 14: User Interface and Responsive Design
File: 14-day14.md
Topics:
  - Bootstrap 5 responsive grid and breakpoints
  - Navbar with mobile collapse and Help link (visible to anonymous visitors)
  - Avatar system (Multiavatar SVG + profile photos)
  - user_icon template filter with fallback
  - Impersonation banner
  - Public Help & Documentation page + contact form (honeypot + timestamp anti-spam)
  - Profile fields display (yacht_club, about_me/bio when set)
  - Mobile-friendly layout patterns

### Day 15: Site Settings and Admin Configuration
File: 15-day15.md
Topics:
  - SiteSetting model (key/value store)
  - Google Analytics settings page
  - Email settings page (SES sender, sender_to, region) + send-test
  - AI settings: monthly budget (`ai_monthly_cost_limit`) + monthly alert flag
  - Reminder settings (RSVP reminder days, upcoming days, API token, rate limit)
  - Runtime config vs environment variables
  - Context processor for conditional GA injection

### Day 16: Docker and Containerization
File: 16-day16.md
Topics:
  - Dockerfile structure and best practices
  - Docker Compose for local development
  - GitHub Container Registry (GHCR) publishing
  - Entrypoint script (migrations, admin init, Gunicorn)
  - Gunicorn production configuration
  - Volume management and local storage

### Day 17: Database Migrations and Testing
File: 17-day17.md
Topics:
  - Flask-Migrate and Alembic fundamentals
  - Migration history (24 versioned migrations)
  - Creating and applying migrations
  - pytest fixtures and test configuration
  - Test patterns (admin, skipper, crew clients)
  - Test suites for new features (public schedule, crew RSVP, help, AI stats, etc.)
  - Mocking external APIs (Anthropic, SES, requests)

### Day 18: CI/CD, Security and Deployment
File: 18-day18.md
Topics:
  - GitHub Actions workflows (deploy, daily vuln scan, GHCR retention, terraform)
  - Trivy vulnerability scanning (deploy gate + daily, auto-issue with @owner mention)
  - Weekly GHCR retention (keep `:latest`, last 5 semver tags, recent SHA tags, untagged purge)
  - In-progress deployment polling on Lightsail (avoids back-to-back deploy errors)
  - Terraform infrastructure (Lightsail, SES, CloudFront, Route53)
  - AWS Lightsail Container Service deployment
  - Security practices (CSRF, SSRF, path traversal, HMAC, contact-form anti-spam)

### Appendix: Quick Reference
File: 99-appendix.md
Topics:
  - Model reference table (all 8 models + skipper_crew)
  - Permission patterns reference
  - Notification types and triggers
  - SiteSetting keys reference
  - Template filters reference
  - Email templates listing
  - Flask routing patterns
  - SQLAlchemy query examples
  - Docker Compose commands
  - Terraform and Trivy commands
  - Troubleshooting guide
  - Security best practices

# Navigating the Materials

## File Naming Convention

00-index.md       This file - course overview and roadmap
01-day1.md        Day 1 session
02-day2.md        Day 2 session
...
18-day18.md       Day 18 session
99-appendix.md    Reference materials and cheat sheets

## Reading the Code References

Throughout the materials, you'll see references like:

  File: app/models.py:24-60

This means "open the file app/models.py and look at lines 24 through 60."
All file paths are relative to the race-crew-network/ directory.

## Architecture Diagrams

ASCII diagrams show system architecture and data flow. Read them carefully:

```
  [Component A] ---> [Component B]
       |                  ^
       |                  |
       +------------------+
```

Arrows show direction of data flow or dependencies.

## Code Walkthrough Format

Code snippets are formatted as:

  ```python
  def example_function():
      """This is example code from the application."""
      return "Hello"
  ```

Explanation follows the code, connecting it to broader concepts.

# Getting Started

## Step 1: Set Up Your Environment

1. Navigate to the race-crew-network/ directory
2. Copy .env.example to .env
3. Generate a secret key:
   python3 -c "import secrets; print(secrets.token_hex(32))"
4. Update SECRET_KEY in .env with the generated value

## Step 2: Start the Application

1. Build and start containers:
   docker compose up --build

2. Wait for all services to be healthy
3. The entrypoint script automatically:
   - Runs database migrations
   - Creates the admin account from INIT_ADMIN_EMAIL/INIT_ADMIN_PASSWORD

4. Access the app at http://localhost

## Step 3: Begin Day 1

Open 01-day1.md and start your learning journey!

# Learning Objectives

By the end of this 18-day program, you will understand:

### Flask Fundamentals
- Application factory pattern
- Blueprint organization (6 blueprints)
- Route handlers and HTTP methods
- Template rendering with Jinja2
- Form processing and flash messages
- Context processors and template filters
- Configuration management

### Database and ORM
- SQLAlchemy models and relationships (10 models)
- Self-referential many-to-many relationships
- Database migrations with Alembic (24 migrations)
- Query patterns and filtering
- Permission scoping on queries

### Authentication and Security
- Flask-Login integration
- Password hashing with bcrypt
- Token-based authentication (invite, calendar, password reset)
- Forgot/reset password flow with 1-hour expiry
- CSRF protection
- Role-based access control (Admin/Skipper/Crew)
- Admin impersonation
- HMAC token verification (unsubscribe)
- SSRF, path traversal, and contact-form (honeypot+timestamp) protections

### Email and Notifications
- AWS SES email integration
- RSVP notifications (per-event and digest)
- Scheduled reminders
- Bounce and complaint handling
- One-click unsubscribe (RFC 8058)

### AI Integration
- Claude API for data extraction
- Prompt engineering for structured output (with city/state inference)
- File parsing (PDF, DOCX, TXT, XLSX)
- SSE streaming for long-running tasks
- Token+cost logging, monthly budget cap, 80% alert email
- AI Statistics admin dashboard

### Docker and Deployment
- Multi-container applications
- Container networking and volumes
- Production server configuration
- Cloud deployment with AWS Lightsail
- CI/CD with GitHub Actions (deploy, vuln scan, GHCR retention, terraform)
- Lightsail in-progress deployment polling (no back-to-back deploy errors)
- Weekly GHCR image retention policy
- Terraform infrastructure as code
- Trivy vulnerability scanning with auto-issue creation

### Advanced Features
- S3/local storage abstraction
- iCalendar feed generation
- PDF generation with WeasyPrint
- Public per-skipper schedule pages (slug-based, anonymous access)
- Responsive design with Bootstrap 5
- Avatar system (SVG + photo)
- Runtime configuration via SiteSetting
- Email queue and bounce/complaint webhooks

# Support and Tips

## Stuck on a Concept?

1. Re-read the relevant section slowly
2. Open the referenced file and read the code
3. Check the 99-appendix.md for quick reference
4. Search for the topic in Flask documentation
5. Review earlier sessions for foundational concepts

## Best Practices for Learning

- Don't rush - take time to understand each concept
- Type out code examples yourself (don't just read)
- Experiment with small changes to see what happens
- Use print() statements to debug and explore
- Keep a learning journal of new concepts
- Draw your own diagrams to solidify understanding

## Docker Tips

- Keep Docker Desktop running while working
- Use 'docker compose logs' to debug issues
- Restart containers with 'docker compose restart'
- Fresh start: 'docker compose down -v && docker compose up --build'

## Testing Your Understanding

After each session, ask yourself:
1. Can I explain this concept to someone else?
2. Do I understand why the code is structured this way?
3. Could I modify this feature or add a similar one?
4. What security considerations does this code address?

# Ready to Begin?

You now have everything you need to start your Flask learning journey!

Open 01-day1.md and let's build something great together.

Happy coding!

# Course Information

Application: Race Crew Network v0.73.2
Python: 3.13+
Flask: 3.x
Training Version: 3.1
Last Updated: 2026-04

Repository: race-crew-network/
Documentation: README.md, CLAUDE.md
