# Overview

Create an 18-day training curriculum for an IT professional with Python/Docker experience but no Flask knowledge. The curriculum will explain the Race Crew Network v0.61.0 Flask application through 21 text files.

## User Requirements

- Target Audience: IT professional with Python and Docker knowledge, zero Flask experience
- Format: Text files with index and appendix
- Code Display: Hybrid (key snippets included, longer sections referenced by file path)
- Style: Explanation-focused (no exercises, just understanding existing code)
- Focus: Flask patterns and Docker deployment (minimal Python basics)
- Lesson Length: Concise 30-60 min sessions (~1500-2500 words)

## Files to Create

### Index File

Path: 00-index.md
Contents: Course overview, prerequisites, 18-day roadmap, navigation guide

### Daily Lesson Files (18 files)

Paths: 01-day1.md through 18-day18.md

#### Phase 1: Foundations (Days 1-4)

**Day 1: Introduction & Environment Setup**
- Application overview and feature tour (3 roles, 6 blueprints)
- Docker Compose architecture (web, db containers)
- Running the app locally
- Creating admin account with Flask CLI
- Basic Flask concepts: routes, templates, blueprints

**Day 2: Flask Application Factory Pattern**
- The create_app() factory pattern
- Extension initialization (SQLAlchemy, Flask-Login, Flask-Migrate, CSRF)
- Configuration management with environment variables
- Blueprint registration (6 blueprints)
- Context processors and template filters (avatar_svg, user_icon, sort_rsvps, regatta_days)

**Day 3: Database Models & SQLAlchemy ORM**
- Object-Relational Mapping concepts
- 8 models: User, Regatta, Document, RSVP, ImportCache, TaskResult, NotificationLog, SiteSetting
- skipper_crew association table (self-referential M2M)
- User model expansion (avatar_seed, profile_image_key, notification_prefs, email_opt_in)
- visible_regattas() and permission scoping

**Day 4: Authentication & User Management**
- Flask-Login integration and UserMixin
- Login/logout implementation
- Invite-based registration with tokens
- Skipper invites and email invites
- Auto-link crew to inviting skipper
- Avatar seed generation on registration
- Admin user administration (edit, delete, impersonate)

#### Phase 2: Core Features (Days 5-9)

**Day 5: Multi-User Role System & Permissions**
- Three roles: Admin, Skipper, Crew
- permissions.py: require_admin, require_skipper, can_manage_regatta, can_rsvp_to_regatta
- Admin impersonation flow (session-based)
- Role-based navbar and UI visibility

**Day 6: Event Management (CRUD Operations)**
- RESTful route design in Flask
- Create, Read, Update, Delete operations
- Updated permissions model (skipper can CRUD own events)
- Bulk delete with checkbox selection
- Auto-generated Google Maps links
- Schedule filters (skipper, RSVP status)

**Day 7: RSVP System & Schedule View**
- Schedule switcher (My Schedule / All Schedules)
- RSVP with filter state preservation
- PDF schedule generation with WeasyPrint
- RSVP notification triggers
- Custom template filters (sort_rsvps, regatta_days)

**Day 8: Document Upload & Storage**
- File upload processing with Flask
- S3/local storage abstraction (app/storage.py)
- Profile image uploads with validation
- Path traversal protection
- Presigned URLs for secure downloads
- Storage blueprint for local file serving

**Day 9: Skipper & Crew Management**
- My Crew page and crew listing
- Invite crew (new user or existing user)
- Remove crew member
- Create/delete schedule (self-service skipper)
- Leave skipper (crew self-service)

#### Phase 3: Communication & Integration (Days 10-13)

**Day 10: Email Service with AWS SES**
- AWS SES integration via boto3
- HMAC-SHA256 unsubscribe tokens
- RFC 8058 one-click unsubscribe
- Bounce and complaint webhook handling (SNS)
- Email opt-in/opt-out model
- SiteSetting-based email configuration

**Day 11: Notification System**
- Manual crew notification (skipper selects events + crew)
- RSVP-to-skipper notifications (per-RSVP and digest modes)
- Scheduled reminders (RSVP reminder, coming-up reminder)
- Crew digest emails
- NotificationLog for deduplication
- Digest flush on preference switch

**Day 12: Calendar Integration**
- iCalendar format (RFC 5545)
- Token-based feed authentication
- Subscribe page with webcal:// URLs
- Scoped feeds (only yes/maybe RSVPs)
- RSVP status in event descriptions
- Email links to calendar subscribe

**Day 13: AI-Powered Schedule Import**
- Claude API integration (anthropic SDK)
- Extraction prompt engineering
- File import (PDF, DOCX, TXT via file_utils.py)
- ImportCache for result caching
- SSE streaming progress
- SSRF protection (_is_private_ip)
- Document discovery (level-1 and deep crawl)

#### Phase 4: Operations & Advanced Topics (Days 14-18)

**Day 14: User Interface & Responsive Design**
- Bootstrap 5 responsive grid and breakpoints
- Navbar (expand-md, collapse, mobile toggler)
- Avatar system (Multiavatar SVG + profile photos)
- user_icon template filter (photo with avatar fallback)
- Impersonation banner
- Mobile-friendly layout patterns

**Day 15: Site Settings & Admin Configuration**
- SiteSetting model (key/value store)
- Google Analytics settings page
- Email settings page (SES sender, region)
- Runtime config vs environment variables
- Context processor for GA injection

**Day 16: Docker & Containerization**
- Dockerfile structure (Python 3.13-slim base)
- Docker Compose for local dev
- GHCR image publishing
- Entrypoint script (migrations + admin init + Gunicorn)
- Gunicorn configuration
- Local storage via storage blueprint

**Day 17: Database Migrations & Testing**
- Flask-Migrate and Alembic
- Migration history (16 migrations)
- Creating and applying migrations
- pytest fixtures (session-scoped app, autouse cleanup)
- Test patterns (admin/skipper/crew clients)
- Mocking external APIs (Anthropic, SES)

**Day 18: CI/CD, Security & Deployment**
- GitHub Actions workflows (deploy, vulnerability scan, terraform)
- Trivy vulnerability scanning (deploy-gate + daily)
- Terraform infrastructure as code (Lightsail, SES, CloudFront, Route53)
- AWS Lightsail Container Service deployment
- Security practices (CSRF, SSRF, path traversal, HMAC)

### Appendix File

Path: 99-appendix.md
Contents:
- Permission patterns reference
- Notification types and triggers
- SiteSetting keys reference
- Template filters reference
- Email templates listing
- Terraform resource reference
- Trivy/security commands
- Model reference table (all 8 models + skipper_crew)
- Flask routing quick reference
- SQLAlchemy query patterns
- Docker Compose command cheat sheet
- Common troubleshooting scenarios

## Content Structure (Each Daily Lesson)

1. Learning Objectives (3-5 bullet points)
2. Concepts Covered (technical topics list)
3. File Focus (which files to examine)
4. Code Walkthrough (detailed explanations)
   - Key snippets included inline (5-20 lines)
   - Longer code sections referenced by file:line
5. Architecture Diagrams (ASCII art where helpful)
6. Key Takeaways (summary and connections)

## Writing Guidelines

### Tone & Approach

- Professional and technical
- Assume Python/Docker familiarity
- Focus on Flask-specific patterns
- Explain WHY decisions were made, not just WHAT the code does
- Connect concepts to broader web development patterns

### Code Examples

- Include inline: Critical snippets (5-20 lines) that demonstrate key patterns
- Reference by path: Full functions, longer route handlers
- Always provide file paths and line numbers for reference
- Format: File: app/models.py:25-45

### Architecture Diagrams

Use ASCII art for:
- Application initialization flow (Day 2)
- Database ER diagram (Day 3)
- Request/response cycle (Day 6)
- Container architecture (Day 16)
- Authentication flow (Day 4)
- Notification flow (Day 11)
- CI/CD pipeline (Day 18)

### Security Notes

Highlight security patterns when encountered:
- Password hashing (Day 3)
- CSRF protection (Day 4)
- HMAC unsubscribe tokens (Day 10)
- SSRF protection (Day 13)
- Path traversal protection (Day 8)
- File upload validation (Day 8)

## Critical Files to Reference

### Core Application

- app/__init__.py - App factory, context processors, template filters
- app/config.py - Configuration
- app/models.py - 8 models + skipper_crew table
- app/permissions.py - Role-based permission helpers
- app/commands.py - CLI commands
- app/storage.py - S3/local storage abstraction

### Blueprints (Routes)

- app/auth/routes.py - Authentication, user management, crew management
- app/regattas/routes.py - Event CRUD, RSVP, documents, notifications
- app/admin/routes.py - Import, settings, document discovery
- app/calendar/routes.py - iCal feeds, subscribe page
- app/email/routes.py - Unsubscribe, SES webhooks
- app/storage_routes.py - Local file serving

### Services

- app/admin/email_service.py - AWS SES email sending
- app/admin/ai_service.py - Claude API integration
- app/admin/file_utils.py - File text extraction
- app/notifications/service.py - Notification logic

### Templates

- app/templates/base.html - Base template with navbar
- app/templates/index.html - Main schedule page
- app/templates/email/*.html - Email templates

### Deployment

- Dockerfile - Container build
- docker-compose.yml - Local orchestration
- gunicorn.conf.py - WSGI config
- entrypoint.sh - Startup script
- .github/workflows/deploy.yml - CI/CD pipeline
- .github/workflows/vulnerability-scan.yml - Security scanning
- .github/workflows/terraform.yml - Infrastructure automation
- terraform/main.tf - AWS infrastructure

### Tests

- tests/conftest.py - Test fixtures
- tests/test_*.py - Test modules

## Implementation Steps

1. Phase 1: Foundation (Days 1-4) — App structure, models, auth
2. Phase 2: Core features (Days 5-9) — Roles, CRUD, RSVP, storage, crew
3. Phase 3: Communication (Days 10-13) — Email, notifications, calendar, AI
4. Phase 4: Operations (Days 14-18) — UI, settings, Docker, testing, CI/CD
5. Appendix: Comprehensive reference materials

## Verification After Creation

1. All 21 files present (00-index, 01-18, 99-appendix, plan)
2. No old numbered files remain
3. Each lesson follows the structure template
4. File paths and line numbers reference actual source code
5. Cross-references between lessons are consistent
6. Lesson progression is logical and builds on previous days
7. Total word count per lesson is ~1500-2500 words
8. Version metadata updated to v0.61.0 / Training v3.0

## Success Criteria

The training materials succeed if:
- Each lesson can be read in 30-60 minutes
- Code explanations reference actual application files
- Flask patterns are clearly explained (not just Python)
- A developer with Python/Docker knowledge can understand the full application after 18 days
- Materials are self-contained in text files (no external dependencies)
- Lessons build progressively from basics to advanced topics
