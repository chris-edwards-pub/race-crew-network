# Race Crew Network

A simple web app for organizing sailboat regattas. Track dates, locations, NOR/SI documents, and crew availability with Yes/No/Maybe RSVPs.

## Features

- Single-page regatta table sorted by date
- Location links to Google Maps
- Upload/download NOR and SI PDFs (stored in S3)
- Crew RSVP (Yes / No / Maybe) with color-coded initials
- AI-powered schedule import: paste text or URL, Claude extracts regattas for review and bulk import
- Admin: add/edit/delete regattas, upload documents, invite crew, import schedules
- Crew: view schedule, download docs, set RSVP
- Invite-based registration (no public sign-up)

## Tech Stack

- Python 3.11, Flask, SQLAlchemy, Flask-Login
- MySQL 8 (Lightsail Managed Database in production)
- Gunicorn
- Docker Compose (local dev)
- Bootstrap 5
- GitHub Container Registry (GHCR) for container images
- GitHub Actions for CI/CD

## Architecture

```
Production:
  Lightsail Container Service (Micro) ─── Lightsail Managed MySQL (Micro)
         │                                         │
         ├── GHCR image (Flask/Gunicorn)           └── Automated backups
         ├── Built-in HTTPS + custom domain (www.racecrew.net)
         └── Lightsail Object Storage (S3) ── file uploads

  CloudFront + ACM ─── S3 redirect bucket
         │                    │
         ├── SSL for racecrew.net (naked domain)
         └── 301 redirect → https://www.racecrew.net

Local Development:
  docker-compose up
         │
         ├── web (Flask/Gunicorn)
         └── db (MySQL 8)
```

---

## Local Development & Testing

### Prerequisites

- Python 3.11+
- MySQL 8 installed locally
- Docker and Docker Compose (optional, for containerized dev)

### Quick Start (dev script)

```bash
git clone <your-repo-url>
cd race-crew-network
cp .env.example .env
```

Edit `.env` and set `SECRET_KEY`, `INIT_ADMIN_EMAIL`, `INIT_ADMIN_PASSWORD`, and
optionally `ANTHROPIC_API_KEY` for the AI schedule import feature.

```bash
./dev.sh start
```

This handles everything: creates a virtual environment, installs dependencies,
creates the MySQL database, runs migrations, creates the admin account, and
starts Flask on port 5001. Open http://localhost:5001 and log in.

#### Dev script commands

| Command | Description |
|---------|-------------|
| `./dev.sh start` | Install deps, migrate DB, start Flask (idempotent) |
| `./dev.sh stop` | Stop the Flask server |
| `./dev.sh restart` | Stop and start |
| `./dev.sh reset-db` | Drop DB, recreate, migrate, create admin |
| `./dev.sh status` | Check if Flask is running and DB is accessible |
| `./dev.sh cleanup` | Full teardown: stop server, drop DB, remove .venv |
| `./dev.sh logs` | Tail Flask output |

Set `DEV_PORT` to use a different port (default: 5001).

### Docker Compose (alternative)

```bash
docker compose up --build
```

This starts 2 containers:
- **web** — Flask app on Gunicorn (port 8000 internal, port 80 exposed)
- **db** — MySQL 8 (port 3306 internal)

The app automatically runs database migrations on startup.

```bash
docker compose exec web flask create-admin
```

You'll be prompted for email, password, display name, and initials.

Open http://localhost and login with your admin credentials.

### Invite crew

1. Go to **Crew** in the navbar
2. Enter a crew member's email and click **Send Invite**
3. Copy the invite link and send it to them
4. They click the link, set their name/initials/password, and they're in

### Stop

```bash
./dev.sh stop          # dev script
docker compose down    # Docker
docker compose down -v # Docker + wipe database volume
```

---

## CI/CD Setup (GitHub Actions + Terraform)

Before deploying infrastructure, create a dedicated IAM user with least-privilege
permissions. This user is used by GitHub Actions and Terraform — never use your
personal or root AWS credentials.

### Prerequisites

- AWS CLI installed and configured with admin credentials (`aws configure`)
- GitHub CLI authenticated (`gh auth login`)

### 1. Create IAM user

```bash
aws iam create-user --user-name race-crew-deploy
```

### 2. Create IAM policy

The policy file (`iam-policy.json`) is included in the repo root. Create the policy:

```bash
aws iam create-policy \
  --policy-name race-crew-deploy \
  --policy-document file://iam-policy.json
```

### 3. Attach policy to user

```bash
# Get your account ID
aws sts get-caller-identity --query Account --output text

# Attach the policy (replace <ACCOUNT_ID> with the value above)
aws iam attach-user-policy \
  --user-name race-crew-deploy \
  --policy-arn arn:aws:iam::<ACCOUNT_ID>:policy/race-crew-deploy
```

### 4. Generate access keys

```bash
aws iam create-access-key --user-name race-crew-deploy
```

Save the output — the `SecretAccessKey` is only shown once.

### 5. Store credentials in GitHub Secrets

```bash
gh secret set AWS_ACCESS_KEY_ID
gh secret set AWS_SECRET_ACCESS_KEY
```

You'll be prompted to paste each value.

### Verify setup

```bash
aws iam get-user --user-name race-crew-deploy
aws iam list-attached-user-policies --user-name race-crew-deploy
gh secret list
```

---

## Infrastructure (Terraform)

Infrastructure is managed with Terraform in the `terraform/` directory. Terraform
provisions Lightsail Container Service, Managed MySQL, Object Storage, and DNS.

**Resources provisioned:**
- Lightsail Container Service (`micro` — $10/mo)
- Lightsail Managed MySQL (`micro_1_0` — $15/mo, automated backups)
- Lightsail Object Storage (`small_1_0` — $1/mo, file uploads)
- SSL certificate with DNS validation (Lightsail, for www subdomain)
- ACM certificate with DNS validation (for naked domain)
- CloudFront distribution (naked domain HTTPS → S3 redirect → www)
- S3 bucket (redirect-only, no content)
- Route 53 DNS records (CNAME for www, A-alias for apex → CloudFront, cert validation)
- Bucket access key for app-to-S3 authentication

### First-time setup

Complete the [CI/CD Setup](#cicd-setup-github-actions--terraform) section above first.

#### 1. Create the S3 state bucket

```bash
aws s3api create-bucket \
  --bucket race-crew-tfstate \
  --region us-east-1

aws s3api put-bucket-versioning \
  --bucket race-crew-tfstate \
  --versioning-configuration Status=Enabled

aws s3api put-public-access-block \
  --bucket race-crew-tfstate \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

#### 2. Store secrets in GitHub

```bash
# App secrets
gh secret set SECRET_KEY --body "$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
gh secret set MYSQL_PASSWORD --body "$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
```

#### 3. Store GitHub Variables

```bash
gh variable set DOMAIN_NAME --body "racecrew.net"
gh variable set MYSQL_DATABASE --body "racecrew"
gh variable set MYSQL_USER --body "racecrew"
```

#### 4. Run Terraform

```bash
cd terraform
terraform init
terraform apply \
  -var "db_password=<MYSQL_PASSWORD>" \
  -var "secret_key=<SECRET_KEY>" \
  -var "domain_name=racecrew.net" \
  -var "route53_zone_id=<ZONE_ID>"
```

#### 5. Store Terraform outputs in GitHub

After `terraform apply`, capture the outputs and store them:

```bash
gh variable set CONTAINER_SERVICE_NAME --body "race-crew-network"
gh variable set DB_ENDPOINT --body "$(terraform output -raw database_endpoint):$(terraform output -raw database_port)"
gh variable set BUCKET_NAME --body "$(terraform output -raw bucket_name)"
gh secret set BUCKET_ACCESS_KEY_ID --body "$(terraform output -raw bucket_access_key_id)"
gh secret set BUCKET_SECRET_ACCESS_KEY --body "$(terraform output -raw bucket_secret_access_key)"
```

#### 6. Trigger the first deploy

```bash
gh workflow run deploy.yml
```

#### 7. Get admin credentials

The app auto-generates admin credentials on first boot. Check the container logs
in the Lightsail console or via AWS CLI:

```bash
aws lightsail get-container-log \
  --service-name race-crew-network \
  --container-name web
```

### Managing infrastructure

After initial setup, edit files in `terraform/` and push to `master`. The Terraform
workflow runs plan and apply automatically.

To make changes locally:

```bash
cd terraform
terraform plan \
  -var "db_password=<MYSQL_PASSWORD>" \
  -var "secret_key=<SECRET_KEY>" \
  -var "domain_name=racecrew.net" \
  -var "route53_zone_id=<ZONE_ID>"
```

To tear down everything:

```bash
cd terraform
terraform destroy \
  -var "db_password=<MYSQL_PASSWORD>" \
  -var "secret_key=<SECRET_KEY>" \
  -var "domain_name=racecrew.net" \
  -var "route53_zone_id=<ZONE_ID>"
```

---

## Deployment

Every push to `master` triggers automatic deployment via GitHub Actions. The
workflow has two stages:

1. **Build & Push** — Builds the Docker image in GitHub Actions using BuildKit
   with layer caching, then pushes to GHCR with three tags:
   - `latest` — for docker-compose simplicity
   - Git SHA (e.g. `065d419e...`) — for traceability and rollback
   - Semantic version (e.g. `0.18.0`) — for release tracking
2. **Deploy** — Uses AWS CLI to create a new container service deployment with
   the SHA-tagged image and environment variables from GitHub Secrets/Variables.

The container service handles HTTPS termination, health checks, and rolling
deployments automatically. No SSH, nginx, or certbot required.

### Container images

Images are stored in GHCR at:

```
ghcr.io/chris-edwards-pub/race-crew-network
```

Since the repo is public, the images are public too — no authentication is
needed to pull them.

Browse published images at:
https://github.com/chris-edwards-pub/race-crew-network/pkgs/container/race-crew-network

### Manual deploy

```bash
gh workflow run deploy.yml
```

To deploy a specific branch:

```bash
gh workflow run deploy.yml -f branch=feature/my-branch
```

### Check deploy status

```bash
gh run list --workflow=deploy.yml
```

### Roll back to a specific version

Deploy a previous image tag by creating a new container service deployment:

```bash
aws lightsail create-container-service-deployment \
  --service-name race-crew-network \
  --containers '{"web": {"image": "ghcr.io/chris-edwards-pub/race-crew-network:<SHA_OR_VERSION>", ...}}'
```

Or re-run a previous successful workflow from the GitHub Actions UI.

---

## DNS Setup

DNS is managed by Terraform via Route 53:

- **www.racecrew.net** — CNAME to the Lightsail Container Service. HTTPS is
  handled by a Lightsail-managed SSL certificate with automatic DNS validation
  and renewal.
- **racecrew.net** (naked domain) — A-alias to a CloudFront distribution that
  terminates SSL using an ACM certificate, then forwards to an S3 redirect
  bucket which returns a 301 to `https://www.racecrew.net`.

---

## Cost

| Component | Monthly Cost |
|-----------|-------------|
| Lightsail Container Service (Micro) | $10 |
| Lightsail Managed MySQL (micro_1_0) | $15 |
| Lightsail Object Storage (small_1_0) | $1 |
| S3 state bucket | ~$0 |
| ACM certificate (apex domain) | $0 |
| CloudFront (apex redirect) | $0 (free tier) |
| GitHub Actions | $0 (free tier) |
| GHCR container images | $0 (free for public repos) |
| **Total** | **~$26/mo** |

---

## Backups

### Database

Lightsail Managed MySQL includes automated daily backups with 7-day retention.
Point-in-time restore is available through the Lightsail console or API.

### Uploaded Documents

File uploads are stored in Lightsail Object Storage (S3-compatible) and persist
across container redeployments. Consider enabling bucket versioning for
additional protection.
