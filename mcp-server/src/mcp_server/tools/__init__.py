"""Salla MCP Server tools package."""
from .products import (
    salla_list_products,
    salla_get_product,
    salla_create_product,
    salla_update_product,
)
from .orders import (
    salla_list_orders,
    salla_get_order,
    salla_create_order,
    salla_update_order_status,
)
from .customers import (
    salla_list_customers,
    salla_get_customer,
    salla_create_customer,
)
from .store import salla_get_store_info

__all__ = [
    # Products
    "salla_list_products",
    "salla_get_product",
    "salla_create_product",
    "salla_update_product",
    # Orders
    "salla_list_orders",
    "salla_get_order",
    "salla_create_order",
    "salla_update_order_status",
    # Customers
    "salla_list_customers",
    "salla_get_customer",
    "salla_create_customer",
    # Store
    "salla_get_store_info",
]
