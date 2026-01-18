from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any
from contextlib import asynccontextmanager
import json

from .mcp_client import MCPClient
from .utils import settings, logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager. Connects to MCP server on startup."""
    client = MCPClient()
    try:
        connected = await client.connect_to_server(settings.server_script_path)
        if not connected:
            raise RuntimeError("Failed to connect to MCP server")
        app.state.client = client
        yield
    except Exception as e:
        logger.error(f"Error during lifespan: {e}")
        raise RuntimeError(f"Startup failed: {e}") from e
    finally:
        # shutdown
        await client.cleanup()


app = FastAPI(title="MCP Client API", lifespan=lifespan)


# Add CORS middleware with configurable origins
# Set ALLOWED_ORIGINS env var for production (comma-separated)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


class QueryRequest(BaseModel):
    query: str
    session_id: str | None = None  # Optional: continue existing session


class Message(BaseModel):
    role: str
    content: Any


class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any]


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer probes.
    
    Returns MCP connection status, LLM availability, and service info.
    """
    mcp_connected = app.state.client.session is not None
    
    return {
        "status": "healthy" if mcp_connected else "degraded",
        "mcp_connected": mcp_connected,
        "llm_model": settings.llm_model,
        "active_sessions": len(app.state.client.list_sessions()),
    }


@app.post("/query")
async def process_query(request: QueryRequest):
    """Process a query and return the response.
    
    If session_id is provided, continues the existing conversation.
    Otherwise, starts a new session.
    """
    try:
        session_id, messages = await app.state.client.process_query(
            request.query, request.session_id
        )
        return {"session_id": session_id, "messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/stream")
async def process_query_stream(request: QueryRequest):
    """Process a query with Server-Sent Events streaming.
    
    Returns events as they happen:
    - session: Initial session ID
    - tool_call: When a tool is being called
    - tool_result: Result from a tool call
    - response: Final assistant response
    - error: If an error occurs
    - done: When processing is complete
    """
    async def event_generator():
        async for event in app.state.client.process_query_stream(
            request.query, request.session_id
        ):
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/tools")
async def get_tools():
    """Get the list of available tools"""
    try:
        tools = await app.state.client.get_mcp_tools()
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                }
                for tool in tools
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Session Management Endpoints

@app.post("/sessions")
async def create_session():
    """Create a new conversation session."""
    session_id = app.state.client.create_session()
    return {"session_id": session_id}


@app.get("/sessions")
async def list_sessions():
    """List all active session IDs."""
    sessions = app.state.client.list_sessions()
    return {"sessions": sessions}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get messages for a specific session."""
    messages = app.state.client.get_session(session_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "messages": messages}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a conversation session."""
    deleted = app.state.client.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted"}


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {settings.api_host}:{settings.api_port}")
    uvicorn.run(
        "src.agent.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )