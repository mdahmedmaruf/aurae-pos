from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from api.deps import CurrentUser, SessionDep, require_roles
from models.inventory import Product, StockChangeType, StockMovement
from models.user import User, UserRole
from schemas.inventory import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    StockAdjustmentCreate,
    StockMovementResponse,
)

router = APIRouter()


@router.get("/", response_model=list[ProductResponse])
async def list_products(
    session: SessionDep,
    current_user: CurrentUser,
    search: str | None = Query(None, description="Search by name, SKU, or barcode"),
    category_id: str | None = None,
    low_stock_only: bool = False,
    skip: int = 0,
    limit: int = 50,
):
    stmt = select(Product).options(selectinload(Product.category))

    if search:
        search_filter = f"%{search}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(search_filter),
                Product.sku.ilike(search_filter),
                Product.barcode.ilike(search_filter),
            )
        )

    if category_id:
        stmt = stmt.where(Product.category_id == category_id)

    if low_stock_only:
        stmt = stmt.where(Product.stock_quantity <= Product.reorder_level)

    stmt = stmt.order_by(Product.name).offset(skip).limit(limit)
    result = await session.execute(stmt)

    return result.scalars().all()


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, session: SessionDep, current_user: CurrentUser):
    stmt = (
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product_id)
    )
    result = await session.execute(stmt)
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    return product


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_in: ProductCreate,
    session: SessionDep,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
):
    conditions = [Product.sku == product_in.sku]
    if product_in.barcode:
        conditions.append(Product.barcode == product_in.barcode)

    existing = await session.execute(select(Product).where(or_(*conditions)))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product with this SKU or Barcode already exists",
        )

    data = product_in.model_dump()
    initial_stock = data.pop("initial_stock", 0)

    product = Product(**data, stock_quantity=initial_stock)
    session.add(product)
    await session.flush()

    if initial_stock > 0:
        movement = StockMovement(
            product_id=product.id,
            change_type=StockChangeType.INITIAL,
            quantity=initial_stock,
            note="Initial stock on product creation",
            created_by=current_user.id,
        )
        session.add(movement)

    await session.commit()

    stmt = (
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))],
)
async def update_product(
    product_id: str, product_in: ProductUpdate, session: SessionDep
):
    stmt = (
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product_id)
    )
    result = await session.execute(stmt)
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product is not found"
        )

    for field, value in product_in.model_dump(exclude_unset=True).items():
        setattr(product, field, value)

    await session.commit()
    await session.refresh(product)

    return product


@router.post("/{product_id}/adjust-stock", response_model=ProductResponse)
async def adjust_stock(
    product_id: str,
    adjustment: StockAdjustmentCreate,
    session: SessionDep,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
):
    if adjustment.quantity == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adjustment quantity cannot be zero",
        )

    stmt = (
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product_id)
    )
    result = await session.execute(stmt)
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    new_stock = product.stock_quantity + adjustment.quantity
    if new_stock < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient stock. Current stock is {product.stock_quantity}",
        )
    product.stock_quantity = new_stock

    movement = StockMovement(
        product_id=product.id,
        change_type=adjustment.change_type,
        quantity=adjustment.quantity,
        note=adjustment.note,
        created_by=current_user.id,
    )
    session.add(movement)
    await session.commit()
    await session.refresh(product)

    return product


@router.get("/{product_id}/movements", response_model=list[StockMovementResponse])
async def get_product_stock_movements(
    product_id: str, session: SessionDep, current_user: CurrentUser
):
    stmt = (
        select(StockMovement)
        .where(StockMovement.product_id == product_id)
        .order_by(StockMovement.created_at.desc())
    )
    result = await session.execute(stmt)

    return result.scalars().all()
