import time

from app.db import get_cursor


def get_stock(sku):
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT sku, name, stock, price_cents
            FROM products
            WHERE sku = %s
            """,
            (sku,),
        )

        return cursor.fetchone()


def apply_pending_events(batch_size=50):
    applied_count = 0

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            """
            SELECT
                id,
                order_ref,
                sku,
                qty_delta
            FROM stock_events
            WHERE applied = FALSE
            ORDER BY id
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            (batch_size,),
        )

        events = cursor.fetchall()

        for event in events:

            cursor.execute(
                """
                UPDATE products
                SET stock = stock + %s
                WHERE sku = %s
                  AND stock + %s >= 0
                """,
                (
                    event["qty_delta"],
                    event["sku"],
                    event["qty_delta"],
                ),
            )

            if cursor.rowcount != 1:
                raise ValueError(
                    f"Insufficient stock for SKU {event['sku']}"
                )

            cursor.execute(
                """
                UPDATE stock_events
                SET
                    applied = TRUE,
                    applied_at = now()
                WHERE id = %s
                """,
                (event["id"],),
            )

            applied_count += 1

        cursor.connection.commit()

    return applied_count


class StockWorker:

    def run_once(self):
        total = 0

        while True:
            count = apply_pending_events()

            if count == 0:
                break

            total += count

        return total

    def run_forever(self, poll_interval=2):
        print("Stock worker started.")

        while True:
            try:
                count = self.run_once()

                if count:
                    print(
                        f"Applied {count} stock event(s)."
                    )

            except Exception as exc:
                print(
                    f"Worker error: {exc}"
                )

            time.sleep(poll_interval)