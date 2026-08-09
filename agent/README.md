# Salla Agent Service

The core "brain" of the Salla AI Assistant. This FastAPI service orchestrates conversations, manages OAuth authentication, and integrates with the MCP (Model Context Protocol) Server to execute tools.

## 🚀 Key Features

*   **FastAPI & Async**: Built for high-concurrency with Python 3.13+ and full async support.
*   **MCP 2026-07-28 Client**: Uses the MCP Python SDK v2 client with automatic protocol negotiation and legacy fallback.
*   **Request Isolation**: Opens one token-scoped MCP connection per agent query and closes it when the query finishes; MCP connections are not stored per user.
*   **OAuth2 Integration**: Handles the application-side flow for Salla App Store authentication.
*   **Database Persistence**: Uses PostgreSQL + SQLAlchemy (Async) to store user sessions, conversation history, and tokens.
*   **Resilience**: Design includes "degraded mode" (starts even if MCP server is down) and gracefull shutdowns.

## 🛠️ Environment Variables

Create a `.env` file in the `agent` directory:

```env
# Database Connection (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname

# AI Configuration (LiteLLM)
LLM_MODEL=gemini/gemini-3-flash-preview
EVAL_MODEL=gemini/gemini-3-flash-preview
GEMINI_API_KEY=your_gemini_api_key

# MCP Connection (Integration Layer)
MCP_SERVER_URL=http://localhost:8001/mcp

# Salla OAuth Credentials
SALLA_CLIENT_ID=your_client_id
SALLA_CLIENT_SECRET=your_client_secret
SALLA_REDIRECT_URI=http://localhost:3000/callback

# Security
SECRET_KEY=your_secret_key
API_HOST=0.0.0.0
API_PORT=8000

# Phoenix tracing (optional)
PHOENIX_ENABLED=false
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
PHOENIX_BASE_URL=http://localhost:6006
PHOENIX_PROJECT_NAME=salla-agent-dev
PHOENIX_PROTOCOL=http/protobuf
```

When `PHOENIX_ENABLED` is false or tracing initialization fails, the agent keeps
running without telemetry. Docker Compose enables tracing against the bundled,
persistent Phoenix service at `http://localhost:6006`.

Each user turn is recorded as a `salla-agent` span and grouped by conversation
ID in Phoenix Sessions. LiteLLM calls appear beneath the turn, while MCP calls
appear as `mcp.<tool_name>` spans.

## 📦 Installation & Running

### Using uv (Recommended)

This project uses `uv` for ultra-fast dependency management.

1.  **Sync Dependencies**:
    ```bash
    uv sync
    ```

2.  **Run Migrations**:
    ```bash
    uv run alembic upgrade head
    ```

3.  **Start Server**:
    ```bash
    uv run python -m agent.main
    ```

### Using Standard Pip

```bash
pip install -e .
python -m agent.main
```

## 🧪 Testing

Run the agent and evaluation tests inside Docker from the repository root:

```bash
docker compose run --rm --no-deps --entrypoint python agent -m pytest
```

## 🏗️ Architecture

The Agent Service sits in the middle of the stack:

1.  Receives user queries + OAuth token from **Frontend**.
2.  Retrieves conversation history from **PostgreSQL**.
3.  Sends context to **LLM**.
4.  If LLM requests a tool (e.g., `list_products`), Agent forwards request + User Token to **MCP Server**.
5.  Streams response back to Frontend via SSE.

The HTTP transport currently forwards the user's Salla access token to the
private MCP service. This is an internal deployment convention, not a
standards-compliant MCP OAuth boundary. Do not expose the MCP service publicly,
and do not log access tokens. A standards-compliant deployment must give the
MCP server its own audience-bound credential and manage Salla authorization on
the server side.
