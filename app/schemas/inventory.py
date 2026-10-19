from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from models.inventory import StockChangeType


# Category Schemas
class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: str | None = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = None


class CategoryResponse(CategoryBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Product Schemas
class ProductBase(BaseModel):
    sku: str = Field(..., min_length=2, max_length=50)
    barcode: str | None = Field(None, max_length=100)
    name: str = Field(..., min_length=2, max_length=200)
    description: str | None = None
    category_id: str | None = None
    cost_price: Decimal = Field(..., ge=0)
    selling_price: Decimal = Field(..., ge=0)
    reorder_level: int = Field(default=10, ge=0)
    is_active: bool = True


class ProductCreate(ProductBase):
    initial_stock: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    sku: str | None = Field(None, min_length=2, max_length=50)
    barcode: str | None = Field(None, max_length=100)
    name: str | None = Field(None, min_length=2, max_length=200)
    description: str | None = None
    category_id: str | None = None
    cost_price: Decimal | None = Field(None, ge=0)
    selling_price: Decimal | None = Field(None, ge=0)
    reorder_level: int | None = Field(None, ge=0)
    is_active: bool | None = None


class ProductResponse(ProductBase):
    id: str
    stock_quantity: int
    category: CategoryResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Stock Adjustment Schemas
class StockAdjustmentCreate(BaseModel):
    change_type: StockChangeType
    quantity: int = Field(
        ...,
        description="Positive to add stock (e.g. 10), negative to deduct stock (e.g. -5)",
    )
    note: str | None = Field(None, max_length=255)


class StockMovementResponse(BaseModel):
    id: str
    product_id: str
    change_type: StockChangeType
    quantity: int
    note: str | None
    created_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
