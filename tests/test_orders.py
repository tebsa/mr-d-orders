import uuid

import pytest

from app.db import get_cursor, init_db
from app.orders import OrderRejected, create_order, get_order


@pytest.fixture(autouse=True)
def clean_database():
    init_db()

    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            TRUNCATE TABLE
                order_events,
                stock_events,
                order_items,
                orders,
                products
            RESTART IDENTITY CASCADE
            """
        )

        cursor.execute(
            """
            INSERT INTO products (
                sku,
                name,
                price_cents,
                stock
            )
            VALUES
                ('SKU-001', 'Test Product', 1000, 10)
            """
        )


def test_create_order_calculates_total():
    order_ref = f"TEST-{uuid.uuid4()}"

    order, created = create_order(
        order_ref=order_ref,
        customer_id="customer-1",
        items=[
            {
                "sku": "SKU-001",
                "qty": 2,
            }
        ],
    )

    assert created is True
    assert order["total_cents"] == 2000


def test_duplicate_order_is_not_created_twice():
    order_ref = f"TEST-{uuid.uuid4()}"

    first, created_first = create_order(
        order_ref=order_ref,
        customer_id="customer-1",
        items=[
            {
                "sku": "SKU-001",
                "qty": 1,
            }
        ],
    )

    second, created_second = create_order(
        order_ref=order_ref,
        customer_id="customer-1",
        items=[
            {
                "sku": "SKU-001",
                "qty": 1,
            }
        ],
    )

    assert created_first is True
    assert created_second is False

    assert first["order_ref"] == second["order_ref"]

    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM orders
            WHERE order_ref = %s
            """,
            (order_ref,),
        )

        result = cursor.fetchone()

    assert result["count"] == 1

def test_unknown_sku_is_rejected():
    order_ref = f"TEST-{uuid.uuid4()}"

    with pytest.raises(OrderRejected):
        create_order(
            order_ref=order_ref,
            customer_id="customer-1",
            items=[
                {
                    "sku": "DOES-NOT-EXIST",
                    "qty": 1,
                }
            ],
        )

def test_order_creates_order_accepted_event():
    order_ref = f"TEST-{uuid.uuid4()}"

    create_order(
        order_ref=order_ref,
        customer_id="customer-1",
        items=[
            {
                "sku": "SKU-001",
                "qty": 2,
            }
        ],
    )

    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                event_type,
                order_ref,
                customer_id,
                total_cents
            FROM order_events
            WHERE order_ref = %s
            """,
            (order_ref,),
        )

        event = cursor.fetchone()

    assert event["event_type"] == "ORDER_ACCEPTED"
    assert event["order_ref"] == order_ref
    assert event["customer_id"] == "customer-1"
    assert event["total_cents"] == 2000