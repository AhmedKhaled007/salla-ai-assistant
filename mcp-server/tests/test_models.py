"""Tests for Pydantic input models validation."""
import pytest
from pydantic import ValidationError

from mcp_server.models import (
    # Product models
    ListProductsInput,
    GetProductInput,
    CreateProductInput,
    UpdateProductInput,
    ProductType,
    # Order models
    ListOrdersInput,
    GetOrderInput,
    CreateOrderInput,
    UpdateOrderStatusInput,
    OrderProduct,
    DeliveryMethod,
    PaymentMethod,
    # Customer models
    ListCustomersInput,
    GetCustomerInput,
    CreateCustomerInput,
)


# =============================================================================
# PRODUCT MODEL TESTS
# =============================================================================

class TestListProductsInput:
    """Tests for ListProductsInput model."""

    def test_default_values(self):
        """Test that defaults are applied correctly."""
        params = ListProductsInput()
        assert params.page == 1
        assert params.per_page == 15
        assert params.keyword == ""
        assert params.status == ""
        assert params.category == ""

    def test_custom_values(self):
        """Test with custom values."""
        params = ListProductsInput(
            keyword="phone",
            status="sale",
            category="electronics",
            page=2,
            per_page=50
        )
        assert params.keyword == "phone"
        assert params.status == "sale"
        assert params.page == 2
        assert params.per_page == 50

    def test_page_minimum(self):
        """Test page must be >= 1."""
        with pytest.raises(ValidationError) as exc:
            ListProductsInput(page=0)
        assert "page" in str(exc.value)

    def test_per_page_maximum(self):
        """Test per_page must be <= 100."""
        with pytest.raises(ValidationError) as exc:
            ListProductsInput(per_page=101)
        assert "per_page" in str(exc.value)

    @pytest.mark.parametrize("per_page", [1, 50, 100])
    def test_valid_per_page_range(self, per_page):
        """Test valid per_page values."""
        params = ListProductsInput(per_page=per_page)
        assert params.per_page == per_page

    def test_whitespace_stripping(self):
        """Test that string fields strip whitespace."""
        params = ListProductsInput(keyword="  phone  ")
        assert params.keyword == "phone"


class TestGetProductInput:
    """Tests for GetProductInput model."""

    def test_required_product_id(self):
        """Test product_id is required."""
        with pytest.raises(ValidationError) as exc:
            GetProductInput()
        assert "product_id" in str(exc.value)

    def test_valid_product_id(self):
        """Test with valid product_id."""
        params = GetProductInput(product_id=12345)
        assert params.product_id == 12345


class TestCreateProductInput:
    """Tests for CreateProductInput model."""

    def test_required_fields(self):
        """Test required fields validation."""
        with pytest.raises(ValidationError) as exc:
            CreateProductInput()
        errors = exc.value.errors()
        required_fields = {e["loc"][0] for e in errors}
        assert "name" in required_fields
        assert "price" in required_fields
        assert "product_type" in required_fields

    def test_minimal_valid_input(self):
        """Test with minimal required fields."""
        params = CreateProductInput(
            name="Test Product",
            price=99.99,
            product_type=ProductType.PRODUCT
        )
        assert params.name == "Test Product"
        assert params.price == 99.99
        assert params.product_type == ProductType.PRODUCT

    def test_full_input(self):
        """Test with all fields."""
        params = CreateProductInput(
            name="Full Product",
            price=199.99,
            product_type=ProductType.SERVICE,
            quantity=50,
            description="A full description",
            sku="SKU-001",
            status="sale",
            sale_price=149.99,
            cost_price=100.00,
        )
        assert params.quantity == 50
        assert params.description == "A full description"
        assert params.sale_price == 149.99

    def test_price_minimum(self):
        """Test price must be >= 0."""
        with pytest.raises(ValidationError) as exc:
            CreateProductInput(
                name="Test",
                price=-10,
                product_type=ProductType.PRODUCT
            )
        assert "price" in str(exc.value)

    def test_name_minimum_length(self):
        """Test name must have at least 1 character."""
        with pytest.raises(ValidationError) as exc:
            CreateProductInput(
                name="",
                price=10,
                product_type=ProductType.PRODUCT
            )
        assert "name" in str(exc.value)

    @pytest.mark.parametrize("product_type", list(ProductType))
    def test_all_product_types(self, product_type):
        """Test all product types are valid."""
        params = CreateProductInput(
            name="Test",
            price=10,
            product_type=product_type
        )
        assert params.product_type == product_type

    def test_model_dump_excludes_unset(self):
        """Test model_dump correctly excludes unset fields."""
        params = CreateProductInput(
            name="Test",
            price=10,
            product_type=ProductType.PRODUCT
        )
        data = params.model_dump(exclude_unset=True, exclude_none=True)
        assert "name" in data
        assert "price" in data
        assert "product_type" in data
        assert "quantity" not in data  # Not set
        assert "description" not in data  # Not set


class TestUpdateProductInput:
    """Tests for UpdateProductInput model."""

    def test_required_product_id(self):
        """Test product_id is required."""
        with pytest.raises(ValidationError) as exc:
            UpdateProductInput()
        assert "product_id" in str(exc.value)

    def test_partial_update(self):
        """Test partial update with only some fields."""
        params = UpdateProductInput(
            product_id=123,
            price=79.99
        )
        data = params.model_dump(exclude_unset=True, exclude_none=True, exclude={"product_id"})
        assert "price" in data
        assert data["price"] == 79.99
        assert "name" not in data


# =============================================================================
# ORDER MODEL TESTS
# =============================================================================

class TestListOrdersInput:
    """Tests for ListOrdersInput model."""

    def test_default_values(self):
        """Test default pagination values."""
        params = ListOrdersInput()
        assert params.page == 1
        assert params.per_page == 15

    def test_date_filters(self):
        """Test date filter fields."""
        params = ListOrdersInput(
            from_date="2024-01-01",
            to_date="2024-12-31"
        )
        assert params.from_date == "2024-01-01"
        assert params.to_date == "2024-12-31"


class TestCreateOrderInput:
    """Tests for CreateOrderInput model."""

    def test_required_fields(self):
        """Test required fields."""
        with pytest.raises(ValidationError) as exc:
            CreateOrderInput()
        errors = exc.value.errors()
        required_fields = {e["loc"][0] for e in errors}
        assert "customer_id" in required_fields
        assert "products" in required_fields

    def test_valid_order(self):
        """Test valid order creation input."""
        params = CreateOrderInput(
            customer_id=123,
            products=[
                OrderProduct(identifier="12345", quantity=2),
                OrderProduct(identifier="SKU-001", identifier_type="sku", quantity=1)
            ]
        )
        assert params.customer_id == 123
        assert len(params.products) == 2
        assert params.delivery_method == DeliveryMethod.SHIPPING  # default
        assert params.payment_method == PaymentMethod.BANK  # default

    def test_products_minimum(self):
        """Test products list must have at least one item."""
        with pytest.raises(ValidationError) as exc:
            CreateOrderInput(customer_id=123, products=[])
        assert "products" in str(exc.value)

    @pytest.mark.parametrize("method", list(PaymentMethod))
    def test_all_payment_methods(self, method):
        """Test all payment methods are valid."""
        params = CreateOrderInput(
            customer_id=123,
            products=[OrderProduct(identifier="1")],
            payment_method=method
        )
        assert params.payment_method == method


class TestUpdateOrderStatusInput:
    """Tests for UpdateOrderStatusInput model."""

    def test_required_order_id(self):
        """Test order_id is required."""
        with pytest.raises(ValidationError) as exc:
            UpdateOrderStatusInput()
        assert "order_id" in str(exc.value)

    def test_status_by_id(self):
        """Test updating status by ID."""
        params = UpdateOrderStatusInput(order_id=123, status_id=5)
        assert params.status_id == 5

    def test_status_by_slug(self):
        """Test updating status by slug."""
        params = UpdateOrderStatusInput(order_id=123, slug="completed")
        assert params.slug == "completed"


# =============================================================================
# CUSTOMER MODEL TESTS
# =============================================================================

class TestCreateCustomerInput:
    """Tests for CreateCustomerInput model."""

    def test_required_fields(self):
        """Test all required fields."""
        with pytest.raises(ValidationError) as exc:
            CreateCustomerInput()
        errors = exc.value.errors()
        required_fields = {e["loc"][0] for e in errors}
        assert "first_name" in required_fields
        assert "last_name" in required_fields
        assert "mobile" in required_fields
        assert "mobile_code_country" in required_fields

    def test_valid_customer(self):
        """Test valid customer creation."""
        params = CreateCustomerInput(
            first_name="Ahmed",
            last_name="Khaled",
            mobile="500000000",
            mobile_code_country="+966"
        )
        assert params.first_name == "Ahmed"
        assert params.last_name == "Khaled"

    def test_optional_fields(self):
        """Test optional fields."""
        params = CreateCustomerInput(
            first_name="Ali",
            last_name="Mohamed",
            mobile="500000000",
            mobile_code_country="+966",
            email="ali@example.com",
            gender="male",
            birthday="1990-01-15",
            groups=[1, 2, 3]
        )
        assert params.email == "ali@example.com"
        assert params.groups == [1, 2, 3]

    def test_name_max_length(self):
        """Test name fields have max length."""
        long_name = "A" * 30  # Exceeds 25 char limit
        with pytest.raises(ValidationError) as exc:
            CreateCustomerInput(
                first_name=long_name,
                last_name="Test",
                mobile="500000000",
                mobile_code_country="+966"
            )
        assert "first_name" in str(exc.value)


class TestListCustomersInput:
    """Tests for ListCustomersInput model."""

    def test_default_pagination(self):
        """Test default pagination values."""
        params = ListCustomersInput()
        assert params.page == 1
        assert params.per_page == 15

    def test_keyword_search(self):
        """Test keyword search parameter."""
        params = ListCustomersInput(keyword="ahmed@example.com")
        assert params.keyword == "ahmed@example.com"
