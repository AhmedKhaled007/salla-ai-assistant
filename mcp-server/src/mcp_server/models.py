"""Pydantic input models for Salla MCP Server tools."""
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


# ENUMS

class ProductStatus(str, Enum):
    """Product status options."""
    HIDDEN = "hidden"
    SALE = "sale"
    OUT = "out"
    DELETED = "deleted"


class ProductType(str, Enum):
    """Product type options."""
    PRODUCT = "product"
    SERVICE = "service"
    GROUP_PRODUCTS = "group_products"
    CODES = "codes"
    DIGITAL = "digital"
    FOOD = "food"
    BOOKING = "booking"
    DONATING = "donating"


class DeliveryMethod(str, Enum):
    """Order delivery method options."""
    SHIPPING = "shipping"
    PICKUP = "pickup"


class PaymentMethod(str, Enum):
    """Order payment method options."""
    BANK = "bank"
    CREDIT_CARD = "credit_card"
    MADA = "mada"
    COD = "cod"


class Gender(str, Enum):
    """Customer gender options."""
    MALE = "male"
    FEMALE = "female"


# PRODUCT MODELS

class ListProductsInput(BaseModel):
    """Input model for listing products."""
    model_config = ConfigDict(str_strip_whitespace=True)

    keyword: str = Field(
        default="",
        description="Search keyword to filter products by name or SKU"
    )
    status: str = Field(
        default="",
        description="Filter by product status: hidden, sale, out, deleted"
    )
    category: str = Field(
        default="",
        description="Filter by category ID"
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number for pagination"
    )
    per_page: int = Field(
        default=15,
        ge=1,
        le=100,
        description="Number of products per page (max 100)"
    )


class GetProductInput(BaseModel):
    """Input model for getting a single product."""
    model_config = ConfigDict(str_strip_whitespace=True)

    product_id: int = Field(
        ...,
        description="The unique ID of the product"
    )


class CreateProductInput(BaseModel):
    """Input model for creating a product."""
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Product name (required)"
    )
    price: float = Field(
        ...,
        ge=0,
        description="Product price (required)"
    )
    product_type: ProductType = Field(
        ...,
        description="Product type: product, service, group_products, codes, digital, food, booking, donating (required)"
    )
    quantity: Optional[int] = Field(
        default=None,
        ge=0,
        description="Quantity of the product"
    )
    description: str = Field(
        default="",
        description="Product description"
    )
    sku: str = Field(
        default="",
        max_length=100,
        description="Stock Keeping Unit"
    )
    status: str = Field(
        default="",
        description="Product status: sale, out, hidden, deleted"
    )
    sale_price: Optional[float] = Field(
        default=None,
        ge=0,
        description="The sale price of the product"
    )
    cost_price: Optional[float] = Field(
        default=None,
        ge=0,
        description="Product cost price"
    )
    images: Optional[list[dict]] = Field(
        default=None,
        description="List of images [{\"original\": \"url\", \"thumbnail\": \"url\", ...}]"
    )
    options: Optional[list[dict]] = Field(
        default=None,
        description="List of product options"
    )
    metadata_title: str = Field(
        default="",
        description="SEO Title"
    )
    metadata_description: str = Field(
        default="",
        description="SEO Description"
    )


class UpdateProductInput(BaseModel):
    """Input model for updating a product."""
    model_config = ConfigDict(str_strip_whitespace=True)

    product_id: int = Field(
        ...,
        description="The unique ID of the product to update (required)"
    )
    name: str = Field(
        default="",
        max_length=255,
        description="New product name"
    )
    price: Optional[float] = Field(
        default=None,
        ge=0,
        description="New selling price"
    )
    quantity: Optional[int] = Field(
        default=None,
        ge=0,
        description="New available quantity"
    )
    description: str = Field(
        default="",
        description="New product description"
    )
    sku: str = Field(
        default="",
        max_length=100,
        description="New SKU"
    )
    status: str = Field(
        default="",
        description="New status: sale, out, hidden, deleted"
    )
    sale_price: Optional[float] = Field(
        default=None,
        ge=0,
        description="New sale price"
    )
    require_shipping: Optional[bool] = Field(
        default=None,
        description="Update shipping requirement"
    )


# ORDER MODELS

class ListOrdersInput(BaseModel):
    """Input model for listing orders."""
    model_config = ConfigDict(str_strip_whitespace=True)

    page: int = Field(
        default=1,
        ge=1,
        description="Page number"
    )
    per_page: int = Field(
        default=15,
        ge=1,
        le=100,
        description="Number of orders per page"
    )
    keyword: str = Field(
        default="",
        description="Search keyword (customer name, mobile, shipping number, etc.)"
    )
    status: str = Field(
        default="",
        description="Filter by status slug or ID (can be comma-separated)"
    )
    from_date: str = Field(
        default="",
        description="Filter orders created after date (YYYY-MM-DD)"
    )
    to_date: str = Field(
        default="",
        description="Filter orders created before date (YYYY-MM-DD)"
    )


class GetOrderInput(BaseModel):
    """Input model for getting a single order."""
    model_config = ConfigDict(str_strip_whitespace=True)

    order_id: int = Field(
        ...,
        description="The unique ID of the order"
    )
    format: str = Field(
        default="light",
        description="Optional format. Set to 'light' to reduce response size."
    )


class OrderProduct(BaseModel):
    """Product item for order creation."""
    identifier: str = Field(
        ...,
        description="Product ID or SKU"
    )
    identifier_type: str = Field(
        default="id",
        description="Type of identifier: 'id' or 'sku'"
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="Quantity of the product"
    )


class CreateOrderInput(BaseModel):
    """Input model for creating an order."""
    model_config = ConfigDict(str_strip_whitespace=True)

    customer_id: int = Field(
        ...,
        description="ID of the customer placing the order (required)"
    )
    products: list[OrderProduct] = Field(
        ...,
        min_length=1,
        description="List of products (required). Each item: {identifier, identifier_type, quantity}"
    )
    delivery_method: DeliveryMethod = Field(
        default=DeliveryMethod.SHIPPING,
        description="Method of delivery: shipping, pickup"
    )
    payment_method: PaymentMethod = Field(
        default=PaymentMethod.BANK,
        description="Payment method: bank, credit_card, mada, cod"
    )
    bank_id: Optional[int] = Field(
        default=None,
        description="Required if payment_method is bank"
    )
    receipt_image: str = Field(
        default="",
        description="Required if payment_method is bank"
    )


class UpdateOrderStatusInput(BaseModel):
    """Input model for updating order status."""
    model_config = ConfigDict(str_strip_whitespace=True)

    order_id: int = Field(
        ...,
        description="The unique ID of the order to update (required)"
    )
    status_id: Optional[int] = Field(
        default=None,
        description="The new status ID to set (optional if slug is provided)"
    )
    slug: str = Field(
        default="",
        description="The new status slug (e.g. 'completed', 'under_review') (optional if status_id provided)"
    )
    note: str = Field(
        default="",
        description="Note about status change"
    )
    restore_items: bool = Field(
        default=False,
        description="Whether to restore items to stock (if applicable)"
    )


# CUSTOMER MODELS

class ListCustomersInput(BaseModel):
    """Input model for listing customers."""
    model_config = ConfigDict(str_strip_whitespace=True)

    page: int = Field(
        default=1,
        ge=1,
        description="Page number for pagination"
    )
    per_page: int = Field(
        default=15,
        ge=1,
        le=100,
        description="Number of customers per page"
    )
    keyword: str = Field(
        default="",
        description="Search by customer name, email, or mobile number"
    )
    date_from: str = Field(
        default="",
        description="Filter customers created after (YYYY-MM-DD)"
    )
    date_to: str = Field(
        default="",
        description="Filter customers created before (YYYY-MM-DD)"
    )


class GetCustomerInput(BaseModel):
    """Input model for getting a single customer."""
    model_config = ConfigDict(str_strip_whitespace=True)

    customer_id: int = Field(
        ...,
        description="The unique ID of the customer"
    )


class CreateCustomerInput(BaseModel):
    """Input model for creating a customer."""
    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str = Field(
        ...,
        min_length=1,
        max_length=25,
        description="Customer given name (required)"
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=25,
        description="Customer family name (required)"
    )
    mobile: str = Field(
        ...,
        min_length=1,
        description="Mobile number without country code (required)"
    )
    mobile_code_country: str = Field(
        ...,
        min_length=1,
        description="Country code for mobile (e.g. '+966') (required)"
    )
    email: str = Field(
        default="",
        description="Email address of the customer"
    )
    gender: str = Field(
        default="",
        description="Gender: male, female"
    )
    birthday: str = Field(
        default="",
        description="Date of birth (YYYY-MM-DD)"
    )
    groups: Optional[list[int]] = Field(
        default=None,
        description="List of group IDs to assign the customer to"
    )


# EXPORTS

__all__ = [
    # Enums
    "ProductStatus",
    "ProductType",
    "DeliveryMethod",
    "PaymentMethod",
    "Gender",
    # Product models
    "ListProductsInput",
    "GetProductInput",
    "CreateProductInput",
    "UpdateProductInput",
    # Order models
    "ListOrdersInput",
    "GetOrderInput",
    "OrderProduct",
    "CreateOrderInput",
    "UpdateOrderStatusInput",
    # Customer models
    "ListCustomersInput",
    "GetCustomerInput",
    "CreateCustomerInput",
]
