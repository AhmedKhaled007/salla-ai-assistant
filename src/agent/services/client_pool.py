"""MCPClient pool for per-user client instances.

This module provides a pool of MCPClient instances, one per authenticated user.
This solves the token isolation problem - each user's requests use their own
client instance with their own Salla access token.
"""

import asyncio
from typing import Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from ..core import settings, logger
from .mcp_client import MCPClient


@dataclass
class PooledClient:
    """Wrapper for a pooled MCPClient with metadata."""
    client: MCPClient
    access_token: Optional[str] = None
    last_used: datetime = field(default_factory=datetime.now)
    in_use: bool = False
    
    # Store the auth session ID associated with this client
    auth_session_id: Optional[str] = None


class MCPClientPool:
    """Pool of MCPClient instances, one per authenticated user.
    
    This class manages the lifecycle of MCPClient instances:
    - Creates new clients for new users
    - Reuses existing clients for returning users
    - Cleans up idle clients to free resources
    - Handles token updates per client
    """
    
    def __init__(
        self, 
        transport: str = "stdio",
        server_url: Optional[str] = None,
        server_script_path: str = "",
        max_idle_seconds: int = 300,  # 5 minutes idle timeout
        cleanup_interval_seconds: int = 60,
    ):
        """Initialize the client pool.
        
        Args:
            transport: Transport type - 'stdio' or 'http'
            server_url: URL for HTTP transport
            server_script_path: Path for stdio transport
            max_idle_seconds: Seconds before an idle client is removed
            cleanup_interval_seconds: Seconds between cleanup runs
        """
        self.transport = transport
        self.server_url = server_url
        self.server_script_path = server_script_path
        self.max_idle_seconds = max_idle_seconds
        
        # Pool storage: {auth_session_id: PooledClient}
        self._clients: dict[str, PooledClient] = {}
        
        # Default client for unauthenticated users (if allowed)
        self._default_client: Optional[MCPClient] = None
        
        # Locks and synchronization
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = cleanup_interval_seconds
        self._running = False

    async def initialize(self) -> bool:
        """Initialize the pool and start background cleanup task.
        
        Returns:
            True if initialization successful
        """
        self._running = True
        
        # Initialize default client
        logger.info("Initializing default MCP client...")
        try:
            self._default_client = MCPClient(
                transport=self.transport, 
                server_url=self.server_url
            )
            await self._default_client.connect_to_server(self.server_script_path)
        except Exception as e:
            logger.error(f"Failed to initialize default client: {e}")
            # We continue even if default client fails, hoping per-user clients work
        
        # Start cleanup task
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
        # Case 1: Unauthenticated request
        if not auth_session_id:
            if not self._default_client:
                # Try to re-init default client
                self._default_client = MCPClient(self.transport, self.server_url)
                await self._default_client.connect_to_server(self.server_script_path)
            
            return self._default_client

        # Case 2: Authenticated request
        async with self._lock:
            # Check if client exists
            if auth_session_id in self._clients:
                pooled = self._clients[auth_session_id]
                pooled.last_used = datetime.now()
                pooled.in_use = True
                
                # Check if token changed (e.g., refreshed)
                if access_token and access_token != pooled.access_token:
                    logger.info(f"Updating token for client {auth_session_id}")
                    await pooled.client.set_access_token(access_token)
                    pooled.access_token = access_token
                
                return pooled.client
                
            # Create new client for this user
            logger.info(f"Creating new MCP client for user {auth_session_id}")
            new_client = MCPClient(self.transport, self.server_url)
            
            # Connect with user's token
            success = await new_client.connect_to_server(
                self.server_script_path, access_token
            )
            
            if not success:
                logger.error(f"Failed to create client for {auth_session_id}")
                # Fallback to default if user client creation fails? 
                # Better to raise error so they know something failed.
                raise RuntimeError(f"Could not connect MCP client for user {auth_session_id}")
            
            # Add to pool
            self._clients[auth_session_id] = PooledClient(
                client=new_client,
                access_token=access_token,
                auth_session_id=auth_session_id,
                in_use=True
            )
            
            return new_client

    async def release_client(self, auth_session_id: Optional[str]) -> None:
        """Mark a client as no longer in use.
        
        Args:
            auth_session_id: User's auth session ID
        """
        if not auth_session_id:
            return
            
        async with self._lock:
            if auth_session_id in self._clients:
                self._clients[auth_session_id].in_use = False
                self._clients[auth_session_id].last_used = datetime.now()

    async def remove_client(self, auth_session_id: str) -> bool:
        """Remove and cleanup a specific client.
        
        Args:
            auth_session_id: User's auth session ID
            
        Returns:
            True if client existed and was removed
        """
        async with self._lock:
            if auth_session_id in self._clients:
                pooled = self._clients.pop(auth_session_id)
                await pooled.client.cleanup()
                logger.debug(f"Removed client for {auth_session_id}")
                return True
            return False

    async def cleanup_idle(self) -> int:
        """Remove clients that have been idle too long.
        
        Returns:
            Number of clients cleaned up
        """
        now = datetime.now()
        to_remove = []
        
        async with self._lock:
            for auth_id, pooled in self._clients.items():
                # Don't remove in-use clients
                if pooled.in_use:
                    continue
                    
                # Check idle time
                idle_duration = (now - pooled.last_used).total_seconds()
                if idle_duration > self.max_idle_seconds:
                    to_remove.append(auth_id)
            
            # Remove marked
            count = 0
            for auth_id in to_remove:
                pooled = self._clients.pop(auth_id)
                await pooled.client.cleanup()
                count += 1
                
        if count > 0:
            logger.info(f"Cleaned up {count} idle MCP clients")
            
        return count

    async def _cleanup_loop(self):
        """Background task to periodically cleanup idle clients."""
        while self._running:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self.cleanup_idle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def cleanup_all(self):
        """Cleanup all clients and stop background tasks."""
        self._running = False
        
        # Stop cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cleanup default client
        if self._default_client:
            await self._default_client.cleanup()
            
        # Cleanup all pooled clients
        async with self._lock:
            for pooled in self._clients.values():
                await pooled.client.cleanup()
            self._clients.clear()
            
        logger.info("MCPClientPool shutdown complete")

    def pool_size(self) -> int:
        """Get the current number of pooled clients."""
        return len(self._clients)

    def active_clients(self) -> int:
        """Get the number of clients currently in use."""
        return sum(1 for c in self._clients.values() if c.in_use)

    async def ping(self) -> bool:
        """Check if the default client is responsive."""
        if self._default_client:
            return await self._default_client.ping()
        return False
        
    def is_connected(self) -> bool:
        """Check if the pool is initialized and connected."""
        if self._default_client:
            return self._default_client.is_connected()
        return self._running
