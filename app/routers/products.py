"""Catalog endpoints: list products and read a single product."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.deps import SettingsDep, StoreDep
from app.models import ErrorResponse, Product, ProductListResponse

router = APIRouter(prefix="/products", tags=["products"])


@router.get(
    "",
    response_model=ProductListResponse,
    summary="List products with pagination and optional category filter",
)
def list_products(
    store: StoreDep,
    settings: SettingsDep,
    category: Annotated[
        str | None, Query(min_length=1, max_length=100, description="Exact category")
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Items to skip")] = 0,
    limit: Annotated[
        int | None, Query(ge=1, description="Page size, defaults to DEFAULT_PAGE_LIMIT")
    ] = None,
) -> ProductListResponse:
    """Return a page of the catalog and the total count after filtering."""
    page_size = limit if limit is not None else settings.default_page_limit
    if page_size > settings.max_page_limit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"limit must not exceed {settings.max_page_limit}",
        )
    items, total = store.list_products(
        category=category, offset=offset, limit=page_size
    )
    return ProductListResponse(items=items, total=total, offset=offset, limit=page_size)


@router.get(
    "/{product_id}",
    response_model=Product,
    summary="Get one product by id",
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
def get_product(
    store: StoreDep,
    product_id: Annotated[int, Path(ge=1, description="Product id")],
) -> Product:
    """Return a product, or 404 if it does not exist."""
    product = store.get_product(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    return product
