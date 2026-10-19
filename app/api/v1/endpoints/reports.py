from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from api.deps import CurrentUser, SessionDep
from models.inventory import Product
from models.order import Order, OrderStatus

router = APIRouter()


class DashboardSummary(BaseModel):
    total_revenue: Decimal
    total_orders: int
    total_products: int
    low_stock_count: int


@router.get("/dashboard", response_model=DashboardSummary)
async def get_dashboard_summary(session: SessionDep, current_user: CurrentUser):
    # total revenue and completed order count
    sales_stmt = select(
        func.coalesce(func.sum(Order.total_amount), Decimal("0.00")),
        func.count(Order.id),
    ).where(Order.status == OrderStatus.COMPLETED)
    sales_result = await session.execute(sales_stmt)
    total_revenue, total_orders = sales_result.one()

    # total active products
    products_stmt = select(func.count(Product.id)).where(Product.is_active == True)
    total_products = (await session.execute(products_stmt)).scalar() or 0

    # low stock products count (stock_quantity <= reorder_level)
    low_stock_stmt = select(func.count(Product.id)).where(
        Product.is_active == True, Product.stock_quantity <= Product.reorder_level
    )
    low_stock_count = (await session.execute(low_stock_stmt)).scalar() or 0

    return DashboardSummary(
        total_revenue=total_revenue,
        total_orders=total_orders,
        total_products=total_products,
        low_stock_count=low_stock_count,
    )
