"""Salla MCP Server - Core e-commerce tools for AI agents."""
import json
from typing import Any
from mcp.server.fastmcp import FastMCP

from .salla_client import salla_client, SallaAPIError


# Initialize MCP server
mcp = FastMCP("salla-ecommerce")


def format_response(data: Any) -> str:
    """Format response data as JSON string."""
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def format_error(error: Exception) -> str:
    """Format error as readable string."""
    if isinstance(error, SallaAPIError):
        return f"API Error ({error.status_code}): {error.message}"
    return f"Error: {str(error)}"


# =============================================================================
# PRODUCTS TOOLS
# =============================================================================

@mcp.tool()
async def list_products(
    page: int = 1,
    per_page: int = 15,
    keyword: str = "",
    status: str = "",
) -> str:
    """
    List all products in the Salla store with optional filtering.
    
    Args:
        page: Page number for pagination (default: 1)
        per_page: Number of products per page, max 60 (default: 15)
        keyword: Search keyword to filter products by name
        status: Filter by product status (sale, out, hidden, deleted)
    
    Returns:
        JSON string with list of products and pagination info
    """
    try:
        params = {"page": page, "per_page": min(per_page, 60)}
        if keyword:
            params["keyword"] = keyword
        if status:
            params["status"] = status
        
        result = await salla_client.get("/products", params=params)
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def get_product(product_id: int) -> str:
    """
    Get detailed information about a specific product.
    
    Args:
        product_id: The unique ID of the product
    
    Returns:
        JSON string with product details including name, price, quantity, images, etc.
    """
    try:
        result = await salla_client.get(f"/products/{product_id}")
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def create_product(
    name: str,
    price: float,
    product_type: str = "product",
    quantity: int = 0,
    description: str = "",
    cost_price: float = 0,
    sku: str = "",
) -> str:
    """
    Create a new product in the Salla store.
    
    Args:
        name: Product name (required)
        price: Product selling price (required)
        product_type: Type of product - "product", "service", "group_products", "codes", "digital", "food", "booking" (default: "product")
        quantity: Available quantity (default: 0 means unlimited)
        description: Product description
        cost_price: Cost price for profit calculation
        sku: Stock Keeping Unit identifier
    
    Returns:
        JSON string with created product details
    """
    try:
        data = {
            "name": name,
            "price": price,
            "product_type": product_type,
        }
        if quantity:
            data["quantity"] = quantity
        if description:
            data["description"] = description
        if cost_price:
            data["cost_price"] = cost_price
        if sku:
            data["sku"] = sku
        
        result = await salla_client.post("/products", data=data)
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def update_product(
    product_id: int,
    name: str = "",
    price: float = 0,
    quantity: int = -1,
    description: str = "",
    status: str = "",
) -> str:
    """
    Update an existing product's details.
    
    Args:
        product_id: The unique ID of the product to update (required)
        name: New product name
        price: New selling price
        quantity: New available quantity (-1 means don't update)
        description: New product description
        status: New status - "sale", "out", "hidden"
    
    Returns:
        JSON string with updated product details
    """
    try:
        data = {}
        if name:
            data["name"] = name
        if price > 0:
            data["price"] = price
        if quantity >= 0:
            data["quantity"] = quantity
        if description:
            data["description"] = description
        if status:
            data["status"] = status
        
        if not data:
            return "Error: No fields provided to update"
        
        result = await salla_client.put(f"/products/{product_id}", data=data)
        return format_response(result)
    except Exception as e:
        return format_error(e)


# =============================================================================
# ORDERS TOOLS
# =============================================================================

@mcp.tool()
async def list_orders(
    page: int = 1,
    per_page: int = 15,
    status: str = "",
    keyword: str = "",
) -> str:
    """
    List all orders in the Salla store with optional filtering.
    
    Args:
        page: Page number for pagination (default: 1)
        per_page: Number of orders per page, max 60 (default: 15)
        status: Filter by order status (pending, completed, cancelled, refunded, etc.)
        keyword: Search by order ID, customer name, email, or phone
    
    Returns:
        JSON string with list of orders and pagination info
    """
    try:
        params = {"page": page, "per_page": min(per_page, 60)}
        if status:
            params["status"] = status
        if keyword:
            params["keyword"] = keyword
        
        result = await salla_client.get("/orders", params=params)
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def get_order(order_id: int) -> str:
    """
    Get detailed information about a specific order.
    
    Args:
        order_id: The unique ID of the order
    
    Returns:
        JSON string with order details including items, customer, shipping, payment info
    """
    try:
        result = await salla_client.get(f"/orders/{order_id}")
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def create_order(
    customer_id: int,
    products: list[dict],
    shipping_method: int = 0,
    payment_method: int = 0,
    note: str = "",
) -> str:
    """
    Create a new order in the Salla store.
    
    Args:
        customer_id: ID of the customer placing the order (required)
        products: List of products with format [{"product_id": 123, "quantity": 2}, ...] (required)
        shipping_method: Shipping method ID
        payment_method: Payment method ID
        note: Order note/comment
    
    Returns:
        JSON string with created order details
    """
    try:
        data = {
            "customer": customer_id,
            "products": products,
        }
        if shipping_method:
            data["shipping_method"] = shipping_method
        if payment_method:
            data["payment_method"] = payment_method
        if note:
            data["note"] = note
        
        result = await salla_client.post("/orders", data=data)
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def update_order_status(
    order_id: int,
    status_id: int,
    notify_customer: bool = True,
) -> str:
    """
    Update the status of an existing order.
    
    Args:
        order_id: The unique ID of the order to update (required)
        status_id: The new status ID to set (required)
        notify_customer: Whether to notify customer about status change (default: True)
    
    Returns:
        JSON string with updated order details
    """
    try:
        data = {
            "status_id": status_id,
            "notify_customer": notify_customer,
        }
        result = await salla_client.put(f"/orders/{order_id}/status", data=data)
        return format_response(result)
    except Exception as e:
        return format_error(e)


# =============================================================================
# CUSTOMERS TOOLS
# =============================================================================

@mcp.tool()
async def list_customers(
    page: int = 1,
    per_page: int = 15,
    keyword: str = "",
) -> str:
    """
    List all customers in the Salla store with optional filtering.
    
    Args:
        page: Page number for pagination (default: 1)
        per_page: Number of customers per page, max 60 (default: 15)
        keyword: Search by customer name, email, or mobile number
    
    Returns:
        JSON string with list of customers and pagination info
    """
    try:
        params = {"page": page, "per_page": min(per_page, 60)}
        if keyword:
            params["keyword"] = keyword
        
        result = await salla_client.get("/customers", params=params)
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def get_customer(customer_id: int) -> str:
    """
    Get detailed information about a specific customer.
    
    Args:
        customer_id: The unique ID of the customer
    
    Returns:
        JSON string with customer details including name, contact info, addresses, orders
    """
    try:
        result = await salla_client.get(f"/customers/{customer_id}")
        return format_response(result)
    except Exception as e:
        return format_error(e)


@mcp.tool()
async def create_customer(
    first_name: str,
    last_name: str = "",
    mobile: str = "",
    email: str = "",
    country_code: str = "SA",
) -> str:
    """
    Create a new customer in the Salla store.
    
    Args:
        first_name: Customer's first name (required)
        last_name: Customer's last name
        mobile: Mobile phone number (without country code)
        email: Email address
        country_code: Country code for mobile, e.g., "SA" for Saudi Arabia (default: "SA")
    
    Returns:
        JSON string with created customer details
    """
    try:
        data = {
            "first_name": first_name,
        }
        if last_name:
            data["last_name"] = last_name
        if mobile:
            data["mobile"] = mobile
            data["mobile_code"] = country_code
        if email:
            data["email"] = email
        
        result = await salla_client.post("/customers", data=data)
        return format_response(result)
    except Exception as e:
        return format_error(e)


# =============================================================================
# STORE TOOLS
# =============================================================================

@mcp.tool()
async def get_store_info() -> str:
    """
    Get information about the Salla store.
    
    Returns:
        JSON string with store details including name, domain, plan, currency, settings
    """
    try:
        result = await salla_client.get("/store/info")
        return format_response(result)
    except Exception as e:
        return format_error(e)


# =============================================================================
# RUN SERVER
# =============================================================================

if __name__ == "__main__":
    mcp.run()
