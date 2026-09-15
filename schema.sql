CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    stock INTEGER NOT NULL CHECK (stock >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    order_ref TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
    status TEXT NOT NULL DEFAULT 'accepted',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_ref TEXT NOT NULL REFERENCES orders(order_ref),
    sku TEXT NOT NULL REFERENCES products(sku),
    qty INTEGER NOT NULL CHECK (qty > 0),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0)
);

CREATE TABLE IF NOT EXISTS stock_events (
    id SERIAL PRIMARY KEY,
    order_ref TEXT NOT NULL REFERENCES orders(order_ref),
    sku TEXT NOT NULL REFERENCES products(sku),
    qty_delta INTEGER NOT NULL,
    applied BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_stock_events_pending
ON stock_events (id)
WHERE applied = FALSE;

CREATE TABLE IF NOT EXISTS order_events (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    order_ref TEXT NOT NULL REFERENCES orders(order_ref),
    customer_id TEXT NOT NULL,
    total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_order_events_id
ON order_events (id);