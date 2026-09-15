import argparse
import json

from app.db import init_db
from app.orders import OrderRejected, create_order, get_order
from app.stock import StockWorker, get_stock


def create_order_command(args):
    items = []

    for item in args.item:
        sku, qty = item.split(":", 1)

        items.append(
            {
                "sku": sku,
                "qty": int(qty),
            }
        )

    try:
        order, created = create_order(
            order_ref=args.order_ref,
            customer_id=args.customer,
            items=items,
        )

    except OrderRejected as exc:
        print(f"Order rejected: {exc}")
        raise SystemExit(1)

    print(
        json.dumps(
            {
                "created": created,
                "order": order,
            },
            default=str,
            indent=2,
        )
    )


def get_order_command(args):
    order = get_order(args.order_ref)

    if order is None:
        print("Order not found.")
        raise SystemExit(1)

    print(
        json.dumps(
            order,
            default=str,
            indent=2,
        )
    )


def get_stock_command(args):
    stock = get_stock(args.sku)

    if stock is None:
        print("SKU not found.")
        raise SystemExit(1)

    print(
        json.dumps(
            stock,
            default=str,
            indent=2,
        )
    )


def run_worker_command(args):
    worker = StockWorker()
    worker.run_forever()


def main():
    parser = argparse.ArgumentParser(
        description="Orders & Stock CLI"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    init_parser = subparsers.add_parser("init-db")
    init_parser.set_defaults(
        func=lambda args: init_db()
    )

    create_parser = subparsers.add_parser(
        "create-order"
    )

    create_parser.add_argument(
        "--order-ref",
        required=True,
    )

    create_parser.add_argument(
        "--customer",
        required=True,
    )

    create_parser.add_argument(
        "--item",
        action="append",
        required=True,
        help="SKU:quantity",
    )

    create_parser.set_defaults(
        func=create_order_command
    )

    get_order_parser = subparsers.add_parser(
        "get-order"
    )

    get_order_parser.add_argument(
        "--order-ref",
        required=True,
    )

    get_order_parser.set_defaults(
        func=get_order_command
    )

    get_stock_parser = subparsers.add_parser(
        "get-stock"
    )

    get_stock_parser.add_argument(
        "--sku",
        required=True,
    )

    get_stock_parser.set_defaults(
        func=get_stock_command
    )

    worker_parser = subparsers.add_parser(
        "run-worker"
    )

    worker_parser.set_defaults(
        func=run_worker_command
    )

    args = parser.parse_args()

    args.func(args)


if __name__ == "__main__":
    main()