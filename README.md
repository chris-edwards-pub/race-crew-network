# Thistle Regatta Schedule

A simple web app for organizing Thistle sailboat regattas. Track dates, locations, NOR/SI documents, and crew availability with Yes/No/Maybe RSVPs.

## Features

- Single-page regatta table sorted by date
- Location links to Google Maps
- Upload/download NOR and SI PDFs
- Crew RSVP (Yes / No / Maybe) with color-coded initials
- Admin: add/edit/delete regattas, upload documents, invite crew
- Crew: view schedule, download docs, set RSVP
- Invite-based registration (no public sign-up)

## Tech Stack

- Python 3.11, Flask, SQLAlchemy, Flask-Login
- MySQL 8
- Gunicorn + Nginx
- Docker Compose
- Bootstrap 5

---

## Local Development & Testing

### Prerequisites

- Docker and Docker Compose installed

### 1. Clone and configure

```bash
git clone <your-repo-url>
cd thistle-regatta-schedule
cp .env.example .env
```

Edit `.env` and set a real `SECRET_KEY`:

```bash
# Generate a random key
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Build and start

```bash
docker compose up --build
```

This starts 3 containers:
- **web** — Flask app on Gunicorn (port 8000 internal)
- **db** — MySQL 8 (port 3306 internal)
- **nginx** — Reverse proxy (port 80 exposed)

The app automatically runs database migrations on startup.

### 3. Create admin account

```bash
docker compose exec web flask create-admin
```

You'll be prompted for email, password, display name, and initials.

### 4. Access the app

Open http://localhost in your browser and login with your admin credentials.

### 5. Invite crew

1. Go to **Crew** in the navbar
2. Enter a crew member's email and click **Send Invite**
3. Copy the invite link and send it to them
4. They click the link, set their name/initials/password, and they're in

### 6. Stop

```bash
docker compose down
```

To also remove the database volume (fresh start):

```bash
docker compose down -v
```

---

## AWS Lightsail Deployment

### Option A: Lightsail Container Service (Recommended)

This deploys your containers as a managed service — no EC2 instance to maintain.

#### 1. Install AWS CLI and Lightsail plugin

```bash
# Install AWS CLI if not already installed
brew install awscli

# Install the Lightsail control plugin
brew install aws/tap/lightsailctl
```

#### 2. Create a Lightsail container service

```bash
aws lightsail create-container-service \
  --service-name thistle-regattas \
  --power nano \
  --scale 1
```

The `nano` power is $7/month and is plenty for this app.

#### 3. Build and push the web image

```bash
# Build the image
docker build -t thistle-web .

# Push to Lightsail
aws lightsail push-container-image \
  --service-name thistle-regattas \
  --label web \
  --image thistle-web
```

Note the image name returned (e.g., `:thistle-regattas.web.1`).

#### 4. Create a MySQL database

For Lightsail containers, you need an external database. Use Lightsail's managed database:

```bash
aws lightsail create-relational-database \
  --relational-database-name thistle-db \
  --relational-database-blueprint-id mysql_8_0 \
  --relational-database-bundle-id micro_2_0 \
  --master-database-name regatta \
  --master-username regatta \
  --master-user-password <your-db-password>
```

The `micro_2_0` bundle is $15/month. Alternatively, run MySQL inside the container (not recommended for production data durability).

Get the database endpoint:

```bash
aws lightsail get-relational-database --relational-database-name thistle-db \
  --query 'relationalDatabase.masterEndpoint.address' --output text
```

#### 5. Deploy the container

Create a `lightsail-deploy.json` file:

```json
{
  "serviceName": "thistle-regattas",
  "containers": {
    "web": {
      "image": ":thistle-regattas.web.1",
      "ports": {
        "8000": "HTTP"
      },
      "environment": {
        "SECRET_KEY": "<your-secret-key>",
        "DATABASE_URL": "mysql+pymysql://regatta:<db-password>@<db-endpoint>:3306/regatta",
        "UPLOAD_FOLDER": "/app/uploads"
      }
    }
  },
  "publicEndpoint": {
    "containerName": "web",
    "containerPort": 8000,
    "healthCheck": {
      "path": "/login"
    }
  }
}
```

Deploy:

```bash
aws lightsail create-container-service-deployment \
  --cli-input-json file://lightsail-deploy.json
```

#### 6. Set up custom domain

1. In the Lightsail console, go to your container service
2. Under **Custom domains**, click **Create certificate**
3. Enter `edwards.pub` (and `www.edwards.pub` if desired)
4. Validate via DNS (add the CNAME records shown)
5. Once validated, attach the certificate
6. Update your DNS to point `edwards.pub` to the Lightsail container service endpoint

#### 7. Create admin account

```bash
# Find the container ID
aws lightsail get-container-log --service-name thistle-regattas --container-name web

# SSH isn't directly available with Lightsail containers.
# Instead, add a temporary init route or use the registration flow:
# 1. Temporarily set INIT_ADMIN_EMAIL and INIT_ADMIN_PASSWORD env vars
# 2. Or use Option B (EC2) for easier admin setup
```

For the initial admin setup on Lightsail containers, the simplest approach is to connect to the database directly and insert the admin user, or temporarily add a setup endpoint.

---

### Option B: Lightsail Instance (EC2-like)

If you prefer a traditional VM where you can SSH in and run commands:

#### 1. Create a Lightsail instance

- OS: Amazon Linux 2023
- Blueprint: OS Only
- Plan: $5/month (1GB RAM) or $10/month (2GB RAM)
- Enable SSH

#### 2. SSH in and install Docker

```bash
ssh -i <your-key> ec2-user@<your-instance-ip>

# Install Docker
sudo yum update -y
sudo yum install -y docker
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and back in for group changes
exit
```

#### 3. Deploy the app

```bash
ssh ec2-user@<your-instance-ip>

git clone <your-repo-url>
cd thistle-regatta-schedule
cp .env.example .env
# Edit .env with production values (real SECRET_KEY, strong DB password)

docker compose up -d --build
docker compose exec web flask create-admin
```

#### 4. Set up HTTPS with Let's Encrypt

Update `nginx.conf` for your domain, then:

```bash
# Install certbot on the host
sudo yum install -y certbot

# Stop nginx temporarily
docker compose stop nginx

# Get certificate
sudo certbot certonly --standalone -d edwards.pub

# Update nginx.conf to use SSL (see below)
# Restart
docker compose up -d
```

Updated `nginx.conf` for SSL:

```nginx
server {
    listen 80;
    server_name edwards.pub;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name edwards.pub;
    client_max_body_size 10M;

    ssl_certificate /etc/letsencrypt/live/edwards.pub/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/edwards.pub/privkey.pem;

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Mount the certs in `docker-compose.yml` under the nginx service:

```yaml
volumes:
  - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
  - /etc/letsencrypt:/etc/letsencrypt:ro
ports:
  - "80:80"
  - "443:443"
```

#### 5. Set up DNS

Point `edwards.pub` A record to your Lightsail instance's static IP.

---

## Cost Summary

| Component | Option A (Container) | Option B (Instance) |
|-----------|---------------------|---------------------|
| Compute | $7/mo (nano) | $5-10/mo |
| Database | $15/mo (managed) | $0 (in Docker) |
| **Total** | **$22/mo** | **$5-10/mo** |

Option B is significantly cheaper since the database runs inside Docker on the same instance.

---

## Backups

### Database

```bash
# Dump database to file
docker compose exec db mysqldump -u regatta -pregatta regatta > backup.sql

# Restore from backup
docker compose exec -T db mysql -u regatta -pregatta regatta < backup.sql
```

### Uploaded Documents

```bash
# Copy uploads from Docker volume
docker compose cp web:/app/uploads ./uploads-backup
```

Consider setting up a cron job to back these up to S3 regularly.
