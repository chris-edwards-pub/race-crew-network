#!/bin/bash
set -euo pipefail

# Obtain initial Let's Encrypt SSL certificate.
# Run once on the Lightsail server after the first deploy.
#
# Usage: bash scripts/init-ssl.sh <domain> <email>
# Example: bash scripts/init-ssl.sh regatta.example.com admin@example.com

DOMAIN="${1:?Usage: $0 <domain> <email>}"
EMAIL="${2:?Usage: $0 <domain> <email>}"
APP_DIR="${3:-/home/ec2-user/app}"

echo "=== Obtaining SSL certificate for $DOMAIN ==="

cd "$APP_DIR"

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
