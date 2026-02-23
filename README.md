# Race Crew Network

A simple web app for organizing sailboat regattas. Track dates, locations, NOR/SI documents, and crew availability with Yes/No/Maybe RSVPs.

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
cd race-crew-network
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

The policy file (`iam-policy.json`) is included in the repo root:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LightsailFullAccess",
      "Effect": "Allow",
      "Action": "lightsail:*",
      "Resource": "*"
    },
    {
      "Sid": "TerraformStateBucket",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::race-crew-tfstate",
        "arn:aws:s3:::race-crew-tfstate/*"
      ]
    }
  ]
}
```

Create the policy:

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
provisions a Lightsail instance running Amazon Linux 2023 with Docker Compose.

**Resources provisioned:**
- Lightsail instance (`small_3_0` — $10/mo, 2GB RAM)
- Static IP address (free when attached)
- Firewall rules (ports 22, 80, 443)
- SSH key pair for deployment

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

#### 2. Generate SSH key pair

```bash
ssh-keygen -t ed25519 -C "race-crew-deploy" \
  -f ~/.ssh/race-crew-deploy -N ""
```

#### 3. Store secrets in GitHub

```bash
# SSH keys
gh secret set LIGHTSAIL_SSH_PRIVATE_KEY < ~/.ssh/race-crew-deploy
gh secret set LIGHTSAIL_SSH_PUBLIC_KEY < ~/.ssh/race-crew-deploy.pub

# Repository URL
gh secret set REPO_URL --body "https://github.com/<owner>/<repo>.git"

# App secrets
gh secret set SECRET_KEY --body "$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
gh secret set MYSQL_ROOT_PASSWORD --body "$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
gh secret set MYSQL_DATABASE --body "racecrew"
gh secret set MYSQL_USER --body "racecrew"
gh secret set MYSQL_PASSWORD --body "$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
```

#### 4. Store GitHub Variables

```bash
gh variable set DOMAIN_NAME --body "racecrew.net"
gh variable set CERTBOT_EMAIL --body "you@example.com"
gh variable set MYSQL_DATABASE --body "racecrew"
gh variable set MYSQL_USER --body "racecrew"
```

#### 5. Run Terraform

```bash
cd terraform
terraform init
terraform apply \
  -var "ssh_public_key=$(cat ~/.ssh/race-crew-deploy.pub)" \
  -var "repo_url=https://github.com/<owner>/<repo>.git"
```

#### 6. Store the instance IP

```bash
gh variable set LIGHTSAIL_HOST --body "$(terraform output -raw static_ip)"
```

#### 7. Wait and verify

The instance takes ~3 minutes to install Docker via user-data. Then verify:

```bash
STATIC_IP=$(terraform output -raw static_ip)
ssh -i ~/.ssh/race-crew-deploy ec2-user@$STATIC_IP \
  "docker --version && docker compose version && ls ~/app"
```

#### 8. Trigger the first deploy

```bash
gh workflow run deploy.yml
```

#### 9. Get admin credentials

The app auto-generates admin credentials on first boot:

```bash
ssh -i ~/.ssh/race-crew-deploy ec2-user@$STATIC_IP \
  "cd ~/app && docker compose logs web 2>&1 | grep -A 6 'INITIAL ADMIN'"
```

### Managing infrastructure

After initial setup, edit files in `terraform/` and push to `master`. The Terraform
workflow runs plan and apply automatically.

To make changes locally:

```bash
cd terraform
terraform plan \
  -var "ssh_public_key=$(cat ~/.ssh/race-crew-deploy.pub)" \
  -var "repo_url=https://github.com/<owner>/<repo>.git"
terraform apply \
  -var "ssh_public_key=$(cat ~/.ssh/race-crew-deploy.pub)" \
  -var "repo_url=https://github.com/<owner>/<repo>.git"
```

To tear down everything:

```bash
cd terraform
terraform destroy \
  -var "ssh_public_key=$(cat ~/.ssh/race-crew-deploy.pub)" \
  -var "repo_url=https://github.com/<owner>/<repo>.git"
```

---

## Deployment

Every push to `master` triggers automatic deployment via GitHub Actions.

The deploy workflow SSHes into the Lightsail instance, pulls the latest code,
writes the `.env` file from GitHub Secrets, and runs `docker compose up -d --build`.

### Manual deploy

```bash
gh workflow run deploy.yml
```

### Check deploy status

```bash
gh run list --workflow=deploy.yml
```

### SSH into the instance

```bash
ssh -i ~/.ssh/race-crew-deploy ec2-user@<STATIC_IP>
cd ~/app
docker compose ps
docker compose logs web
```

---

## DNS Setup

Point your domain's A record to the static IP from `terraform output static_ip`.

HTTPS is provisioned automatically on deploy via Let's Encrypt. The first deploy
obtains the certificate; subsequent deploys reuse it. Certificates auto-renew
every 60 days.

---

## Cost

| Component | Monthly Cost |
|-----------|-------------|
| Lightsail instance (small_3_0, 2GB RAM) | $10 |
| Static IP (attached to instance) | $0 |
| S3 state bucket | ~$0 |
| GitHub Actions | $0 (free tier) |
| **Total** | **~$10/mo** |

---

## Backups

### Database

```bash
# Dump database to file
docker compose exec db mysqldump -u racecrew -pracecrew racecrew > backup.sql

# Restore from backup
docker compose exec -T db mysql -u racecrew -pracecrew racecrew < backup.sql
```

### Uploaded Documents

```bash
# Copy uploads from Docker volume
docker compose cp web:/app/uploads ./uploads-backup
```

Consider setting up a cron job to back these up to S3 regularly.
