"""Salla MCP Server - Core e-commerce tools."""
import logging
from contextlib import asynccontextmanager
import uvicorn

from mcp.server.fastmcp import FastMCP

from .config import settings
from .salla_client import close_shared_client
from .tools.products import salla_list_products,salla_get_product,salla_create_product,salla_update_product
from .tools.orders import salla_list_orders,salla_get_order,salla_create_order,salla_update_order_status
from .tools.customers import salla_list_customers,salla_get_customer,salla_create_customer
from .tools.store import salla_get_store_info

# Initialize logging
logging.basicConfig(level=settings.logger_level)
logger = logging.getLogger(__name__)


# LIFESPAN MANAGEMENT

@asynccontextmanager
async def app_lifespan():
    """Manage server lifecycle - startup and shutdown."""
    # Startup
    logger.info("Salla MCP Server starting up...")
    yield {}
    # Shutdown
    logger.info("Salla MCP Server shutting down...")
    await close_shared_client()


# Initialize MCP server
mcp = FastMCP(
    "salla_mcp",
    host="0.0.0.0",
    stateless_http=True,
    json_response=True,
    lifespan=app_lifespan,
)


# PRODUCTS TOOLS

mcp.tool(
    name="salla_list_products",
    annotations={
        "title": "List Products",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)(salla_list_products)

mcp.tool(
    name="salla_get_product",
    annotations={
        "title": "Get Product Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)(salla_get_product)

mcp.tool(
    name="salla_create_product",
    annotations={
        "title": "Create Product",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)(salla_create_product)

mcp.tool(
    name="salla_update_product",
    annotations={
        "title": "Update Product",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)(salla_update_product)


# ORDERS TOOLS

mcp.tool(
    name="salla_list_orders",
    annotations={
        "title": "List Orders",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)(salla_list_orders)

mcp.tool(
    name="salla_get_order",
    annotations={
        "title": "Get Order Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)(salla_get_order)

mcp.tool(
    name="salla_create_order",
    annotations={
        "title": "Create Order",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)(salla_create_order)

mcp.tool(
    name="salla_update_order_status",
    annotations={
        "title": "Update Order Status",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)(salla_update_order_status)


# CUSTOMERS TOOLS

mcp.tool(
    name="salla_list_customers",
    annotations={
        "title": "List Customers",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)(salla_list_customers)

mcp.tool(
    name="salla_get_customer",
    annotations={
        "title": "Get Customer Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)(salla_get_customer)

mcp.tool(
    name="salla_create_customer",
    annotations={
        "title": "Create Customer",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)(salla_create_customer)


# STORE TOOLS

mcp.tool(
    name="salla_get_store_info",
    annotations={
        "title": "Get Store Information",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)(salla_get_store_info)


# RUN SERVER

if __name__ == "__main__":

    # Get the ASGI app from FastMCP
    base_app = mcp.streamable_http_app()

    uvicorn.run(base_app, host="0.0.0.0", port=8001)
