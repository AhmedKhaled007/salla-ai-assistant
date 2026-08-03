# Salla MCP Server

A **Model Context Protocol (MCP)** server that exposes Salla e-commerce API capabilities as programmable tools. This service acts as the integration layer, translating tool calls into secure requests to the Salla Admin API.

## 🤖 What is MCP?
The [Model Context Protocol](https://modelcontextprotocol.io) creates a standard way for models to connect to data and tools. This server uses MCP Python SDK v2, negotiates protocol `2026-07-28`, and continues to serve legacy clients.

## 🛠️ Available Tools

The server currently exposes **12 tools** across 4 categories:

### Products
- `list_products`: Search/filter products.
- `get_product`: Get details by ID.
- `create_product`: Add new items.
- `update_product`: Modify inventory/prices.

### Orders
- `list_orders`: View store orders.
- `get_order`: specific order details.
- `create_order`: Programmatically create orders.
- `update_order_status`: Change status (e.g., to "Shipping").

### Customers
- `list_customers`: Find customers.
- `get_customer`: Customer profile & history.
- `create_customer`: Register new customers.

### Store
- `get_store_info`: Basic store metadata.

## ⚙️ Configuration

The server is designed to be **stateless regarding user tokens**. The Salla OAuth Access Token must be passed **per request** for HTTP or through `SALLA_ACCESS_TOKEN` for stdio.

The HTTP bearer-token forwarding is a trusted,network convention and
does not implement the MCP OAuth authorization profile.

### Environment Variables (.env)

```env
# Optional: Override default Salla V2 API URL
SALLA_API_BASE_URL=https://api.salla.dev/admin/v2

# Request Timeouts
API_TIMEOUT=30

# MCP listener
MCP_HOST=0.0.0.0
MCP_PORT=8001
```

## 🚀 Running the Server

### 1. HTTP Transport (Production)
Run as a web service usable by MCP clients.

```bash
# Using uv (Recommended)
uv run python -m mcp_server.main --transport http --host 0.0.0.0 --port 8001
```

### 2. Stdio Transport (Development/CLI)
Run over standard input/output for local testing or direct connection to MCP-compliant IDEs (like Zed or Claude Desktop).

```bash
uv run python -m mcp_server.main --transport stdio
```

## 📦 Dependencies

- **mcp 2.x**: Official MCP client/server SDK with `2026-07-28` support.
- **httpx**: Async HTTP client for calling Salla API.
- **pydantic**: Data validation.
