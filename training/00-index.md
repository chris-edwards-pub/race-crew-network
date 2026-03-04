# Race Crew Network - Flask Application Training: 10-Day Curriculum

## Course Overview

This training program teaches you how to build and deploy a production-ready
Flask web application through the study of the Race Crew Network app.
Over 10 days, you'll learn Flask fundamentals, database management with
SQLAlchemy, authentication, file uploads, calendar integration, AI-powered
data import, cloud storage, and containerized cloud deployment.

## Target Audience

IT professionals with:
- Basic Python knowledge (variables, functions, classes)
- Docker familiarity (containers, images, compose)
- Interest in web application development
- Little to no Flask experience (we'll teach you!)

## What You'll Build Understanding of

A complete web application for managing sailing regatta events:
- User authentication with role-based access (Admin/Crew)
- Invite-based registration system
- CRUD operations for regatta events
- RSVP system with Yes/No/Maybe responses
- Document upload and management (PDFs, external links)
- AI-powered schedule import from URLs (Anthropic Claude API)
- Document discovery with SSE streaming progress
- iCal calendar feed integration
- PDF schedule generation with WeasyPrint
- S3-compatible cloud storage for file uploads
- Production deployment with Docker on AWS Lightsail

## Technical Stack You'll Master

- Python 3.13 & Flask 3.1.0 web framework
- SQLAlchemy ORM for database operations
- Flask-Login for authentication
- Flask-Migrate for database schema management
- MySQL 8.0 database
- Gunicorn WSGI server
- Docker Compose orchestration (local dev)
- AWS Lightsail Container Service (production)
- S3-compatible object storage (Lightsail buckets)
- Anthropic Claude API for AI-powered imports
- WeasyPrint for PDF generation
- Bootstrap 5 for responsive frontend

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

1. Read each session sequentially (Day 1 → Day 10)
2. Have the code repository open while reading
3. Follow along by examining the referenced files
4. Take notes on concepts that are new to you
5. Pause to explore code sections in detail
6. Return to earlier sessions as needed for review

## Time Commitment

Each session: 1-2 hours of focused reading and code exploration
Total course: ~15-20 hours spread over 10 workdays
Best pace: One session per day with hands-on exploration

# Session Roadmap

### Day 1: Introduction and Environment Setup
File: 01-day1.md
Topics:
  - Application overview and feature tour
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
  - Blueprint registration and organization
  - Application context and lifecycle

### Day 3: Database Models and SQLAlchemy
File: 03-day3.md
Topics:
  - Object-Relational Mapping (ORM) concepts
  - User, Regatta, Document, and RSVP models
  - Database relationships and foreign keys
  - Password hashing with bcrypt
  - Database schema design

### Day 4: Authentication and User Management
File: 04-day4.md
Topics:
  - Flask-Login integration
  - Login/logout implementation
  - Invite-based registration system
  - Token generation for security
  - User profile management
  - Admin user administration

### Day 5: Regatta Management (CRUD Operations)
File: 05-day5.md
Topics:
  - RESTful route design in Flask
  - Create, Read, Update, Delete operations
  - Form processing and validation
  - Date handling in Python
  - Permission checks and admin-only routes
  - Flash messages for user feedback

### Day 6: RSVP System and Database Relationships
File: 06-day6.md
Topics:
  - Many-to-many relationships
  - Upsert pattern (update or insert)
  - SQLAlchemy lazy loading
  - Custom Jinja2 template filters
  - Status tracking and display

### Day 7: Document Upload and File Handling
File: 07-day7.md
Topics:
  - File upload processing with Flask
  - UUID-based secure filename generation
  - Supporting both file uploads and external URLs
  - S3-compatible cloud storage abstraction
  - Presigned URLs for secure file downloads
  - File size limits and validation

### Day 8: Calendar Integration (iCal Feeds)
File: 08-day8.md
Topics:
  - iCalendar format (RFC 5545)
  - icalendar Python library
  - Token-based feed authentication
  - Generating calendar events
  - All-day event handling
  - Calendar subscription URLs

### Day 9: Docker and Containerization
File: 09-day9.md
Topics:
  - Dockerfile structure and best practices
  - Multi-container orchestration with docker-compose
  - Container networking and service discovery
  - Volume persistence for data
  - Health checks for dependencies
  - Gunicorn production configuration
  - GitHub Container Registry (GHCR)

### Day 10: Database Migrations and Deployment
File: 10-day10.md
Topics:
  - Flask-Migrate and Alembic
  - Creating and applying database migrations
  - Automatic migration on startup
  - AWS Lightsail Container Service deployment
  - GitHub Actions CI/CD pipeline
  - Environment variables in production
  - Managed database and automated backups

### Appendix: Quick Reference
File: 99-appendix.md
Topics:
  - Flask routing patterns
  - SQLAlchemy query examples
  - Jinja2 template syntax
  - Docker Compose commands
  - Flask CLI commands
  - Troubleshooting guide
  - Security best practices
  - Further reading resources

# Navigating the Materials

## File Naming Convention

00-index.md       This file - course overview and roadmap
01-day1.md        Day 1 session
02-day2.md        Day 2 session
...
10-day10.md       Day 10 session
99-appendix.md    Reference materials and cheat sheets

## Reading the Code References

Throughout the materials, you'll see references like:

  File: app/models.py:15-20

This means "open the file app/models.py and look at lines 15 through 20."
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
3. Open a new terminal and create an admin account:
   docker compose exec web flask create-admin

4. Access the app at http://localhost

## Step 3: Begin Day 1

Open 01-day1.md and start your learning journey!

# Learning Objectives

By the end of this 10-day program, you will understand:

### Flask Fundamentals
- Application factory pattern
- Blueprint organization
- Route handlers and HTTP methods
- Template rendering with Jinja2
- Form processing
- Flash messages
- Configuration management

### Database and ORM
- SQLAlchemy models and relationships
- Database migrations with Alembic
- Query patterns and filtering
- Foreign keys and constraints
- Transaction management

### Authentication and Security
- Flask-Login integration
- Password hashing with bcrypt
- Token-based authentication
- CSRF protection
- Role-based access control
- Secure file handling

### Docker and Deployment
- Multi-container applications
- Container networking
- Volume management
- Production server configuration
- Cloud deployment with AWS Lightsail
- CI/CD with GitHub Actions

### Advanced Features
- File upload handling with S3 storage
- iCalendar feed generation
- AI-powered data import (Anthropic API)
- PDF generation with WeasyPrint
- Custom CLI commands
- Database relationship patterns
- Template filters

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

Application: Race Crew Network
Version: 0.34.2
Python: 3.13+
Flask: 3.1.0
Training Version: 2.0
Last Updated: 2026-03

Repository: race-crew-network/
Documentation: README.md, CLAUDE.md
