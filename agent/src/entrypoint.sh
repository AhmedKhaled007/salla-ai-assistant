#!/bin/bash
set -e

# Run database migrations
echo "Running database migrations..."
alembic -c /app/src/agent/alembic.ini upgrade head

# Start the application
echo "Starting Salla AI Agent..."
if [ "$ENVIRONMENT" = "development" ]; then
    echo "Running in DEVELOPMENT mode with reload"
    exec uvicorn agent.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000} --reload
else
    echo "Running in PRODUCTION mode"
    exec uvicorn agent.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000}
fi