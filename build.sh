#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

# Install python dependencies
pip install -r requirements.txt

# Collect static files into staticfiles/
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate

# Load initial data fixture if data.json exists
if [ -f data.json ]; then
    python manage.py loaddata data.json
fi

# Create superuser from environment variables if set
python manage.py createsuperuser_if_none_exists

