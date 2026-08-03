"""Order tools for Salla MCP Server."""
from mcp.server.mcpserver import Context

from ..models import (
    ListOrdersInput,
    GetOrderInput,
    CreateOrderInput,
    UpdateOrderStatusInput,
)
from ..utils import get_salla_client, format_error

__all__ = [
    "salla_list_orders",
    "salla_get_order",
    "salla_create_order",
    "salla_update_order_status",
]


async def salla_list_orders(params: ListOrdersInput, ctx: Context) -> dict:
    """
    List all orders in the Salla store with optional filtering.

    Args:
        params: Input parameters containing:
            - page (int): Page number (default: 1)
            - per_page (int): Number of orders per page (default: 15)
            - keyword (str): Search keyword (customer name, mobile, shipping number, etc.)
            - status (str): Filter by status slug or ID (can be comma-separated)
            - from_date (str): Filter orders created after date (YYYY-MM-DD)
            - to_date (str): Filter orders created before date (YYYY-MM-DD)

    Returns:
        dict: API response with list of orders and pagination info
    """
    try:
        client = get_salla_client(ctx)
        request_params = {}
        if params.page:
            request_params["page"] = params.page
        if params.per_page:
            request_params["per_page"] = params.per_page
        if params.keyword:
            request_params["keyword"] = params.keyword
        if params.status:
            request_params["status"] = params.status.split(",") if "," in params.status else params.status
        if params.from_date:
            request_params["from_date"] = params.from_date
        if params.to_date:
            request_params["to_date"] = params.to_date

        result = await client.get("/orders", params=request_params)
        return result
    except Exception as e:
        return format_error(e)


async def salla_get_order(params: GetOrderInput, ctx: Context) -> dict:
    """
    Get detailed information about a specific order.

    Args:
        params: Input parameters containing:
            - order_id (int): The unique ID of the order
            - format (str): Optional format. Set to 'light' to reduce response size.

    Returns:
        dict: Order details including items, customer, status, shipping info
    """
    try:
        client = get_salla_client(ctx)
        request_params = {}
        if params.format:
            request_params["format"] = params.format
        result = await client.get(f"/orders/{params.order_id}", params=request_params)
        return result
    except Exception as e:
        return format_error(e)


async def salla_create_order(params: CreateOrderInput, ctx: Context) -> dict:
    """
    Create a new order in the Salla store.

    Args:
        params: Input parameters containing:
            - customer_id (int): ID of the customer placing the order (required)
            - products (list): List of products (required). Each item: {identifier, identifier_type, quantity}
            - delivery_method (str): Method of delivery (shipping, pickup)
            - payment_method (str): Payment method (bank, credit_card, mada, cod)
            - bank_id (int): Required if payment_method is bank
            - receipt_image (str): Required if payment_method is bank

    Returns:
        dict: Created order details
    """
    try:
        client = get_salla_client(ctx)
        # Construct payload according to specs
        products_data = [
            {
                "identifier": p.identifier,
                "identifier_type": p.identifier_type,
                "quantity": p.quantity,
            }
            for p in params.products
        ]

        data = {
            "customer": {"id": params.customer_id},
            "products": products_data,
            "delivery_method": params.delivery_method.value,
            "payment": {
                "method": params.payment_method.value,
                "status": "paid" if params.payment_method.value != "cod" else "pending_payment"
            }
        }

        if params.payment_method.value == "bank":
            if params.bank_id:
                data["payment"]["store_bank_id"] = params.bank_id
            if params.receipt_image:
                data["payment"]["receipt_image_path"] = params.receipt_image

        result = await client.post("/orders", data=data)
        return result
    except Exception as e:
        return format_error(e)


async def salla_update_order_status(params: UpdateOrderStatusInput, ctx: Context) -> dict:
    """
    Update the status of an existing order.

    Args:
        params: Input parameters containing:
            - order_id (int): The unique ID of the order to update (required)
            - status_id (int): The new status ID to set (optional if slug is provided)
            - slug (str): The new status slug (e.g. 'completed', 'under_review')
            - note (str): Note about status change
            - restore_items (bool): Whether to restore items to stock

    Returns:
        dict: Updated order details
    """
    try:
        client = get_salla_client(ctx)
        data = params.model_dump(exclude_unset=True, exclude_none=True, exclude={"order_id"})
        # Remove empty strings and False booleans for restore_items
        data = {k: v for k, v in data.items() if v not in ("", False)}

        if not params.status_id and not params.slug:
            return {"error": "Provide either status_id or slug"}

        # POST not PUT according to Salla API spec
        result = await client.post(f"/orders/{params.order_id}/status", data=data)
        return result
    except Exception as e:
        return format_error(e)
