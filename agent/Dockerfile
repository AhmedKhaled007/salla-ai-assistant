# Agent Service Dockerfile
FROM python:3.13-slim

WORKDIR /app
# Install system dependencies
RUN apt-get update && apt-get install -y curl
# Install uv for faster Python package management
RUN pip install uv

# Copy project definition first to leverage cache
COPY pyproject.toml .

# Copy source code
COPY src/ src/

RUN uv pip install --system -e '.[dev]'

RUN useradd -m -u 1000 agent && \
    mkdir -p /app/conversations && \
    chown -R agent:agent /app

# Expose the API port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# Switch to non-root user
USER agent

# Start the agent service using the entrypoint script
ENTRYPOINT ["/app/src/entrypoint.sh"]
