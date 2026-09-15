import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/orders_stock",
)


@contextmanager
def get_cursor(commit=False):
    connection = psycopg2.connect(DATABASE_URL)

    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            yield cursor

        if commit:
            connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def init_db():
    with open("schema.sql", "r", encoding="utf-8") as file:
        schema = file.read()

    with get_cursor(commit=True) as cursor:
        cursor.execute(schema)