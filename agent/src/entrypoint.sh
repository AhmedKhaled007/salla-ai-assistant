#!/bin/bash
set -e

# Run database migrations
echo "Running database migrations..."
# Alembic is configured to look for alembic.ini in the current directory or via -c
# We run it from /app/src/agent where alembic.ini is located
cd /app/src/agent
alembic upgrade head
cd /app

# Start the application
echo "Starting Salla AI Agent..."
if [ "$ENVIRONMENT" = "development" ]; then
    echo "Running in DEVELOPMENT mode with reload"
    exec uvicorn agent.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000} --reload
else
    echo "Running in PRODUCTION mode"
    exec uvicorn agent.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000}
fi