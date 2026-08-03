"""Customer tools for Salla MCP Server."""
from mcp.server.fastmcp import Context

from ..models import (
    ListCustomersInput,
    GetCustomerInput,
    CreateCustomerInput,
)
from ..utils import get_salla_client, format_error

__all__ = [
    "salla_list_customers",
    "salla_get_customer",
    "salla_create_customer",
]


async def salla_list_customers(params: ListCustomersInput, ctx: Context) -> dict:
    """
    List all customers in the Salla store with optional filtering.

    Args:
        params: Input parameters containing:
            - page (int): Page number for pagination (default: 1)
            - per_page (int): Number of customers per page (default: 15)
            - keyword (str): Search by customer name, email, or mobile number
            - date_from (str): Filter customers created after (YYYY-MM-DD)
            - date_to (str): Filter customers created before (YYYY-MM-DD)

    Returns:
        dict: API response with list of customers and pagination info
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
        if params.date_from:
            request_params["date_from"] = params.date_from
        if params.date_to:
            request_params["date_to"] = params.date_to

        result = await client.get("/customers", params=request_params)
        return result
    except Exception as e:
        return format_error(e)


async def salla_get_customer(params: GetCustomerInput, ctx: Context) -> dict:
    """
    Get detailed information about a specific customer.

    Args:
        params: Input parameters containing:
            - customer_id (int): The unique ID of the customer

    Returns:
        dict: Customer details including name, contact info, addresses, orders
    """
    try:
        client = get_salla_client(ctx)
        result = await client.get(f"/customers/{params.customer_id}")
        return result
    except Exception as e:
        return format_error(e)


async def salla_create_customer(params: CreateCustomerInput, ctx: Context) -> dict:
    """
    Create a new customer in the Salla store.

    Args:
        params: Input parameters containing:
            - first_name (str): Customer given name (required)
            - last_name (str): Customer family name (required)
            - mobile (str): Mobile number without country code (required)
            - mobile_code_country (str): Country code (e.g. '+966') (required)
            - email (str): Email address of the customer
            - gender (str): Gender (male, female)
            - birthday (str): Date of birth (YYYY-MM-DD)
            - groups (list[int]): List of group IDs

    Returns:
        dict: Created customer details
    """
    try:
        client = get_salla_client(ctx)
        data = params.model_dump(exclude_unset=True, exclude_none=True)
        # Remove empty strings
        data = {k: v for k, v in data.items() if v != ""}

        result = await client.post("/customers", data=data)
        return result
    except Exception as e:
        return format_error(e)
