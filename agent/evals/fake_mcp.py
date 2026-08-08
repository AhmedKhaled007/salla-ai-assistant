"""Deterministic in-memory replacement for Salla MCP tool execution."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


class FakeSallaStore:
    """Execute the current Salla tool surface against synthetic data."""

    def __init__(self, fixture_path: Path) -> None:
        self.data = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.calls: list[dict[str, Any]] = []

    async def execute_tool(self, name: str, arguments: dict) -> str:
        result = self._execute(name, arguments)
        self.calls.append({
            "name": name,
            "arguments": deepcopy(arguments),
            "result": deepcopy(result),
        })
        return json.dumps(result, ensure_ascii=False)

    def _execute(self, name: str, arguments: dict) -> dict:
        # MCP tools expose their Pydantic input as a single `params` argument.
        params = arguments.get("params", arguments)
        handlers = {
            "salla_get_store_info": self._get_store,
            "salla_list_products": self._list_products,
            "salla_get_product": self._get_product,
            "salla_create_product": self._create_product,
            "salla_update_product": self._update_product,
            "salla_list_orders": self._list_orders,
            "salla_get_order": self._get_order,
            "salla_create_order": self._create_order,
            "salla_update_order_status": self._update_order_status,
            "salla_list_customers": self._list_customers,
            "salla_get_customer": self._get_customer,
            "salla_create_customer": self._create_customer,
        }
        handler = handlers.get(name)
        if handler is None:
            return {"error": f"Unsupported fake tool: {name}"}
        return handler(params)

    def _get_store(self, _: dict) -> dict:
        return {"data": deepcopy(self.data["store"])}

    def _list_products(self, arguments: dict) -> dict:
        products = self._filter(
            self.data["products"],
            arguments.get("keyword", ""),
            fields=("name", "sku"),
        )
        status = arguments.get("status")
        if status:
            products = [item for item in products if item["status"] == status]
        return {"data": deepcopy(products), "pagination": {"count": len(products)}}

    def _get_product(self, arguments: dict) -> dict:
        return self._find("products", "id", arguments["product_id"])

    def _create_product(self, arguments: dict) -> dict:
        product = {"id": self._next_id("products"), **deepcopy(arguments)}
        self.data["products"].append(product)
        return {"data": product}

    def _update_product(self, arguments: dict) -> dict:
        product = self._item("products", "id", arguments["product_id"])
        if product is None:
            return {"error": "Product not found"}
        product.update({
            key: value
            for key, value in arguments.items()
            if key != "product_id"
        })
        return {"data": deepcopy(product)}

    def _list_orders(self, arguments: dict) -> dict:
        orders = self._filter(
            self.data["orders"],
            arguments.get("keyword", ""),
            fields=("customer_name", "id"),
        )
        status = arguments.get("status")
        if status:
            allowed = set(str(status).split(","))
            orders = [item for item in orders if item["status"] in allowed]
        return {"data": deepcopy(orders), "pagination": {"count": len(orders)}}

    def _get_order(self, arguments: dict) -> dict:
        return self._find("orders", "id", arguments["order_id"])

    def _create_order(self, arguments: dict) -> dict:
        order = {
            "id": self._next_id("orders"),
            "status": "created",
            **deepcopy(arguments),
        }
        self.data["orders"].append(order)
        return {"data": order}

    def _update_order_status(self, arguments: dict) -> dict:
        order = self._item("orders", "id", arguments["order_id"])
        if order is None:
            return {"error": "Order not found"}
        order["status"] = arguments.get("slug") or arguments.get("status_id")
        return {"data": deepcopy(order)}

    def _list_customers(self, arguments: dict) -> dict:
        customers = self._filter(
            self.data["customers"],
            arguments.get("keyword", ""),
            fields=("first_name", "last_name", "email", "mobile"),
        )
        return {"data": deepcopy(customers), "pagination": {"count": len(customers)}}

    def _get_customer(self, arguments: dict) -> dict:
        return self._find("customers", "id", arguments["customer_id"])

    def _create_customer(self, arguments: dict) -> dict:
        customer = {"id": self._next_id("customers"), **deepcopy(arguments)}
        self.data["customers"].append(customer)
        return {"data": customer}

    def _find(self, collection: str, key: str, value: Any) -> dict:
        item = self._item(collection, key, value)
        if item is None:
            return {"error": f"{collection.removesuffix('s').title()} not found"}
        return {"data": deepcopy(item)}

    def _item(self, collection: str, key: str, value: Any) -> dict | None:
        return next(
            (item for item in self.data[collection] if item.get(key) == value),
            None,
        )

    def _next_id(self, collection: str) -> int:
        return max(item["id"] for item in self.data[collection]) + 1

    @staticmethod
    def _filter(items: list[dict], keyword: str, fields: tuple[str, ...]) -> list[dict]:
        if not keyword:
            return list(items)
        needle = str(keyword).lower()
        return [
            item
            for item in items
            if any(needle in str(item.get(field, "")).lower() for field in fields)
        ]
