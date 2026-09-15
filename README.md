# Orders & Stock Core Flow

A small Python and PostgreSQL implementation of an order and stock flow.

The project demonstrates how to build a reliable order flow that can handle:

- Duplicate order submissions
- Temporary unavailability of the stock capability
- Persistent state in PostgreSQL
- Asynchronous stock processing
- Event-driven integration through a database-backed event surface
- Safe recovery after a worker interruption
- Basic automated testing

The implementation intentionally keeps the architecture small and easy to run locally.

---

## 1. Architecture

The application consists of three logical components:

1. **Orders API**
   - Accepts and retrieves orders.
   - Calculates the order total using product prices at order time.
   - Prevents duplicate `order_ref` submissions.
   - Creates durable stock and integration events.

2. **Stock Worker**
   - Polls pending stock events from PostgreSQL.
   - Applies stock changes asynchronously.
   - Can be stopped and restarted without losing pending work.

3. **Order Events Consumer**
   - Polls the `order_events` table.
   - Represents a simple integration surface for another service.
   - Consumes `ORDER_ACCEPTED` events and prints them to the console.

The order, order items, stock event and order event are created as part of the same database transaction.

---

## 2. Technology Stack

- Python 3.12
- FastAPI
- PostgreSQL 16
- psycopg2
- Docker
- Docker Compose
- pytest
- httpx
- requests

---

## 3. Project Structure

    mr-d-orders/
    ├── app/
    │   ├── __init__.py
    │   ├── db.py
    │   ├── orders.py
    │   ├── stock.py
    │   └── api.py
    ├── scripts/
    │   ├── __init__.py
    │   ├── seed_and_demo.py
    │   └── events_consumer.py
    ├── tests/
    │   └── test_orders.py
    ├── cli.py
    ├── schema.sql
    ├── requirements.txt
    ├── Dockerfile
    ├── docker-compose.yml
    ├── .env.example
    ├── .gitignore
    ├── README.md
    └── SOLUTION.md

---

## 4. Running the Application

### Prerequisites

The easiest way to run the project is with:

- Docker
- Docker Compose

The project was developed and tested using Docker on Linux/WSL2.

No local PostgreSQL installation is required.

---

## 5. Start the Services

From the project root:

    docker compose up -d

This starts:

- PostgreSQL
- Orders API
- Stock Worker

Check the service status:

    docker compose ps

The PostgreSQL service should report as healthy.

---

## 6. API

The API is available at:

    http://localhost:8000

FastAPI's interactive documentation is available at:

    http://localhost:8000/docs

### Health check

    curl http://localhost:8000/health

Expected response:

    {
      "status": "ok"
    }

---

## 7. Products and Demo Data

Products are stored in the PostgreSQL `products` table.

The demo seed script can be used to create the products and demonstrate the order flow.

Run:

    docker compose run --rm api python -m scripts.seed_and_demo

The seed/demo script is intended to make the demonstration repeatable rather than requiring products and orders to be entered manually.

---

## 8. Creating an Order

Example:

    curl -X POST http://localhost:8000/orders \
      -H "Content-Type: application/json" \
      -d '{
        "order_ref": "DEMO-001",
        "customer_id": "customer-1",
        "items": [
          {
            "sku": "SKU-001",
            "qty": 2
          }
        ]
      }'

The API creates the order and records the corresponding events.

The order total is calculated using the current product price when the order is created.

The price is also stored against the order item so that the order retains the price that was used at the time of submission.

---

## 9. Retrieving an Order

    curl http://localhost:8000/orders/DEMO-001

The response includes the order details and its items.

---

## 10. Checking Stock

    curl http://localhost:8000/stock/SKU-001

The response contains the product and current stock level.

---

## 11. Duplicate Order Handling

The same `order_ref` can be submitted more than once.

The database uses `order_ref` as the primary key of the `orders` table.

This provides a durable uniqueness constraint and prevents the same order from being created twice.

The API returns the existing order when the same `order_ref` is submitted again.

This means duplicate submissions do not result in:

- A second order
- A second set of order items
- A second stock event
- A second `ORDER_ACCEPTED` event

The behaviour is covered by an automated test.

---

## 12. Stock Processing

Stock changes are not dependent on the API directly updating the product stock.

When an order is accepted, a pending record is added to `stock_events`.

The Stock Worker continuously polls this table.

The flow is:

    Order accepted
         |
         v
    stock_events
         |
         v
    Stock Worker
         |
         v
    products.stock

This allows the order flow to continue even if the stock worker is temporarily unavailable.

---

## 13. Simulating a Stock Interruption

The Stock Worker runs as a separate Docker Compose service.

To simulate a temporary interruption:

    docker compose stop worker

Orders can still be submitted while the worker is stopped.

The stock event remains persisted in PostgreSQL.

Start the worker again:

    docker compose start worker

The worker finds the pending event and applies the stock change.

This demonstrates the catch-up behaviour after a temporary interruption.

---

## 14. Order Events Integration Surface

The project includes a small database-backed integration surface through the `order_events` table.

When an order is accepted, an `ORDER_ACCEPTED` event is created.

The event contains:

- Event type
- Order reference
- Customer ID
- Order total
- Creation timestamp

The event is written in the same transaction as the order.

This means an accepted order and its integration event cannot be committed independently.

---

## 15. Running the Event Consumer

Run:

    docker compose run --rm api python -m scripts.events_consumer

The consumer will start and wait for new events.

Example output:

    Order events consumer started.

When an order is submitted, the consumer prints:

    ORDER_ACCEPTED order_ref=DEMO-001 customer_id=customer-1 total_cents=2000

The consumer uses the event ID to process events in order.

The current implementation keeps its last event ID in memory because this is a small demonstration. A production implementation would persist the consumer checkpoint/offset.

---

## 16. Running Tests

Run all tests with:

    docker compose run --rm api python -m pytest tests/test_orders.py -v

The test suite covers:

1. Order total calculation
2. Duplicate order handling
3. Unknown SKU rejection
4. Creation of an `ORDER_ACCEPTED` event

Expected result:

    4 passed

---

## 17. Database

The application uses PostgreSQL as the source of truth.

The main tables are:

### products

Stores:

- SKU
- Product name
- Current price
- Current stock

### orders

Stores:

- Order reference
- Customer
- Total
- Status
- Creation timestamp

`order_ref` is the primary key.

### order_items

Stores:

- Order
- SKU
- Quantity
- Unit price at order time

### stock_events

Stores pending stock changes.

The worker marks events as applied after successfully updating stock.

### order_events

Stores integration events such as:

    ORDER_ACCEPTED

---

## 18. Resetting the Development Database

PostgreSQL data is stored in a Docker volume.

To completely reset the development database:

    docker compose down -v

Then start the application again:

    docker compose up -d

This recreates the database and applies `schema.sql` from the beginning.

---

## 19. Design Principles

The implementation focuses on:

- Durable state rather than in-memory state
- Database-enforced uniqueness
- Transactional writes
- Idempotent order submission
- Asynchronous processing
- Safe worker restart
- Simple failure recovery
- Small, independently understandable components

The implementation deliberately avoids introducing Kafka, Redis or Kubernetes because they are not required to demonstrate the requested behaviour.

---

## 20. AI-Assisted Development

AI tools were used during development for implementation assistance, including boilerplate and code suggestions.

The architecture, database design, transaction boundaries, failure-handling approach and testing strategy were reviewed and adapted for the requirements of the assignment.

All generated code was reviewed and tested locally.

---

## 21. Demo Scenario

A recommended demonstration sequence is:

1. Start the application.
2. Seed the products.
3. Check the initial stock.
4. Start the event consumer.
5. Submit an order.
6. Show the order response.
7. Show the `ORDER_ACCEPTED` event in the consumer.
8. Show the stock reduction.
9. Submit the same order reference again.
10. Show that a duplicate order is not created.
11. Stop the stock worker.
12. Submit another order.
13. Show that the order is persisted while stock processing is interrupted.
14. Start the worker again.
15. Show that the pending stock event is processed.
16. Run the automated tests.

This demonstrates both required unhappy paths:

- Duplicate submission
- Temporary stock interruption followed by recovery