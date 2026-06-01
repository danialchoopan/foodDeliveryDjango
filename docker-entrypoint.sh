#!/bin/bash

# Docker entrypoint script for DanialFood

set -e

echo "Waiting for PostgreSQL to be ready..."
while ! nc -z ${DB_HOST:-localhost} ${DB_PORT:-5432}; do
  sleep 1
done
echo "PostgreSQL is ready!"

echo "Waiting for Redis to be ready..."
while ! nc -z ${REDIS_HOST:-localhost} ${REDIS_PORT:-6379}; do
  sleep 1
done
echo "Redis is ready!"

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if it doesn't exist (optional)
echo "Creating superuser if not exists..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print("Superuser created: admin / admin123")
END

echo "Starting application..."

exec "$@"

