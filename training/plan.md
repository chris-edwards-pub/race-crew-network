# Overview

Create a 10-day training curriculum for an IT professional with Python/Docker experience but no Flask knowledge. The curriculum will explain the Race Crew Network Regatta Schedule Flask application through 12 text files.

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
Status: Already created
Contents: Course overview, prerequisites, roadmap, navigation guide

### Daily Lesson Files (10 files)

Paths: 01-day1.md through 10-day10.md

**Day 1: Introduction & Environment Setup**
- Application overview and feature tour
- Docker Compose architecture (3 containers: web, db, nginx)
- Running the app locally
- Creating admin account with Flask CLI
- Basic Flask concepts: routes, templates, blueprints

**Day 2: Flask Application Factory Pattern**
- The create_app() factory pattern
- Extension initialization (SQLAlchemy, Flask-Login, Flask-Migrate, CSRF)
- Configuration management with environment variables
- Blueprint registration
- Application context and lifecycle

**Day 3: Database Models & SQLAlchemy ORM**
- Object-Relational Mapping concepts
- User model (password hashing with bcrypt)
- Regatta model (events with dates/locations)
- Document model (file uploads + external URLs)
- RSVP model (many-to-many relationships)
- Database schema design and foreign keys

**Day 4: Authentication & User Management**
- Flask-Login integration and UserMixin
- Login/logout implementation
- Invite-based registration system with tokens
- User profile management
- Admin user administration
- Authorization patterns (@login_required, role checks)

**Day 5: Regatta Management (CRUD Operations)**
- RESTful route design in Flask
- Create, Read, Update, Delete operations
- Form processing with request.form
- Date handling in Python
- Permission checks (admin-only routes)
- Flash messages for user feedback

**Day 6: RSVP System & Database Relationships**
- Many-to-many relationship implementation
- Upsert pattern (update or insert logic)
- SQLAlchemy lazy vs eager loading
- Custom Jinja2 template filters
- Status display and crew initials

**Day 7: Document Upload & File Handling**
- File upload processing in Flask
- UUID-based secure filename generation
- Supporting both uploads and external URLs
- Docker volume management for storage
- Secure file downloads with send_from_directory
- File size limits and validation

**Day 8: Calendar Integration (iCal Feeds)**
- iCalendar format (RFC 5545)
- Using the icalendar Python library
- Token-based feed authentication
- Generating calendar events
- All-day event handling
- Calendar subscription URLs

**Day 9: Docker & Containerization**
- Dockerfile structure and best practices
- Multi-container orchestration with docker-compose
- Container networking and service discovery
- Volume persistence for data
- Health checks for database dependencies
- Gunicorn production configuration
- Nginx reverse proxy setup

**Day 10: Database Migrations & Deployment**
- Flask-Migrate and Alembic
- Creating and applying migrations
- Automatic migration on startup
- Production deployment considerations
- Environment variables management
- SSL/HTTPS setup guidance
- Backup strategies

### Appendix File

Path: 99-appendix.md
Contents:
- Flask routing quick reference
- SQLAlchemy query patterns
- Jinja2 template syntax guide
- Docker Compose command cheat sheet
- Flask CLI commands reference
- Common troubleshooting scenarios
- Security best practices checklist
- Further reading resources

## Content Structure (Each Daily Lesson)

1. Learning Objectives (3-5 bullet points)
2. Concepts Covered (technical topics list)
3. File Focus (which files to examine)
4. Code Walkthrough (detailed explanations)
   - Key snippets included inline
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
- Request/response cycle (Day 5)
- Container architecture (Day 9)
- Authentication flow (Day 4)

### Security Notes

Highlight security patterns when encountered:
- Password hashing (Day 3)
- CSRF protection (Day 4)
- File upload security (Day 7)
- Token-based authentication (Day 8)

## Critical Files to Reference

### Core Application

- race-crew-network/app/__init__.py - App factory
- race-crew-network/app/config.py - Configuration
- race-crew-network/app/models.py - All 4 models
- race-crew-network/app/commands.py - CLI commands

### Blueprints (Routes)

- race-crew-network/app/auth/routes.py - Authentication
- race-crew-network/app/regattas/routes.py - CRUD operations
- race-crew-network/app/calendar/routes.py - iCal feeds

### Templates

- race-crew-network/app/templates/base.html - Base template
- race-crew-network/app/templates/index.html - Main page
- race-crew-network/app/templates/regatta_form.html - Form example

### Deployment

- race-crew-network/Dockerfile - Container build
- race-crew-network/docker-compose.yml - Orchestration
- race-crew-network/nginx.conf - Reverse proxy
- race-crew-network/gunicorn.conf.py - WSGI config
- race-crew-network/entrypoint.sh - Startup script
- race-crew-network/requirements.txt - Dependencies

### Database

- race-crew-network/migrations/versions/*.py - Migration examples

## Implementation Steps

1. Day 1-3: Foundation (App structure, models, database)
2. Day 4-6: Core features (Auth, CRUD, relationships)
3. Day 7-8: Advanced features (Files, calendar)
4. Day 9-10: Deployment (Docker, production)
5. Appendix: Quick reference materials

## Verification After Creation

1. Index file exists and provides clear navigation
2. All 10 daily lesson files created (01-10)
3. Appendix file created (99)
4. Each lesson follows the structure template
5. File paths referenced are accurate
6. ASCII diagrams render correctly in plain text
7. Lesson progression is logical and builds on previous days
8. Total word count per lesson is ~1500-2500 words

## Success Criteria

The training materials succeed if:
- Each lesson can be read in 30-60 minutes
- Code explanations reference actual application files
- Flask patterns are clearly explained (not just Python)
- A developer with Python/Docker knowledge can understand the full Flask application architecture after 10 days
- Materials are self-contained in text files (no external dependencies)
- Lessons build progressively from basics to advanced topics
