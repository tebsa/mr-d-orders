from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from app.orders import OrderRejected, create_order, get_order
from app.stock import get_stock


app = FastAPI(
    title="Orders & Stock API",
    version="1.0.0",
)


class OrderItem(BaseModel):
    sku: str
    qty: int = Field(gt=0)


class CreateOrderRequest(BaseModel):
    order_ref: str
    customer_id: str
    items: list[OrderItem]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/orders")
def create_order_endpoint(request: CreateOrderRequest):

    items = [
        {
            "sku": item.sku,
            "qty": item.qty,
        }
        for item in request.items
    ]

    try:
        order, was_created = create_order(
            order_ref=request.order_ref,
            customer_id=request.customer_id,
            items=items,
        )

    except OrderRejected as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    response = {
        "order": order,
        "created": was_created,
    }

    return response


@app.get("/orders/{order_ref}")
def get_order_endpoint(order_ref: str):

    order = get_order(order_ref)

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return order


@app.get("/stock/{sku}")
def get_stock_endpoint(sku: str):

    stock = get_stock(sku)

    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SKU not found",
        )

    return stock