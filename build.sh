#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

# Install python dependencies
pip install -r requirements.txt

# Collect static files into staticfiles/
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate

# Create superuser from environment variables if set
python manage.py createsuperuser_if_none_exists

# (Optional) Seed initial data if database is empty
# python manage.py seed_data

