#!/bin/sh
set -e

DOMAIN=${DOMAIN_NAME:-localhost}

if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    echo "SSL certificates found for $DOMAIN, enabling HTTPS"
    envsubst '${DOMAIN_NAME}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf
    envsubst '${DOMAIN_NAME}' < /etc/nginx/templates/ssl.conf.template > /etc/nginx/conf.d/ssl.conf

    # Reload nginx every 6 hours to pick up renewed certificates
    (while true; do sleep 6h; nginx -s reload 2>/dev/null || true; done) &
else
    echo "No SSL certificates found for $DOMAIN, running HTTP-only mode"
    cat > /etc/nginx/conf.d/default.conf << HTTPCONF
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 10M;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
HTTPCONF
fi

exec nginx -g "daemon off;"
