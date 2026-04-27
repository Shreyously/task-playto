#!/bin/bash

# Exit on error
set -e

echo "Starting Monolith Mode..."

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start Gunicorn (Web Server) in the background
echo "Starting Gunicorn..."
gunicorn playto.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --access-logfile - &

# Start Celery Worker in the background
echo "Starting Celery Worker..."
celery -A playto worker -l info --concurrency 2 &

# Start Celery Beat in the foreground (this will keep the container alive)
echo "Starting Celery Beat..."
celery -A playto beat -l info
