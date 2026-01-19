"""MCPClient pool for per-user client instances.

This module provides a pool of MCPClient instances, one per authenticated user.
This solves the token isolation problem - each user's requests use their own
client instance with their own Salla access token.
"""

import asyncio
from typing import Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from .mcp_client import MCPClient
from .utils import settings, logger


@dataclass
class PooledClient:
    """Wrapper for a pooled MCPClient with metadata."""
    client: MCPClient
    access_token: str
    last_used: datetime = field(default_factory=datetime.now)
    in_use: bool = False


class MCPClientPool:
    """Pool of MCPClient instances, one per authenticated user.
    
    This class manages the lifecycle of MCPClient instances:
    - Creates new clients for new users
    - Reuses existing clients for returning users
    - Updates tokens when they change
    - Cleans up idle clients to prevent memory leaks
    
    Thread-safe via asyncio.Lock.
    
    Example:
        pool = MCPClientPool(transport="http", server_url="http://localhost:8001/mcp")
        await pool.initialize()
        
        # Get client for a user
        client = await pool.get_client("user_session_123", "salla_access_token")
        try:
            await client.process_query("List my products")
        finally:
            await pool.release_client("user_session_123")
        
        # Cleanup on shutdown
        await pool.cleanup_all()
    """

    def __init__(
        self,
        transport: str = "stdio",
        server_url: Optional[str] = None,
        server_script_path: str = "",
        max_idle_seconds: int = 300,
        cleanup_interval_seconds: int = 60,
    ):
        """Initialize the client pool.
        
        Args:
            transport: Transport type - 'stdio' or 'http'
            server_url: URL for HTTP transport
            server_script_path: Path for stdio transport
            max_idle_seconds: Max time a client can be idle before cleanup
            cleanup_interval_seconds: How often to run cleanup task
        """
        self._transport = transport
        self._server_url = server_url
        self._server_script_path = server_script_path
        self._max_idle_seconds = max_idle_seconds
        self._cleanup_interval = cleanup_interval_seconds
        
        self._pool: dict[str, PooledClient] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._default_client: Optional[MCPClient] = None  # For unauthenticated requests

    async def initialize(self) -> bool:
        """Initialize the pool and start background cleanup task.
        
        Returns:
            True if initialization successful
        """
        # Create a default client for unauthenticated requests
        self._default_client = MCPClient(
            transport=self._transport,
            server_url=self._server_url,
        )
        
        connected = await self._default_client.connect_to_server(
            self._server_script_path
        )
        
        if not connected:
            logger.error("Failed to connect default client to MCP server")
            return False
        
        # Start background cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("MCPClientPool initialized")
        return True

    async def get_client(
        self, auth_session_id: Optional[str], access_token: Optional[str]
    ) -> MCPClient:
        """Get or create a client for the user.
        
        Args:
            auth_session_id: User's auth session ID (None for unauthenticated)
            access_token: User's Salla access token (None for unauthenticated)
            
        Returns:
            MCPClient instance for this user
        """
        # Unauthenticated requests use the default client
        if not auth_session_id or not access_token:
            if self._default_client is None:
                raise RuntimeError("Pool not initialized")
            return self._default_client
        
        async with self._lock:
            # Check if client exists for this user
            if auth_session_id in self._pool:
                pooled = self._pool[auth_session_id]
                
                # Update token if changed
                if pooled.access_token != access_token:
                    logger.info(f"Token changed for session {auth_session_id[:8]}..., updating")
                    await pooled.client.set_access_token(access_token)
                    pooled.access_token = access_token
                
                pooled.last_used = datetime.now()
                pooled.in_use = True
                return pooled.client
            
            # Create new client for this user
            logger.info(f"Creating new client for session {auth_session_id[:8]}...")
            
            client = MCPClient(
                transport=self._transport,
                server_url=self._server_url,
            )
            
            connected = await client.connect_to_server(
                self._server_script_path,
                access_token=access_token,
            )
            
            if not connected:
                raise RuntimeError(f"Failed to connect client for session {auth_session_id}")
            
            self._pool[auth_session_id] = PooledClient(
                client=client,
                access_token=access_token,
                in_use=True,
            )
            
            return client

    async def release_client(self, auth_session_id: Optional[str]) -> None:
        """Mark a client as no longer in use.
        
        Args:
            auth_session_id: User's auth session ID
        """
        if not auth_session_id:
            return  # Default client is never released
        
        async with self._lock:
            if auth_session_id in self._pool:
                self._pool[auth_session_id].in_use = False
                self._pool[auth_session_id].last_used = datetime.now()

    async def remove_client(self, auth_session_id: str) -> bool:
        """Remove and cleanup a specific client.
        
        Args:
            auth_session_id: User's auth session ID
            
        Returns:
            True if client existed and was removed
        """
        async with self._lock:
            if auth_session_id in self._pool:
                pooled = self._pool.pop(auth_session_id)
                try:
                    await pooled.client.cleanup()
                except Exception as e:
                    logger.warning(f"Error cleaning up client: {e}")
                logger.info(f"Removed client for session {auth_session_id[:8]}...")
                return True
            return False

    async def cleanup_idle(self) -> int:
        """Remove clients that have been idle too long.
        
        Returns:
            Number of clients cleaned up
        """
        async with self._lock:
            now = datetime.now()
            max_idle = timedelta(seconds=self._max_idle_seconds)
            
            to_remove = []
            for session_id, pooled in self._pool.items():
                if not pooled.in_use and (now - pooled.last_used) > max_idle:
                    to_remove.append(session_id)
            
            for session_id in to_remove:
                pooled = self._pool.pop(session_id)
                try:
                    await pooled.client.cleanup()
                except Exception as e:
                    logger.warning(f"Error cleaning up idle client: {e}")
                logger.info(f"Cleaned up idle client for session {session_id[:8]}...")
            
            return len(to_remove)

    async def _cleanup_loop(self) -> None:
        """Background task to periodically cleanup idle clients."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                cleaned = await self.cleanup_idle()
                if cleaned > 0:
                    logger.info(f"Cleaned up {cleaned} idle clients")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def cleanup_all(self) -> None:
        """Cleanup all clients and stop background tasks."""
        # Stop cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cleanup all pooled clients
        async with self._lock:
            for session_id, pooled in self._pool.items():
                try:
                    await pooled.client.cleanup()
                except Exception as e:
                    logger.warning(f"Error cleaning up client {session_id[:8]}: {e}")
            self._pool.clear()
        
        # Cleanup default client
        if self._default_client:
            try:
                await self._default_client.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up default client: {e}")
            self._default_client = None
        
        logger.info("MCPClientPool cleanup complete")

    @property
    def pool_size(self) -> int:
        """Get the current number of pooled clients."""
        return len(self._pool)

    @property
    def active_clients(self) -> int:
        """Get the number of clients currently in use."""
        return sum(1 for p in self._pool.values() if p.in_use)

    async def ping(self) -> bool:
        """Check if the default client is responsive."""
        if self._default_client:
            return await self._default_client.ping()
        return False

    @property
    def is_connected(self) -> bool:
        """Check if the pool is initialized and connected."""
        return self._default_client is not None and self._default_client.is_connected
