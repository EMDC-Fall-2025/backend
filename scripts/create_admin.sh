#!/bin/bash
# Script to create an admin account in Docker
# Usage: ./create_admin.sh [username] [password] [first_name] [last_name]

set -e

cd /backend

USERNAME=${1:-"admin@example.com"}
PASSWORD=${2:-"admin123"}
FIRST_NAME=${3:-"Admin"}
LAST_NAME=${4:-"User"}

echo "Creating admin account..."
echo "Username: $USERNAME"
echo "Name: $FIRST_NAME $LAST_NAME"

python manage.py create_first_admin \
    --username "$USERNAME" \
    --password "$PASSWORD" \
    --first-name "$FIRST_NAME" \
    --last-name "$LAST_NAME"

echo "✓ Admin account created successfully!"

