"""In-memory data store with thread-safety.

Data lives in process memory and resets on restart. To switch to a database
later, replace this module only: routers depend on its public methods and
exceptions, not on storage details.

Models are frozen, so every mutation is a copy-on-write done under the lock.
Objects returned to callers are immutable snapshots.
"""

from datetime import UTC, datetime
from threading import Lock

from app.models import Order, OrderItem, OrderStatus, Product


class StoreError(Exception):
    """Base class for domain errors raised by the store."""


class ProductNotFound(StoreError):
    """Requested product does not exist (maps to HTTP 404)."""

    def __init__(self, product_id: int) -> None:
        self.product_id = product_id
        super().__init__(f"Product {product_id} not found")


class OrderNotFound(StoreError):
    """Requested order does not exist (maps to HTTP 404)."""

    def __init__(self, order_id: int) -> None:
        self.order_id = order_id
        super().__init__(f"Order {order_id} not found")


class InsufficientStock(StoreError):
    """Not enough units in stock (maps to HTTP 409)."""

    def __init__(self, product_id: int, requested: int, available: int) -> None:
        self.product_id = product_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for product {product_id}: "
            f"requested {requested}, available {available}"
        )


class InvalidOrderState(StoreError):
    """Order status forbids the transition (maps to HTTP 409)."""

    def __init__(self, order_id: int, status: OrderStatus, action: str) -> None:
        self.order_id = order_id
        self.status = status
        super().__init__(f"Cannot {action} order {order_id} in status {status}")


class InvalidQuantity(StoreError):
    """Quantity must be positive (maps to HTTP 422)."""

    def __init__(self, quantity: int) -> None:
        self.quantity = quantity
        super().__init__(f"Quantity must be > 0, got {quantity}")


class InMemoryStore:
    """Thread-safe in-memory store for products and orders."""

    def __init__(self) -> None:
        self._products: dict[int, Product] = {}
        self._orders: dict[int, Order] = {}
        self._next_product_id: int = 1
        self._next_order_id: int = 1
        self._lock = Lock()

    # === Products ===

    def add_product(
        self, title: str, price_cents: int, category: str, stock: int
    ) -> Product:
        """Add a product to the catalog and return it."""
        with self._lock:
            product = Product(
                id=self._next_product_id,
                title=title,
                price_cents=price_cents,
                category=category,
                stock=stock,
            )
            self._products[product.id] = product
            self._next_product_id += 1
            return product

    def get_product(self, product_id: int) -> Product | None:
        """Return a product snapshot, or None if it does not exist."""
        with self._lock:
            return self._products.get(product_id)

    def list_products(
        self,
        category: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Product], int]:
        """Return (page of products, total count after filtering)."""
        with self._lock:
            items = list(self._products.values())
            if category is not None:
                items = [p for p in items if p.category == category]
            total = len(items)
            return items[offset : offset + limit], total

    # === Orders ===

    def create_order(self, items: list[tuple[int, int]]) -> Order:
        """Create an order atomically.

        items: list of (product_id, quantity). Duplicate product ids are merged
        into one line and validated by their total, so a single order cannot
        oversell a product through several lines.
        All-or-nothing: if any line fails, no stock is deducted.
        """
        quantities: dict[int, int] = {}
        for product_id, quantity in items:
            if quantity <= 0:
                raise InvalidQuantity(quantity)
            quantities[product_id] = quantities.get(product_id, 0) + quantity

        with self._lock:
            # 1. Validate all aggregated lines first (no mutations yet)
            order_items: list[OrderItem] = []
            for product_id, quantity in quantities.items():
                product = self._products.get(product_id)
                if product is None:
                    raise ProductNotFound(product_id)
                if product.stock < quantity:
                    raise InsufficientStock(product_id, quantity, product.stock)
                order_items.append(
                    OrderItem(
                        product_id=product.id,
                        title=product.title,
                        price_cents=product.price_cents,
                        quantity=quantity,
                    )
                )

            # 2. Everything is valid: deduct stock by copy-on-write
            for product_id, quantity in quantities.items():
                product = self._products[product_id]
                self._products[product_id] = product.model_copy(
                    update={"stock": product.stock - quantity}
                )

            # 3. Persist the order
            order = Order(
                id=self._next_order_id,
                items=tuple(order_items),
                total_cents=sum(item.subtotal_cents for item in order_items),
                status=OrderStatus.CREATED,
                created_at=datetime.now(UTC),
            )
            self._orders[order.id] = order
            self._next_order_id += 1
            return order

    def get_order(self, order_id: int) -> Order | None:
        """Return an order snapshot, or None if it does not exist."""
        with self._lock:
            return self._orders.get(order_id)

    def list_orders(
        self,
        status: OrderStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Order], int]:
        """Return (page of orders, total count after filtering)."""
        with self._lock:
            items = list(self._orders.values())
            if status is not None:
                items = [o for o in items if o.status == status]
            total = len(items)
            return items[offset : offset + limit], total

    def pay_order(self, order_id: int) -> Order:
        """Pay an order. Only CREATED orders can be paid."""
        with self._lock:
            order = self._require_order(order_id)
            if order.status != OrderStatus.CREATED:
                raise InvalidOrderState(order_id, order.status, "pay")
            paid = order.model_copy(update={"status": OrderStatus.PAID})
            self._orders[order_id] = paid
            return paid

    def cancel_order(self, order_id: int) -> Order:
        """Cancel an order and return stock. Only CREATED orders can be cancelled."""
        with self._lock:
            order = self._require_order(order_id)
            if order.status != OrderStatus.CREATED:
                raise InvalidOrderState(order_id, order.status, "cancel")
            for item in order.items:
                product = self._products.get(item.product_id)
                if product is not None:  # products are never deleted
                    self._products[product.id] = product.model_copy(
                        update={"stock": product.stock + item.quantity}
                    )
            cancelled = order.model_copy(update={"status": OrderStatus.CANCELLED})
            self._orders[order_id] = cancelled
            return cancelled

    def _require_order(self, order_id: int) -> Order:
        """Return an order or raise OrderNotFound. Caller must hold the lock."""
        order = self._orders.get(order_id)
        if order is None:
            raise OrderNotFound(order_id)
        return order

    # === Counters for metrics ===

    def count_products(self) -> int:
        """Number of products in the catalog."""
        with self._lock:
            return len(self._products)

    def count_orders(self) -> int:
        """Number of orders kept in memory."""
        with self._lock:
            return len(self._orders)

    def total_stock_units(self) -> int:
        """Total units left in stock across all products."""
        with self._lock:
            return sum(p.stock for p in self._products.values())
