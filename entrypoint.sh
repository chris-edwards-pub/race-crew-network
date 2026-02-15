#!/bin/sh
set -e

echo "Running database migrations..."
flask db upgrade

echo "Initializing admin account if needed..."
flask init-admin

echo "Starting Gunicorn..."
exec gunicorn -c gunicorn.conf.py wsgi:app
