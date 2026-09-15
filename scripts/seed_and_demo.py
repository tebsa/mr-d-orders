import time

import requests


BASE_URL = "http://localhost:8000"


def seed_products():
    products = [
        {
            "sku": "BURGER-001",
            "name": "Chicken Burger",
            "price_cents": 8500,
            "stock": 20,
        },
        {
            "sku": "PIZZA-001",
            "name": "Margherita Pizza",
            "price_cents": 12000,
            "stock": 15,
        },
        {
            "sku": "DRINK-001",
            "name": "Soft Drink",
            "price_cents": 2500,
            "stock": 30,
        },
    ]

    # Products are seeded directly through PostgreSQL.
    # This keeps the demo script simple.
    from app.db import get_cursor

    with get_cursor(commit=False) as cursor:
        for product in products:
            cursor.execute(
                """
                INSERT INTO products (
                    sku,
                    name,
                    price_cents,
                    stock
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (sku)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    price_cents = EXCLUDED.price_cents
                """,
                (
                    product["sku"],
                    product["name"],
                    product["price_cents"],
                    product["stock"],
                ),
            )

        cursor.connection.commit()


def create_order(order_ref):
    response = requests.post(
        f"{BASE_URL}/orders",
        json={
            "order_ref": order_ref,
            "customer_id": "customer-001",
            "items": [
                {
                    "sku": "BURGER-001",
                    "qty": 2,
                },
                {
                    "sku": "DRINK-001",
                    "qty": 1,
                },
            ],
        },
        timeout=5,
    )

    print(
        response.status_code,
        response.json(),
    )


def main():
    print("Seeding products...")
    seed_products()

    print("\nWaiting for API...")
    time.sleep(2)

    print("\n--- Duplicate order demo ---")

    create_order("ORDER-1001")
    create_order("ORDER-1001")
    create_order("ORDER-1001")

    print("\nThe same order_ref was submitted three times.")


if __name__ == "__main__":
    main()