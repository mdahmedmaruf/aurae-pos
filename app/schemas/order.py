from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from models.order import OrderStatus, PaymentMethod


class OrderItemCreate(BaseModel):
    product_id: str
    quantity: int = Field(..., gt=0, description="Quantity must be at least 1")


class OrderCreate(BaseModel):
    items: list[OrderItemCreate] = Field(..., min_length=1)
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    payment_method: PaymentMethod = PaymentMethod.CASH


class OrderItemResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    sku: str
    unit_price: Decimal
    quantity: int
    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: str
    order_number: str
    cashier_id: str
    subtotal_amount: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    payment_method: PaymentMethod
    status: OrderStatus
    items: list[OrderItemResponse]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
