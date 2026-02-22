#!/bin/bash
set -euo pipefail

# Obtain initial Let's Encrypt SSL certificate.
# Reads DOMAIN_NAME and CERTBOT_EMAIL from the .env file.
# Skips if certificates already exist.

APP_DIR="${1:-/home/ec2-user/app}"

cd "$APP_DIR"

# Load variables from .env
set -a
source .env
set +a

DOMAIN="${DOMAIN_NAME:?DOMAIN_NAME not set in .env}"
EMAIL="${CERTBOT_EMAIL:?CERTBOT_EMAIL not set in .env}"

# Check if certificate already exists
CERT_VOL=$(docker volume inspect "${PWD##*/}_certbot_certs" 2>/dev/null | grep -o '"Mountpoint": "[^"]*"' | cut -d'"' -f4 || true)
if [ -n "$CERT_VOL" ] && [ -f "$CERT_VOL/live/$DOMAIN/fullchain.pem" ]; then
    echo "SSL certificate already exists for $DOMAIN, skipping."
    exit 0
fi

echo "=== Obtaining SSL certificate for $DOMAIN ==="

# Ensure nginx is running (HTTP-only mode) so ACME challenges can be served
docker compose up -d nginx

# Wait for nginx to be ready
sleep 5

# Request certificate using webroot authentication
docker compose run --rm certbot \
    certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

echo "=== Certificate obtained! Restarting nginx with SSL... ==="

# Restart nginx so it picks up the new certificates
docker compose restart nginx

echo "=== SSL setup complete! ==="
echo "Test: curl -I https://$DOMAIN"
