"""Pydantic models for the online shop API.

Money is stored as integer kopecks (1 RUB = 100 kopecks) to avoid
floating-point rounding errors.

All models are frozen (immutable): the store changes state only via
model_copy(update=...) inside its lock, so objects handed out to callers
can never be mutated behind the lock's back.
"""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field


class OrderStatus(StrEnum):
    """Order lifecycle: created -> paid | cancelled."""

    CREATED = "created"
    PAID = "paid"
    CANCELLED = "cancelled"


class FrozenModel(BaseModel):
    """Base for all models: immutable instances."""

    model_config = ConfigDict(frozen=True)


# === Domain entities ===


class Product(FrozenModel):
    """Product in the catalog."""

    id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    price_cents: int = Field(gt=0, description="Price in kopecks (1 RUB = 100)")
    category: str = Field(min_length=1, max_length=100)
    stock: int = Field(ge=0, description="Available quantity")


class OrderItem(FrozenModel):
    """Single line of an order; title and price are fixed at purchase time."""

    product_id: int = Field(gt=0)
    title: str
    price_cents: int = Field(gt=0, description="Price snapshot, kopecks")
    quantity: int = Field(gt=0, le=1000)

    @computed_field
    @property
    def subtotal_cents(self) -> int:
        """Line total in kopecks."""
        return self.price_cents * self.quantity


class Order(FrozenModel):
    """Customer order."""

    id: int = Field(gt=0)
    items: tuple[OrderItem, ...] = Field(min_length=1)
    total_cents: int = Field(ge=0)
    status: OrderStatus = OrderStatus.CREATED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# === Request schemas (strict: unknown fields are rejected) ===


class OrderItemRequest(FrozenModel):
    """One line of an order creation request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=1000)


class OrderCreateRequest(FrozenModel):
    """Request body for POST /orders."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={"examples": [{"items": [{"product_id": 1, "quantity": 2}]}]},
    )

    items: list[OrderItemRequest] = Field(min_length=1, max_length=50)


# === Response schemas ===


class ProductListResponse(FrozenModel):
    """Paginated catalog page."""

    items: list[Product]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(gt=0)


class OrderListResponse(FrozenModel):
    """Paginated orders page."""

    items: list[Order]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(gt=0)


class HealthResponse(FrozenModel):
    """GET /health payload."""

    status: str = "ok"
    version: str
    uptime_seconds: float = Field(ge=0)


class ErrorResponse(FrozenModel):
    """Error payload, compatible with FastAPI HTTPException."""

    detail: str
