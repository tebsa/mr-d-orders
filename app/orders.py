from psycopg2.errors import UniqueViolation

from app.db import get_cursor


class OrderRejected(Exception):
    pass


def get_order(order_ref):
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                order_ref,
                customer_id,
                total_cents,
                status,
                created_at
            FROM orders
            WHERE order_ref = %s
            """,
            (order_ref,),
        )

        order = cursor.fetchone()

        if order is None:
            return None

        cursor.execute(
            """
            SELECT
                sku,
                qty,
                unit_price_cents
            FROM order_items
            WHERE order_ref = %s
            ORDER BY id
            """,
            (order_ref,),
        )

        order["items"] = cursor.fetchall()

        return order


def create_order(order_ref, customer_id, items):
    if not items:
        raise OrderRejected("Order must contain at least one item.")

    # Fast path for an obvious duplicate.
    existing_order = get_order(order_ref)

    if existing_order:
        return existing_order, False

    try:
        with get_cursor(commit=False) as cursor:

            prices = {}

            for item in items:
                sku = item["sku"]
                qty = item["qty"]

                if qty <= 0:
                    raise OrderRejected(
                        f"Quantity for {sku} must be greater than zero."
                    )

                cursor.execute(
                    """
                    SELECT price_cents
                    FROM products
                    WHERE sku = %s
                    """,
                    (sku,),
                )

                product = cursor.fetchone()

                if product is None:
                    raise OrderRejected(
                        f"Unknown SKU: {sku}"
                    )

                prices[sku] = product["price_cents"]

            total_cents = sum(
                item["qty"] * prices[item["sku"]]
                for item in items
            )

            try:
                cursor.execute(
                    """
                    INSERT INTO orders (
                        order_ref,
                        customer_id,
                        total_cents
                    )
                    VALUES (%s, %s, %s)
                    """,
                    (
                        order_ref,
                        customer_id,
                        total_cents,
                    ),
                )

            except UniqueViolation:
                cursor.connection.rollback()

                return get_order(order_ref), False

            for item in items:
                sku = item["sku"]
                qty = item["qty"]

                cursor.execute(
                    """
                    INSERT INTO order_items (
                        order_ref,
                        sku,
                        qty,
                        unit_price_cents
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        order_ref,
                        sku,
                        qty,
                        prices[sku],
                    ),
                )

                cursor.execute(
                    """
                    INSERT INTO stock_events (
                        order_ref,
                        sku,
                        qty_delta
                    )
                    VALUES (%s, %s, %s)
                    """,
                    (
                        order_ref,
                        sku,
                        -qty,
                    ),
                )

            cursor.execute(
                """
                INSERT INTO order_events (event_type,
                                          order_ref,
                                          customer_id,
                                          total_cents)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    "ORDER_ACCEPTED",
                    order_ref,
                    customer_id,
                    total_cents,
                ),
            )

            cursor.connection.commit()

    except OrderRejected:
        raise

    return get_order(order_ref), True