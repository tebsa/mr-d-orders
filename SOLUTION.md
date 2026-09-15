# Solution

## 1. Overview

This solution implements a small order and stock flow using Python, FastAPI and PostgreSQL.

The main goals are:

- Accept and persist orders reliably.
- Prevent duplicate orders.
- Calculate and retain the order price at the time of submission.
- Allow orders to be accepted when the stock processing capability is temporarily unavailable.
- Process stock changes after recovery.
- Provide a simple integration surface for accepted orders.
- Keep the implementation small enough to understand and run locally.

The design deliberately avoids unnecessary infrastructure for this exercise.

---

# 2. Requirements Addressed

The implementation addresses the main requirements as follows.

| Requirement | Solution |
|---|---|
| Persist orders | PostgreSQL |
| Prevent duplicate `order_ref` | Primary key on `orders.order_ref` |
| Calculate order total | Product price × quantity at order time |
| Preserve historical price | `order_items.unit_price_cents` |
| Stock stored persistently | PostgreSQL `products` table |
| Stock processing | Database-backed `stock_events` |
| Temporary stock interruption | Pending stock events remain in PostgreSQL |
| Recovery after interruption | Worker processes pending events after restart |
| Integration surface | `order_events` table |
| Accepted order event | `ORDER_ACCEPTED` |
| Automated tests | pytest |

---

# 3. Architecture

The application has three logical components:

### Orders API

Responsible for:

- Receiving order requests
- Validating the request
- Looking up product prices
- Calculating the order total
- Persisting the order
- Creating order items
- Creating stock events
- Creating an `ORDER_ACCEPTED` integration event

### Stock Worker

Responsible for:

- Polling pending stock events
- Updating product stock
- Marking events as applied
- Retrying pending events after temporary failures

### Order Events Consumer

Responsible for:

- Polling the `order_events` integration surface
- Reading accepted-order events
- Demonstrating how another service could consume the events

---

# 4. Architecture

The solution consists of three logical components:

### Orders API

The Orders API is responsible for receiving order requests, validating the input, calculating the order total, and persisting the order-related data.

When an order is accepted, the API creates the order, its items, the corresponding stock event, and the `ORDER_ACCEPTED` integration event within the same database transaction.

### Stock Worker

The Stock Worker processes pending records from `stock_events`. It runs independently of the Orders API and updates product stock when events are available.

Keeping stock processing separate allows the order API to continue accepting orders when the worker is temporarily unavailable.

### Order Events Consumer

The Order Events Consumer reads `ORDER_ACCEPTED` events from the `order_events` table.

It represents a simple integration surface that could be replaced by a message broker or another event delivery mechanism in a larger production system.

### PostgreSQL

PostgreSQL is the durable source of truth for the application.

It stores:

- Products and current stock
- Orders
- Order items
- Pending stock events
- Accepted-order integration events

The database also provides the transaction and constraint mechanisms used to maintain consistency and prevent duplicate orders.

---

# 5. Idempotency and Duplicate Orders

Duplicate submission is one of the main failure cases in the assignment.

For example, a client may send:

    order_ref = ORDER-123

and then retry the same request because of a timeout.

Without idempotency, the system could create two orders and potentially reduce stock twice.

The solution uses PostgreSQL to enforce uniqueness.

The `orders` table defines:

    order_ref TEXT PRIMARY KEY

The application also checks whether the order already exists.

The database constraint is the final protection against concurrent duplicate submissions.

This is important because an application-level "check then insert" by itself can still have a race condition:

    Request A -> check -> not found
    Request B -> check -> not found
    Request A -> insert
    Request B -> insert

The database constraint prevents both inserts from succeeding.

For an existing order reference, the API returns the existing order rather than creating a second order.

---

# 6. Price Calculation

The product table stores the current product price.

When an order is created, the application reads the current price and calculates:

    line_total = quantity × unit_price

The order total is the sum of all line totals.

The price used at the time of the order is stored in:

    order_items.unit_price_cents

This means that a later change to the product price does not change the historical order total.

For example:

    Product price at order time = R100
    Quantity = 2

    Order line total = R200

If the product later changes to R120, the original order still records R100 as the unit price.

---

# 7. Transaction Boundaries

The order creation operation uses one database transaction for the initial order state.

Within the transaction the application creates:

1. The order
2. The order items
3. The stock events
4. The `ORDER_ACCEPTED` event

The transaction is committed only after all of these writes succeed.

If an error occurs, the transaction is rolled back.

This prevents a partially created order.

For example, the system should not end up with:

    orders = created
    order_items = created
    stock_events = missing

because of a failure between the individual writes.

---

# 8. Stock Processing

Stock processing is intentionally asynchronous.

Instead of requiring the API to directly perform all stock processing, the order transaction creates a pending `stock_events` record.

For example:

    order_ref = ORDER-123
    sku = SKU-001
    qty_delta = -2
    applied = false

The Stock Worker later processes the event.

The flow becomes:

    Order API
       |
       v
    stock_events
       |
       v
    Stock Worker
       |
       v
    products.stock

This separates order acceptance from stock event processing.

---

# 9. Temporary Stock Interruption

The Stock Worker is deliberately separated from the Orders API so that temporary stock-processing failures do not prevent an order from being persisted.

During an interruption, the following system behaviour is expected:

| System state | Order processing | Stock processing |
|---|---|---|
| Worker available | Orders are accepted and stock events are created | Pending events are processed |
| Worker unavailable | Orders continue to be persisted | Pending events remain in PostgreSQL |
| Worker restarted | Previously persisted orders remain unchanged | Pending events are processed |
| Processing completed | Orders remain persisted | Corresponding stock events are marked as applied |

The important part of this design is that the stock event is persisted before the order transaction commits. The worker does not need to be available at the time the order is submitted.

When the worker becomes available again, it queries PostgreSQL for unapplied stock events and processes them. This provides the required catch-up behaviour without requiring the order to be submitted again.

The interruption can be demonstrated locally by stopping the worker:

    docker compose stop worker

An order can then be submitted while the worker is stopped. The resulting stock event remains persisted in PostgreSQL.

The worker can subsequently be restarted:

    docker compose start worker

The pending event is then available for processing.

---

# 10. Safe Stock Updates

The worker updates stock using a conditional database update.

The update ensures that stock cannot become negative.

Conceptually:

    UPDATE products
    SET stock = stock + qty_delta
    WHERE sku = ...
      AND stock + qty_delta >= 0

The worker only marks the event as applied after the stock update succeeds.

The stock update and event status update occur in the same database transaction.

Therefore, if processing fails before the transaction commits, the event remains pending and can be retried.

---

# 11. Event Consumer

The event consumer polls the `order_events` table for events with an ID greater than the last event it has processed.

Events are retrieved in ascending ID order.

The consumer currently keeps its `last_event_id` in memory because the assignment only requires a small demonstration of the integration surface.

This is intentionally a minimal implementation. In a production environment, the consumer checkpoint would normally be persisted so that the consumer could resume from its previous position after a restart.

The current consumer therefore demonstrates the integration contract without introducing additional infrastructure such as Kafka.

---

# 12. Order Events Integration Surface

The assignment provides a choice between an integration surface and a report.

This solution uses the integration surface approach.

The `order_events` table acts as a small database-backed event stream.

When an order is accepted, the following event is created:

    event_type = ORDER_ACCEPTED

The event contains:

- Event ID
- Event type
- Order reference
- Customer ID
- Order total
- Creation timestamp

The event is inserted in the same transaction as the order.

This means an `ORDER_ACCEPTED` event cannot be committed for an order that failed to commit.

---

# 13. Event Consumer

The consumer polls the `order_events` table using the event ID.

Conceptually:

    SELECT ...
    FROM order_events
    WHERE id > last_event_id
    ORDER BY id

This provides a simple ordered integration mechanism.

The current implementation keeps `last_event_id` in memory because the purpose is to demonstrate the integration flow with minimal infrastructure.

A production implementation would persist the consumer offset/checkpoint so that the consumer could resume exactly from its previous position after a restart.

---

# 14. Why PostgreSQL Was Used

PostgreSQL is used as the persistent source of truth for:

- Products
- Stock
- Orders
- Order items
- Stock events
- Order events

It provides:

- Transactions
- Unique constraints
- Foreign keys
- Conditional updates
- Durable persistence
- Row-level locking

These capabilities are sufficient for the reliability requirements in this exercise.

---

# 15. Why Kafka Was Not Used

Kafka would be a valid choice for a larger production event-driven architecture, but it would add significant infrastructure for this exercise.

The assignment does not require Kafka.

The database-backed event tables demonstrate the required behaviour while keeping the project:

- Small
- Easy to run locally
- Easy to test
- Easy to explain
- Focused on the core reliability requirements

For a production system with higher event volume and multiple independent consumers, Kafka or another durable messaging platform could be considered.

---

# 16. Why the Stock Worker Is Separate

The Stock Worker is separated from the API process to demonstrate temporary capability unavailability.

If stock processing were performed directly inside the API request, stopping the stock capability would prevent the order from being accepted.

With asynchronous processing:

    API
      |
      v
    Persist order + stock event
      |
      v
    Return response

The worker can then process the stock event independently.

This also makes the worker independently scalable in a larger system.

---

# 17. Failure Scenarios

## Scenario 1: Duplicate Submission

A client submits:

    ORDER-123

The order is created.

The client submits:

    ORDER-123

again.

Expected result:

- No second order
- No duplicate order items
- No duplicate stock event
- No duplicate `ORDER_ACCEPTED` event

The existing order is returned.

---

## Scenario 2: Temporary Stock Interruption

The Stock Worker is stopped.

A new order is submitted.

Expected result:

- Order is persisted
- Stock event is persisted
- API remains available
- Stock event remains pending

The worker is started again.

Expected result:

- Pending event is found
- Stock is updated
- Event is marked as applied

No manual re-submission of the order is required.

---

# 18. Testing

The current automated tests cover the core order behaviour.

### Test 1: Order total

Verifies that the total is calculated correctly using the product price and quantity.

### Test 2: Duplicate order

Verifies that submitting the same `order_ref` does not create a second order.

### Test 3: Unknown SKU

Verifies that an order containing an unknown product is rejected.

### Test 4: Accepted order event

Verifies that creating an order creates an `ORDER_ACCEPTED` event containing the expected order reference, customer and total.

Run the tests with:

    docker compose run --rm api python -m pytest tests/test_orders.py -v

---

# 19. Data Consistency

The design aims to keep the following relationships consistent:

    orders
       |
       +--> order_items
       |
       +--> stock_events
       |
       +--> order_events

Foreign keys are used between related records.

The database is therefore responsible for enforcing important relationships rather than relying only on application code.

---

# 20. API Design

The API intentionally exposes only the endpoints required for the exercise.

### Health

    GET /health

### Create order

    POST /orders

### Get order

    GET /orders/{order_ref}

### Get stock

    GET /stock/{sku}

The API is stateless. Persistent state is stored in PostgreSQL.

---

# 21. Scalability Considerations

The current implementation is intentionally small, but the logical separation allows it to evolve.

Possible future improvements include:

- Running multiple API instances behind a load balancer
- Running multiple stock workers
- Using Kafka or another message broker
- Persisting consumer checkpoints
- Adding authentication and authorisation
- Adding structured logging
- Adding metrics and distributed tracing
- Adding retry/backoff policies
- Adding dead-letter handling
- Adding stronger concurrency tests
- Adding database migrations
- Adding Kubernetes deployment

These were not added because they are outside the minimum scope of the exercise.

---

# 22. Security Considerations

The exercise does not require authentication.

The current implementation therefore does not include user authentication or authorisation.

For production, I would add:

- Authentication
- Authorisation
- Input validation
- Secrets management
- TLS
- Database credentials managed outside source control
- Rate limiting where appropriate
- Audit logging

The `.env` file is excluded from Git through `.gitignore`.

---

# 23. Observability

For a production implementation, the main signals I would monitor include:

- API request rate
- API latency
- API error rate
- Database connection errors
- Pending stock event count
- Stock worker processing rate
- Stock worker failures
- Event consumer lag
- Duplicate order rate

The current implementation keeps observability intentionally lightweight to focus on the assignment's core requirements.

---

# 24. Trade-offs

### Database-backed events vs Kafka

**Chosen:** PostgreSQL event tables.

**Reason:** Lower operational complexity and sufficient for the scale of the exercise.

**Trade-off:** It does not provide the same event-streaming capabilities and scalability as Kafka.

### Asynchronous stock processing

**Chosen:** Background worker.

**Reason:** Allows orders to be accepted while stock processing is temporarily unavailable.

**Trade-off:** Stock updates are eventually consistent rather than necessarily completed before the API responds.

### In-memory consumer offset

**Chosen:** In-memory `last_event_id`.

**Reason:** Keeps the demonstration simple.

**Trade-off:** Restarting the consumer resets its position and can result in events being read again.

### Single PostgreSQL database

**Chosen:** PostgreSQL as the source of truth.

**Reason:** Provides transactions and durable state with minimal infrastructure.

**Trade-off:** A larger production architecture may separate responsibilities across services and datastores.

---

# 25. AI-Assisted Development

AI tools were used during development to assist with implementation and boilerplate code.

The following areas were reviewed and determined as part of the solution design:

- Overall architecture
- Database schema
- Transaction boundaries
- Idempotency approach
- Stock processing approach
- Failure scenarios
- Testing strategy

Generated suggestions were reviewed and adapted before being incorporated into the project.

The final implementation was tested locally using Docker Compose and pytest.

---

# 26. Final Design Summary

The solution is designed around a small number of reliability and consistency principles.

### Durable persistence

PostgreSQL is the source of truth for orders, order items, products, stock events, and order events. Important application state is therefore not dependent on in-memory data.

### Idempotent order submission

The `order_ref` is used as the primary key for orders. This provides database-level protection against duplicate submissions and ensures that the same order is not created more than once.

### Transactional order creation

Order data, stock events, and the `ORDER_ACCEPTED` integration event are created within the same database transaction. The transaction either commits the complete set of related records or rolls back.

### Asynchronous stock processing

Stock changes are represented as durable pending events and processed independently by the Stock Worker. This allows order acceptance to continue when the worker is temporarily unavailable.

### Recovery after interruption

Pending stock events remain in PostgreSQL while the Stock Worker is unavailable. When the worker is restarted, it processes the outstanding events and marks them as applied after successful processing.

### Simple integration surface

The `order_events` table provides a lightweight integration mechanism for accepted orders. A separate consumer demonstrates how another component can consume these events without introducing additional infrastructure.

### Focused implementation

The solution intentionally uses PostgreSQL, a small background worker, and a simple event consumer rather than introducing additional infrastructure such as Kafka or Kubernetes. This keeps the implementation focused on the reliability requirements of the assignment while leaving clear paths for future evolution.

The key reliability decisions are:

1. PostgreSQL provides durable state.
2. `order_ref` provides database-enforced idempotency.
3. Product prices are captured at order time.
4. Stock processing is asynchronous.
5. Pending stock events survive worker interruption.
6. Stock updates and event completion are transactional.
7. Accepted-order events are persisted with the order.
8. The architecture remains small and locally reproducible.