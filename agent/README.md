# Salla Agent Service

The core "brain" of the Salla AI Assistant. This FastAPI service orchestrates conversations, manages OAuth authentication, and integrates with the MCP (Model Context Protocol) Server to execute tools.

## 🚀 Key Features

*   **FastAPI & Async**: Built for high-concurrency with Python 3.13+ and full async support.
*   **Model Context Protocol (MCP) Client**: Connects to the MCP Server to discover and execute Salla e-commerce tools.
*   **Connection Pooling**: Custom `MCPClientPool` ensures isolated, secure Salla API access for multiple users simultaneously using their unique OAuth tokens.
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
LLM_TEMPERATURE=1
GEMINI_API_KEY=your_gemini_api_key

# MCP Connection (Integration Layer)
MCP_TRANSPORT=http
MCP_SERVER_URL=http://localhost:8001/mcp

# Salla OAuth Credentials
SALLA_CLIENT_ID=your_client_id
SALLA_CLIENT_SECRET=your_client_secret
SALLA_REDIRECT_URI=http://localhost:3000/callback

# Security
SECRET_KEY=your_secret_key
API_HOST=0.0.0.0
API_PORT=8000
```

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

Run the test suite with `pytest`:

```bash
uv run pytest
```

## 🏗️ Architecture

The Agent Service sits in the middle of the stack:

1.  Receives user queries + OAuth token from **Frontend**.
2.  Retrieves conversation history from **PostgreSQL**.
3.  Sends context to **LLM**.
4.  If LLM requests a tool (e.g., `list_products`), Agent forwards request + User Token to **MCP Server**.
5.  Streams response back to Frontend via SSE.
