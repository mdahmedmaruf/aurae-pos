import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.deps import CurrentUser, SessionDep, require_roles
from models.inventory import Product, StockChangeType, StockMovement
from models.order import Order, OrderItem, OrderStatus
from models.user import User, UserRole
from schemas.order import OrderCreate, OrderResponse

router = APIRouter()


def generate_order_number() -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:6].upper()
    return f"ORD-{date_part}-{random_part}"


@router.post(
    "/checkout", response_model=OrderResponse, status_code=status.HTTP_201_CREATED
)
async def process_checkout(
    order_in: OrderCreate, session: SessionDep, current_user: CurrentUser
):
    subtotal_amount = Decimal("0.00")
    order_number = generate_order_number()

    order = Order(
        order_number=order_number,
        cashier_id=current_user.id,
        subtotal_amount=Decimal("0.00"),
        discount_amount=order_in.discount_amount,
        tax_amount=order_in.tax_amount,
        total_amount=Decimal("0.00"),
        payment_method=order_in.payment_method,
        status=OrderStatus.COMPLETED,
    )
    session.add(order)
    await session.flush()

    for item in order_in.items:
        stmt = select(Product).where(Product.id == item.product_id).with_for_update()
        result = await session.execute(stmt)
        product = result.scalar_one_or_none()

        if not product or not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product ID {item.product_id} not found or inactive",
            )

        if product.stock_quantity < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock for {product.name}"
                    f"Available: {product.stock_quantity}, Requested: {item.quantity}"
                ),
            )

        product.stock_quantity -= item.quantity

        line_subtotal = product.selling_price * item.quantity
        subtotal_amount += line_subtotal

        # create OrderItem snapshot
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,
            sku=product.sku,
            unit_price=product.selling_price,
            quantity=item.quantity,
            subtotal=line_subtotal,
        )
        session.add(order_item)

        # record stock movement audit log
        movement = StockMovement(
            product_id=product.id,
            change_type=StockChangeType.SALE,
            quantity=-item.quantity,
            note=f"POS Sale ({order_number})",
            created_by=current_user.id,
        )
        session.add(movement)

    total_amount = subtotal_amount - order_in.discount_amount + order_in.tax_amount
    if total_amount < Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discount amount cannot exceed order subtotal",
        )

    order.subtotal_amount = subtotal_amount
    order.total_amount = total_amount

    await session.commit()

    # reload order with items for response
    stmt = select(Order).options(selectinload(Order.items)).where(Order.id == order.id)
    result = await session.execute(stmt)

    return result.scalar_one()


@router.get("/", response_model=list[OrderResponse])
async def list_orders(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 50
):
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)

    return result.scalars().all()


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, session: SessionDep, current_user: CurrentUser):
    stmt = select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    if order.status == OrderStatus.REFUNDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order has already been refunded",
        )

    for item in order.items:
        prod_result = await session.execute(
            select(Product).where(Product.id == item.product_id).with_for_update()
        )
        product = prod_result.scalar_one_or_none()
        if product:
            product.stock_quantity += item.quantity

            movement = StockMovement(
                product_id=product.id,
                change_type=StockChangeType.RETURN,
                quantity=item.quantity,
                note=f"Refund for Order ({order.order_number})",
                created_by=current_user.id,
            )
            session.add(movement)

        order.status = OrderStatus.REFUNDED
        await session.commit()
        await session.refresh(order)

        return order
