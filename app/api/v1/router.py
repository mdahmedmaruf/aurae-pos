from fastapi import APIRouter

from api.v1.endpoints import auth, categories, orders, products, reports

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])
api_router.include_router(products.router, prefix="/products", tags=["Product & Stock"])
api_router.include_router(
    orders.router, prefix="/orders", tags=["POS Order & Checkout"]
)
api_router.include_router(
    reports.router, prefix="/reports", tags=["Reports & Analytics"]
)
