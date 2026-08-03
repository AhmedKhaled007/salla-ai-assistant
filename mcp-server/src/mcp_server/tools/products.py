"""Product tools for Salla MCP Server."""
from mcp.server.fastmcp import Context

from ..models import (
    ListProductsInput,
    GetProductInput,
    CreateProductInput,
    UpdateProductInput,
)
from ..utils import get_salla_client, format_error

__all__ = [
    "salla_list_products",
    "salla_get_product",
    "salla_create_product",
    "salla_update_product",
]


async def salla_list_products(params: ListProductsInput, ctx: Context) -> dict:
    """
    List all products in the Salla store with optional filtering.

    Args:
        params: Input parameters containing:
            - keyword (str): Search keyword to filter products by name or SKU
            - status (str): Filter by product status (hidden, sale, out, deleted)
            - category (str): Filter by category ID
            - page (int): Page number for pagination (default: 1)
            - per_page (int): Number of products per page (default: 15)

    Returns:
        dict: API response with list of products and pagination info
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
            request_params["status"] = params.status
        if params.category:
            request_params["category"] = params.category

        result = await client.get("/products", params=request_params)
        return result
    except Exception as e:
        return format_error(e)


async def salla_get_product(params: GetProductInput, ctx: Context) -> dict:
    """
    Get detailed information about a specific product.

    Args:
        params: Input parameters containing:
            - product_id (int): The unique ID of the product

    Returns:
        dict: Product details including name, price, quantity, images, options, etc.
    """
    try:
        client = get_salla_client(ctx)
        result = await client.get(f"/products/{params.product_id}")
        return result

    except Exception as e:
        return format_error(e)


async def salla_create_product(params: CreateProductInput, ctx: Context) -> dict:
    """
    Create a new product in the Salla store.

    Args:
        params: Input parameters containing:
            - name (str): Product name (required)
            - price (float): Product price (required)
            - product_type (str): Product type (required)
            - quantity (int): Quantity of the product
            - description (str): Product description
            - sku (str): Stock Keeping Unit
            - status (str): Product status (sale, out, hidden, deleted)
            - sale_price (float): The sale price of the product
            - cost_price (float): Product cost price
            - images (list): List of images
            - options (list): List of product options
            - metadata_title (str): SEO Title
            - metadata_description (str): SEO Description

    Returns:
        dict: Created product details
    """
    try:
        client = get_salla_client(ctx)
        data = params.model_dump(exclude_unset=True, exclude_none=True)
        # Convert enum to string value
        if "product_type" in data:
            data["product_type"] = data["product_type"].value

        result = await client.post("/products", data=data)
        return result
    except Exception as e:
        return format_error(e)


async def salla_update_product(params: UpdateProductInput, ctx: Context) -> dict:
    """
    Update an existing product's details.

    Args:
        params: Input parameters containing:
            - product_id (int): The unique ID of the product to update (required)
            - name (str): New product name
            - price (float): New selling price
            - quantity (int): New available quantity
            - description (str): New product description
            - sku (str): New SKU
            - status (str): New status (sale, out, hidden, deleted)
            - sale_price (float): New sale price
            - require_shipping (bool): Update shipping requirement

    Returns:
        dict: Updated product details
    """
    try:
        client = get_salla_client(ctx)
        # Exclude product_id from payload, only use for URL
        data = params.model_dump(exclude_unset=True, exclude_none=True, exclude={"product_id"})
        # Remove empty strings
        data = {k: v for k, v in data.items() if v != ""}

        if not data:
            return {"error": "No fields provided to update"}

        result = await client.put(f"/products/{params.product_id}", data=data)
        return result
    except Exception as e:
        return format_error(e)
