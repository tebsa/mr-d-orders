import time

from app.db import get_cursor


def get_new_events(last_event_id):
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                event_type,
                order_ref,
                customer_id,
                total_cents,
                created_at
            FROM order_events
            WHERE id > %s
            ORDER BY id
            """,
            (last_event_id,),
        )

        return cursor.fetchall()


def run():
    last_event_id = 0

    print("Order events consumer started.")

    while True:
        events = get_new_events(last_event_id)

        for event in events:
            print(
                "ORDER_ACCEPTED "
                f"order_ref={event['order_ref']} "
                f"customer_id={event['customer_id']} "
                f"total_cents={event['total_cents']}"
            )

            last_event_id = event["id"]

        time.sleep(2)


if __name__ == "__main__":
    run()