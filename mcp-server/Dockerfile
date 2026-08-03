# MCP Server Dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl

# Install uv for faster Python package management
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv pip install --system -e .

# Create non-root user for security
RUN useradd -m -u 1000 mcp
USER mcp

# Expose the MCP port
EXPOSE 8001

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the MCP server
CMD ["python", "-m", "mcp_server.main", "--transport", "http"]
