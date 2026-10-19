# aurae-pos/app/seed.py
import asyncio
from decimal import Decimal

from sqlalchemy import select

from core.database import AsyncSessionLocal, engine
from core.security import get_password_hash
from models import (
    Base,
    Category,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    Product,
    StockChangeType,
    StockMovement,
    User,
    UserRole,
)


async def seed_data():
    # Ensure all tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check if database is already seeded
        existing_user = await session.execute(
            select(User).where(User.email == "admin@auraepos.com")
        )
        if existing_user.scalar_one_or_none():
            print("⚡ Database already contains demo data. Skipping seed.")
            return

        print("🌱 Seeding demo data into Aurae POS...")

        # 1. Seed Users
        admin = User(
            email="admin@auraepos.com",
            full_name="Maruf Ahmed (Admin)",
            hashed_password=get_password_hash("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        manager = User(
            email="manager@auraepos.com",
            full_name="Store Manager",
            hashed_password=get_password_hash("manager123"),
            role=UserRole.MANAGER,
            is_active=True,
        )
        cashier = User(
            email="cashier@auraepos.com",
            full_name="Front Desk Cashier",
            hashed_password=get_password_hash("cashier123"),
            role=UserRole.CASHIER,
            is_active=True,
        )
        session.add_all([admin, manager, cashier])
        await session.flush()

        # 2. Seed Categories
        categories_data = [
            ("Beverages", "Coffee, tea, soft drinks, and juices"),
            ("Bakery & Snacks", "Fresh pastries, chips, and biscuits"),
            ("Dairy & Groceries", "Milk, eggs, cooking essentials"),
            ("Personal Care", "Daily hygiene and skincare items"),
            ("Accessories", "Phone chargers, cables, and batteries"),
        ]
        categories: dict[str, Category] = {}
        for name, desc in categories_data:
            cat = Category(name=name, description=desc)
            session.add(cat)
            categories[name] = cat
        await session.flush()

        # 3. Seed Products
        products_data = [
            {
                "sku": "BEV-001",
                "barcode": "890100000001",
                "name": "Iced Caramel Latte (350ml)",
                "category": categories["Beverages"],
                "cost_price": Decimal("120.00"),
                "selling_price": Decimal("220.00"),
                "stock_quantity": 45,
                "reorder_level": 10,
            },
            {
                "sku": "BEV-002",
                "barcode": "890100000002",
                "name": "Organic Green Tea (25 Bags)",
                "category": categories["Beverages"],
                "cost_price": Decimal("180.00"),
                "selling_price": Decimal("260.00"),
                "stock_quantity": 30,
                "reorder_level": 8,
            },
            {
                "sku": "BEV-003",
                "barcode": "890100000003",
                "name": "Sparkling Mineral Water (500ml)",
                "category": categories["Beverages"],
                "cost_price": Decimal("25.00"),
                "selling_price": Decimal("40.00"),
                "stock_quantity": 100,
                "reorder_level": 20,
            },
            {
                "sku": "SNK-001",
                "barcode": "890100000004",
                "name": "Butter Croissant",
                "category": categories["Bakery & Snacks"],
                "cost_price": Decimal("75.00"),
                "selling_price": Decimal("140.00"),
                "stock_quantity": 6,  # Low stock item (<= reorder_level 10)
                "reorder_level": 10,
            },
            {
                "sku": "SNK-002",
                "barcode": "890100000005",
                "name": "Sea Salt Potato Chips (150g)",
                "category": categories["Bakery & Snacks"],
                "cost_price": Decimal("60.00"),
                "selling_price": Decimal("95.00"),
                "stock_quantity": 60,
                "reorder_level": 15,
            },
            {
                "sku": "SNK-003",
                "barcode": "890100000006",
                "name": "Dark Chocolate Bar (70% Cocoa)",
                "category": categories["Bakery & Snacks"],
                "cost_price": Decimal("150.00"),
                "selling_price": Decimal("240.00"),
                "stock_quantity": 25,
                "reorder_level": 8,
            },
            {
                "sku": "GRC-001",
                "barcode": "890100000007",
                "name": "Full Cream Milk (1 Liter)",
                "category": categories["Dairy & Groceries"],
                "cost_price": Decimal("85.00"),
                "selling_price": Decimal("110.00"),
                "stock_quantity": 40,
                "reorder_level": 12,
            },
            {
                "sku": "GRC-002",
                "barcode": "890100000008",
                "name": "Free Range Brown Eggs (12 Pack)",
                "category": categories["Dairy & Groceries"],
                "cost_price": Decimal("145.00"),
                "selling_price": Decimal("180.00"),
                "stock_quantity": 5,  # Low stock item (<= reorder_level 10)
                "reorder_level": 10,
            },
            {
                "sku": "PRC-001",
                "barcode": "890100000009",
                "name": "Antibacterial Hand Wash (250ml)",
                "category": categories["Personal Care"],
                "cost_price": Decimal("110.00"),
                "selling_price": Decimal("165.00"),
                "stock_quantity": 35,
                "reorder_level": 10,
            },
            {
                "sku": "ACC-001",
                "barcode": "890100000010",
                "name": "USB-C Fast Charging Cable (1m)",
                "category": categories["Accessories"],
                "cost_price": Decimal("220.00"),
                "selling_price": Decimal("390.00"),
                "stock_quantity": 20,
                "reorder_level": 5,
            },
        ]

        products: list[Product] = []
        for p_data in products_data:
            cat = p_data.pop("category")
            product = Product(**p_data, category_id=cat.id)
            session.add(product)
            products.append(product)

        await session.flush()

        # Log Initial Stock Movements
        for product in products:
            movement = StockMovement(
                product_id=product.id,
                change_type=StockChangeType.INITIAL,
                quantity=product.stock_quantity,
                note="Initial demo inventory seed",
                created_by=admin.id,
            )
            session.add(movement)

        # 4. Seed Sample Completed Orders
        # Sample Order 1: 2x Iced Caramel Latte + 1x Butter Croissant
        latte = products[0]
        croissant = products[3]

        order1_subtotal = (latte.selling_price * 2) + (croissant.selling_price * 1)
        order1 = Order(
            order_number="ORD-20261018-DEMO01",
            cashier_id=cashier.id,
            subtotal_amount=order1_subtotal,
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=order1_subtotal,
            payment_method=PaymentMethod.CASH,
            status=OrderStatus.COMPLETED,
        )
        session.add(order1)
        await session.flush()

        session.add_all(
            [
                OrderItem(
                    order_id=order1.id,
                    product_id=latte.id,
                    product_name=latte.name,
                    sku=latte.sku,
                    unit_price=latte.selling_price,
                    quantity=2,
                    subtotal=latte.selling_price * 2,
                ),
                OrderItem(
                    order_id=order1.id,
                    product_id=croissant.id,
                    product_name=croissant.name,
                    sku=croissant.sku,
                    unit_price=croissant.selling_price,
                    quantity=1,
                    subtotal=croissant.selling_price * 1,
                ),
            ]
        )

        # Sample Order 2: 1x USB-C Cable + 2x Sparkling Water (Paid via Card with 20 discount)
        cable = products[9]
        water = products[2]
        order2_subtotal = (cable.selling_price * 1) + (water.selling_price * 2)
        order2_discount = Decimal("20.00")

        order2 = Order(
            order_number="ORD-20261018-DEMO02",
            cashier_id=cashier.id,
            subtotal_amount=order2_subtotal,
            discount_amount=order2_discount,
            tax_amount=Decimal("0.00"),
            total_amount=order2_subtotal - order2_discount,
            payment_method=PaymentMethod.CARD,
            status=OrderStatus.COMPLETED,
        )
        session.add(order2)
        await session.flush()

        session.add_all(
            [
                OrderItem(
                    order_id=order2.id,
                    product_id=cable.id,
                    product_name=cable.name,
                    sku=cable.sku,
                    unit_price=cable.selling_price,
                    quantity=1,
                    subtotal=cable.selling_price * 1,
                ),
                OrderItem(
                    order_id=order2.id,
                    product_id=water.id,
                    product_name=water.name,
                    sku=water.sku,
                    unit_price=water.selling_price,
                    quantity=2,
                    subtotal=water.selling_price * 2,
                ),
            ]
        )

        await session.commit()
        print("✅ Demo data seeded successfully!")
        print("\n🔑 Demo Login Credentials:")
        print("   Admin   -> Email: admin@auraepos.com   | Password: admin123")
        print("   Manager -> Email: manager@auraepos.com | Password: manager123")
        print("   Cashier -> Email: cashier@auraepos.com | Password: cashier123")


if __name__ == "__main__":
    asyncio.run(seed_data())
