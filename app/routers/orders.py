"""Order endpoints: create, read, list, pay and cancel."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.deps import SettingsDep, StoreDep
from app.models import (
    ErrorResponse,
    Order,
    OrderCreateRequest,
    OrderListResponse,
    OrderStatus,
)
from app.store import (
    InsufficientStock,
    InvalidOrderState,
    InvalidQuantity,
    OrderNotFound,
    ProductNotFound,
)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post(
    "",
    response_model=Order,
    status_code=status.HTTP_201_CREATED,
    summary="Create an order and deduct stock atomically",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def create_order(payload: OrderCreateRequest, store: StoreDep) -> Order:
    """Create an order. Duplicate product ids are merged into a single line."""
    try:
        return store.create_order(
            [(item.product_id, item.quantity) for item in payload.items]
        )
    except ProductNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except InsufficientStock as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except InvalidQuantity as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@router.get("", response_model=OrderListResponse, summary="List orders")
def list_orders(
    store: StoreDep,
    settings: SettingsDep,
    order_status: Annotated[
        OrderStatus | None, Query(alias="status", description="Filter by status")
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Items to skip")] = 0,
    limit: Annotated[
        int | None, Query(ge=1, description="Page size, defaults to DEFAULT_PAGE_LIMIT")
    ] = None,
) -> OrderListResponse:
    """Return a page of orders and the total count after filtering."""
    page_size = limit if limit is not None else settings.default_page_limit
    if page_size > settings.max_page_limit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"limit must not exceed {settings.max_page_limit}",
        )
    items, total = store.list_orders(
        status=order_status, offset=offset, limit=page_size
    )
    return OrderListResponse(items=items, total=total, offset=offset, limit=page_size)


@router.get(
    "/{order_id}",
    response_model=Order,
    summary="Get one order by id",
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
def get_order(
    store: StoreDep,
    order_id: Annotated[int, Path(ge=1, description="Order id")],
) -> Order:
    """Return an order, or 404 if it does not exist."""
    order = store.get_order(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )
    return order


@router.post(
    "/{order_id}/pay",
    response_model=Order,
    summary="Pay an order",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def pay_order(
    store: StoreDep,
    order_id: Annotated[int, Path(ge=1, description="Order id")],
) -> Order:
    """Move an order from created to paid."""
    try:
        return store.pay_order(order_id)
    except OrderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except InvalidOrderState as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.post(
    "/{order_id}/cancel",
    response_model=Order,
    summary="Cancel an order and return stock",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def cancel_order(
    store: StoreDep,
    order_id: Annotated[int, Path(ge=1, description="Order id")],
) -> Order:
    """Move an order from created to cancelled and restore stock."""
    try:
        return store.cancel_order(order_id)
    except OrderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except InvalidOrderState as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
