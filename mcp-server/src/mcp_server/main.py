"""Salla MCP Server - Core e-commerce tools for AI agents."""
import json
import logging
from typing import Any
from mcp.server.fastmcp import FastMCP, Context

from .salla_client import SallaClient, SallaAPIError


# Initialize MCP server
# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("salla-ecommerce", host="0.0.0.0")


def format_response(data: Any) -> str:
    """Format response data as JSON string."""
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def format_error(error: Exception) -> str:
    """Format error as readable string."""
    if isinstance(error, SallaAPIError):
        return f"API Error ({error.status_code}): {error.message}"
    return f"Error: {str(error)}"


def get_salla_client(ctx: Context) -> SallaClient:
    """Extract access token from request context and create a per-request SallaClient.

    For HTTP transport, the token is passed in the Authorization header.
    This function extracts it and creates a new client instance for this request,
    ensuring no token leakage between concurrent requests.

    Args:
        ctx: MCP Context object containing request information

    Returns:
        SallaClient instance with the request's access token

    Raises:
        ValueError: If no authorization token is found in the request
    """
    try:
        request = ctx.request_context.request
        if request:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:]  # Remove "Bearer " prefix
                return SallaClient(access_token=token)
    except Exception as e:
        # If not in HTTP context (stdio transport), fall through to error
        logger.error(f"Error extracting token from context: {e}")

    raise ValueError("No authorization token found in request. Please authenticate first.")


# =============================================================================
# PRODUCTS TOOLS
# =============================================================================

@mcp.tool()
async def list_products(
    ctx: Context,
    keyword: str = "",
    status: str = "",
    category: str = "",
    page: int = 1,
    per_page: int = 15,
) -> str:
    """
    List all products in the Salla store with optional filtering.

    Args:
        keyword: Search keyword to filter products by name or SKU
        status: Filter by product status (hidden, sale, out, deleted)
        category: Filter by category ID
        page: Page number for pagination (default: 1)
        per_page: Number of products per page (default: 15)

    Returns:
        JSON string with list of products and pagination info
    """
    try:
        client = get_salla_client(ctx)
        params = {}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        if keyword:
            params["keyword"] = keyword
        if status:
            params["status"] = status
        if category:
            params["category"] = category

        result = await client.get("/products", params=params)
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def get_product(ctx: Context, product_id: int) -> str:
    """
    Get detailed information about a specific product.

    Args:
        product_id: The unique ID of the product

    Returns:
        JSON string with product details including name, price, quantity, images, etc.
    """
    try:
        client = get_salla_client(ctx)
        result = await client.get(f"/products/{product_id}")
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def create_product(
    ctx: Context,
    name: str,
    price: float,
    product_type: str,
    quantity: int = None,
    description: str = "",
    sku: str = "",
    status: str = "",
    sale_price: float = None,
    cost_price: float = None,
    weight: float = None,
    weight_type: str = "kg",
    require_shipping: bool = True,
    images: list[dict] = None,
    options: list[dict] = None,
    metadata_title: str = "",
    metadata_description: str = "",
) -> str:
    """
    Create a new product in the Salla store.

    Args:
        name: Product Name (required)
        price: Product price (required)
        product_type: Product type (product, service, group_products, codes, digital, food, booking, donating) (required)
        quantity: Quantity of the product
        description: Product description
        sku: Stock Keeping Unit
        status: product status (sale, out, hidden, deleted)
        sale_price: The sale price of the product
        cost_price: Product cost price
        weight: The weight of the product
        weight_type: Weight unit (kg, g, lb, oz)
        require_shipping: Does the product require shipping
        images: List of images [{"original": "url", "thumbnail": "url", ...}]
        options: List of product options
        metadata_title: SEO Title
        metadata_description: SEO Description

    Returns:
        JSON string with created product details
    """
    try:
        client = get_salla_client(ctx)
        data = {
            "name": name,
            "price": price,
            "product_type": product_type,
        }
        if quantity is not None:
            data["quantity"] = quantity
        if description:
            data["description"] = description
        if sku:
            data["sku"] = sku
        if status:
            data["status"] = status
        if sale_price is not None:
            data["sale_price"] = sale_price
        if cost_price is not None:
            data["cost_price"] = cost_price
        if weight is not None:
            data["weight"] = weight
        if weight_type:
            data["weight_type"] = weight_type
        if require_shipping is not None:
            data["require_shipping"] = require_shipping
        if images:
            data["images"] = images
        if options:
            data["options"] = options
        if metadata_title:
            data["metadata_title"] = metadata_title
        if metadata_description:
            data["metadata_description"] = metadata_description

        result = await client.post("/products", data=json.dumps(data))
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def update_product(
    ctx: Context,
    product_id: int,
    name: str = "",
    price: float = None,
    quantity: int = None,
    description: str = "",
    sku: str = "",
    status: str = "",
    sale_price: float = None,
    require_shipping: bool = None,
) -> str:
    """
    Update an existing product's details.

    Args:
        product_id: The unique ID of the product to update (required)
        name: New product name
        price: New selling price
        quantity: New available quantity
        description: New product description
        sku: New SKU
        status: New status (sale, out, hidden, deleted)
        sale_price: New sale price
        require_shipping: Update shipping requirement

    Returns:
        JSON string with updated product details
    """
    try:
        client = get_salla_client(ctx)
        data = {}
        if name:
            data["name"] = name
        if price is not None:
            data["price"] = price
        if quantity is not None:
            data["quantity"] = quantity
        if description:
            data["description"] = description
        if sku:
            data["sku"] = sku
        if status:
            data["status"] = status
        if sale_price is not None:
            data["sale_price"] = sale_price
        if require_shipping is not None:
            data["require_shipping"] = require_shipping

        if not data:
            return "Error: No fields provided to update"

        result = await client.put(f"/products/{product_id}", data=data)
        return format_response(result)
    except Exception as e:
        return format_error(e)


# =============================================================================
# ORDERS TOOLS
# =============================================================================

@mcp.tool()
async def list_orders(
    ctx: Context,
    page: int = 1,
    per_page: int = 15,
    keyword: str = "",
    status: str = "",
    from_date: str = "",
    to_date: str = "",
) -> str:
    """
    List all orders in the Salla store with optional filtering.

    Args:
        page: Page number (default: 1)
        per_page: Number of orders per page (default: 15)
        keyword: Search keyword (customer name, mobile, shipping number, etc.)
        status: Filter by status slug or ID (can be comma-separated)
        from_date: Filter orders created after date (YYYY-MM-DD)
        to_date: Filter orders created before date (YYYY-MM-DD)

    Returns:
        JSON string with list of orders and pagination info
    """
    try:
        client = get_salla_client(ctx)
        params = {}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        if keyword:
            params["keyword"] = keyword
        if status:
            params["status"] = status.split(",") if "," in status else status
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date

        result = await client.get("/orders", params=params)
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def get_order(
    ctx: Context,
    order_id: int,
    format: str = "",
) -> str:
    """
    Get detailed information about a specific order.

    Args:
        order_id: The unique ID of the order
        format: Optional format. Set to 'light' to reduce response size.

    Returns:
        JSON string with order details
    """
    try:
        client = get_salla_client(ctx)
        params = {}
        if format:
            params["format"] = format
        result = await client.get(f"/orders/{order_id}", params=params)
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def create_order(
    ctx: Context,
    customer_id: int,
    products: list[dict],
    delivery_method: str = "shipping",
    payment_method: str = "bank",
    bank_id: int = None,
    receipt_image: str = "",
) -> str:
    """
    Create a new order in the Salla store.

    Args:
        customer_id: ID of the customer placing the order (required)
        products: List of products (required). Each item must follow format: {"identifier": "id/sku", "identifier_type": "id/sku", "quantity": 1}
        delivery_method: Method of delivery (shipping, pickup)
        payment_method: Payment method (bank, credit_card, mada, cod)
        bank_id: Required if payment_method is bank
        receipt_image: Required if payment_method is bank

    Returns:
        JSON string with created order details
    """
    try:
        client = get_salla_client(ctx)
        # Construct payload according to specs
        data = {
            "customer": {"id": customer_id},
            "products": products,
            "delivery_method": delivery_method,
            "payment": {
                "method": payment_method,
                "status": "paid" if payment_method != "cod" else "pending_payment"  # Assumption/simplification
            }
        }

        if payment_method == "bank":
            if bank_id:
                data["payment"]["store_bank_id"] = bank_id
            if receipt_image:
                data["payment"]["receipt_image_path"] = receipt_image

        result = await client.post("/orders", data=data)
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def update_order_status(
    ctx: Context,
    order_id: int,
    status_id: int = None,
    slug: str = "",
    note: str = "",
    restore_items: bool = False,
) -> str:
    """
    Update the status of an existing order.

    Args:
        order_id: The unique ID of the order to update (required)
        status_id: The new status ID to set (optional if slug is provided)
        slug: The new status slug (e.g. 'completed', 'under_review') (optional if status_id provided)
        note: Note about status change
        restore_items: Whether to restore items to stock (if applicable)

    Returns:
        JSON string with updated order details
    """
    try:
        client = get_salla_client(ctx)
        data = {}
        if status_id:
            data["status_id"] = status_id
        if slug:
            data["slug"] = slug
        if note:
            data["note"] = note
        if restore_items:
            data["restore_items"] = restore_items

        if not status_id and not slug:
            return "Error: Provide either status_id or slug"

        result = await client.post(f"/orders/{order_id}/status", data=data)  # POST not PUT according to spec
        return format_response(result)
    except Exception as e:
        return format_error(e)


# =============================================================================
# CUSTOMERS TOOLS
# =============================================================================

@mcp.tool()
async def list_customers(
    ctx: Context,
    page: int = 1,
    per_page: int = 15,
    keyword: str = "",
    date_from: str = "",
    date_to: str = "",
) -> str:
    """
    List all customers in the Salla store with optional filtering.

    Args:
        page: Page number for pagination (default: 1)
        per_page: Number of customers per page (default: 15)
        keyword: Search by customer name, email, or mobile number
        date_from: Filter customers created after (YYYY-MM-DD)
        date_to: Filter customers created before (YYYY-MM-DD)

    Returns:
        JSON string with list of customers and pagination info
    """
    try:
        client = get_salla_client(ctx)
        params = {}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        if keyword:
            params["keyword"] = keyword
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to

        result = await client.get("/customers", params=params)
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def get_customer(ctx: Context, customer_id: int) -> str:
    """
    Get detailed information about a specific customer.

    Args:
        customer_id: The unique ID of the customer

    Returns:
        JSON string with customer details including name, contact info, addresses, orders
    """
    try:
        client = get_salla_client(ctx)
        result = await client.get(f"/customers/{customer_id}")
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def create_customer(
    ctx: Context,
    first_name: str,
    last_name: str,
    mobile: str,
    mobile_code_country: str,
    email: str = "",
    gender: str = "",
    birthday: str = "",
    groups: list[int] = None,
) -> str:
    """
    Create a new customer in the Salla store.

    Args:
        first_name: Customer given name (required)
        last_name: Customer family name (required)
        mobile: The numerical contact information belonging to a customer, without country code (required)
        mobile_code_country: The numeric prefix indicating a customer's country for mobile communication (e.g. "+966") (required)
        email: Email address of the customer
        gender: The categorization of an individual as male, female (male, female)
        birthday: The customer date of birth (YYYY-MM-DD)
        groups: List of unique group identifiers to which a customer belongs

    Returns:
        JSON string with created customer details
    """
    try:
        client = get_salla_client(ctx)

        data = {
            "first_name": first_name,
            "last_name": last_name,
            "mobile": mobile,
            "mobile_code_country": mobile_code_country,
        }

        if email:
            data["email"] = email
        if gender:
            data["gender"] = gender
        if birthday:
            data["birthday"] = birthday
        if groups:
            data["groups"] = groups

        result = await client.post("/customers", data=data)
        return format_response(result)
    except Exception as e:
        return format_error(e)


# =============================================================================
# STORE TOOLS
# =============================================================================

@mcp.tool()
async def get_store_info(ctx: Context) -> str:
    """
    Get information about the Salla store.

    Returns:
        JSON string with store details including name, domain, plan, currency, settings
    """
    try:
        client = get_salla_client(ctx)
        result = await client.get("/store/info")
        return format_response(result)
    except Exception as e:
        return format_error(e)


# =============================================================================
# RUN SERVER
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Salla MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="http",
        help="Transport to use (stdio for dev, http for production)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for HTTP transport (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for HTTP transport (default: 8001)"
    )
    args = parser.parse_args()

    if args.transport == "http":
        # Run with Streamable HTTP transport using uvicorn
        import uvicorn

        # Get the ASGI app from FastMCP
        base_app = mcp.streamable_http_app()

        uvicorn.run(base_app, host=args.host, port=args.port)
    else:
        # Run with stdio for local development
        mcp.run()
