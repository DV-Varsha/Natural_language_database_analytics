"""
Database Module for Natural Language Database Analytics Agent.

Handles SQLite connection, schema definition, sample sales data seeding,
metadata extraction for LLM prompts, and safe query execution.
"""

from __future__ import annotations

import os
import random
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple
import pandas as pd

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sales.db")


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create and return a connection to the SQLite database."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH, force: bool = False) -> str:
    """
    Initialize SQLite database with normalized sales tables and seed sample records.
    If database already exists and force is False, initialization is skipped.
    """
    if os.path.exists(db_path) and not force:
        # Check if tables exist and have data
        try:
            with get_db_connection(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='orders';")
                if cursor.fetchone()[0] > 0:
                    cursor.execute("SELECT COUNT(*) FROM orders;")
                    if cursor.fetchone()[0] > 0:
                        return f"Database already initialized at: {db_path}"
        except Exception:
            pass  # Recreate if corrupt

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    if os.path.exists(db_path) and force:
        try:
            os.remove(db_path)
        except Exception:
            pass

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Create Normalized Relational Schema
    cursor.executescript("""
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS categories;
        DROP TABLE IF EXISTS customers;

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            region TEXT NOT NULL,
            segment TEXT NOT NULL,
            signup_date DATE NOT NULL
        );

        CREATE TABLE categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT NOT NULL UNIQUE,
            description TEXT
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            cost_price REAL NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories (category_id)
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            order_date DATE NOT NULL,
            status TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            shipping_city TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        );

        CREATE TABLE order_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            discount REAL NOT NULL DEFAULT 0.0,
            total_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (order_id),
            FOREIGN KEY (product_id) REFERENCES products (product_id)
        );
    """)

    # Seed Data
    random.seed(42)

    # 1. Categories
    category_data = [
        ("Electronics", "Laptops, monitors, smartphones, audio devices, and peripherals"),
        ("Furniture", "Office chairs, standing desks, bookcases, and conference tables"),
        ("Office Supplies", "Notebooks, pens, paper reams, staplers, and desk organizers"),
        ("Software & Subscriptions", "Productivity suites, cloud backups, and security tools"),
        ("Accessories", "Cables, adapters, laptop bags, webcams, and mice"),
    ]
    cursor.executemany(
        "INSERT INTO categories (category_name, description) VALUES (?, ?);",
        category_data,
    )

    # 2. Customers
    first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Sam", "Chris", "Pat", "Riley", "Casey", "Avery",
                   "Cameron", "Logan", "Dakota", "Reese", "Quinn", "Skyler", "Jesse", "Peyton", "Kendall", "Harper"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
                  "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
    regions = ["North", "South", "East", "West", "Central"]
    segments = ["Consumer", "Corporate", "Home Office", "Small Business"]

    customers_to_insert = []
    base_date = datetime(2023, 1, 1)
    for i in range(30):
        fname = random.choice(first_names)
        lname = random.choice(last_names)
        cname = f"{fname} {lname}"
        email = f"{fname.lower()}.{lname.lower()}{i+1}@example.com"
        reg = random.choice(regions)
        seg = random.choice(segments)
        s_date = (base_date + timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d")
        customers_to_insert.append((cname, email, reg, seg, s_date))

    cursor.executemany(
        "INSERT INTO customers (name, email, region, segment, signup_date) VALUES (?, ?, ?, ?, ?);",
        customers_to_insert,
    )

    # 3. Products
    products_data = [
        # Electronics (category_id = 1)
        ("UltraBook Pro 15", 1, 1299.99, 850.00),
        ("ErgoView 27-inch 4K Monitor", 1, 449.99, 290.00),
        ("Wireless Noise-Canceling Headset", 1, 199.99, 110.00),
        ("ProTab 10-inch Tablet", 1, 499.99, 320.00),
        ("SmartWatch Series 5", 1, 249.99, 140.00),

        # Furniture (category_id = 2)
        ("Ergonomic Mesh Chair", 2, 329.99, 180.00),
        ("Motorized Standing Desk", 2, 599.99, 340.00),
        ("Modular 4-Shelf Bookcase", 2, 189.99, 95.00),
        ("Conference Room Leather Chair", 2, 279.99, 150.00),
        ("Mobile Filing Cabinet", 2, 149.99, 80.00),

        # Office Supplies (category_id = 3)
        ("Premium Gel Ink Pens (Pack of 12)", 3, 18.99, 6.50),
        ("Executive Hardcover Notebook", 3, 24.99, 8.00),
        ("Multipurpose Copy Paper (Box)", 3, 49.99, 28.00),
        ("Heavy-Duty Desktop Stapler", 3, 29.99, 12.00),
        ("Adjustable Monitor Riser Organizer", 3, 39.99, 16.00),

        # Software & Subscriptions (category_id = 4)
        ("CloudSuite Business Annual", 4, 299.00, 60.00),
        ("SecureShield Antivirus Pro", 4, 89.00, 15.00),
        ("TeamCollab Pro Seat License", 4, 149.00, 25.00),

        # Accessories (category_id = 5)
        ("USB-C Multi-Port Hub", 5, 59.99, 22.00),
        ("Wireless Ergonomic Mouse", 5, 49.99, 19.00),
        ("HD 1080p Streaming Webcam", 5, 79.99, 35.00),
        ("Mechanical Backlit Keyboard", 5, 119.99, 55.00),
    ]
    cursor.executemany(
        "INSERT INTO products (product_name, category_id, unit_price, cost_price) VALUES (?, ?, ?, ?);",
        products_data,
    )

    # 4. Orders and Order Items
    cities = {
        "North": ["Chicago", "Minneapolis", "Detroit", "Milwaukee"],
        "South": ["Atlanta", "Dallas", "Miami", "Austin"],
        "East": ["New York", "Boston", "Philadelphia", "Washington DC"],
        "West": ["San Francisco", "Seattle", "Los Angeles", "Denver"],
        "Central": ["Kansas City", "St. Louis", "Indianapolis", "Omaha"],
    }
    statuses = ["Completed", "Shipped", "Processing", "Cancelled"]
    status_weights = [0.65, 0.20, 0.10, 0.05]
    payment_methods = ["Credit Card", "PayPal", "Bank Transfer", "Corporate Invoice"]

    order_date_start = datetime(2024, 1, 1)

    for order_id in range(1, 121):  # 120 realistic orders
        cust_id = random.randint(1, len(customers_to_insert))
        cursor.execute("SELECT region FROM customers WHERE customer_id = ?", (cust_id,))
        cust_region = cursor.fetchone()[0]
        shipping_city = random.choice(cities.get(cust_region, ["Chicago"]))

        days_offset = random.randint(0, 365)
        order_date = (order_date_start + timedelta(days=days_offset)).strftime("%Y-%m-%d")
        status = random.choices(statuses, weights=status_weights)[0]
        pay_method = random.choice(payment_methods)

        cursor.execute(
            """
            INSERT INTO orders (customer_id, order_date, status, payment_method, shipping_city)
            VALUES (?, ?, ?, ?, ?);
            """,
            (cust_id, order_date, status, pay_method, shipping_city),
        )

        # 1 to 4 distinct items per order
        num_items = random.randint(1, 4)
        chosen_products = random.sample(range(1, len(products_data) + 1), num_items)

        for prod_id in chosen_products:
            cursor.execute("SELECT unit_price FROM products WHERE product_id = ?", (prod_id,))
            u_price = cursor.fetchone()[0]
            qty = random.choices([1, 2, 3, 4, 5], weights=[0.45, 0.30, 0.15, 0.07, 0.03])[0]
            discount = random.choices([0.0, 0.05, 0.10, 0.15, 0.20], weights=[0.60, 0.15, 0.12, 0.08, 0.05])[0]
            total = round(qty * u_price * (1.0 - discount), 2)

            cursor.execute(
                """
                INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount, total_price)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (order_id, prod_id, qty, u_price, discount, total),
            )

    conn.commit()
    conn.close()
    return f"Successfully initialized and seeded database at: {db_path}"


def get_schema_ddl(db_path: str = DEFAULT_DB_PATH) -> str:
    """
    Extract the DDL schema description of the database.
    Formats table columns and foreign keys for LLM system prompts.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, sql FROM sqlite_master 
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name;
    """)
    tables = cursor.fetchall()

    ddl_parts = []
    for table_name, sql in tables:
        # Get column info
        cursor.execute(f"PRAGMA table_info({table_name});")
        cols = cursor.fetchall()
        col_summary = ", ".join([f"{col[1]} ({col[2]})" for col in cols])
        ddl_parts.append(f"-- Table: {table_name}\n{sql};\n-- Columns: {col_summary}\n")

    conn.close()
    return "\n".join(ddl_parts)


def get_schema_metadata(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Retrieve structured metadata of all tables, columns, and row counts.
    Used for the Streamlit UI schema viewer.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]

    metadata = {}
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        cols = cursor.fetchall()

        cursor.execute(f"SELECT COUNT(*) FROM {table};")
        count = cursor.fetchone()[0]

        metadata[table] = {
            "row_count": count,
            "columns": [{"cid": c[0], "name": c[1], "type": c[2], "notnull": bool(c[3]), "pk": bool(c[5])} for c in cols],
        }

    conn.close()
    return metadata


def execute_query(sql_query: str, db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Execute a read-only SQL query against the SQLite database and return a Pandas DataFrame.
    """
    conn = get_db_connection(db_path)
    try:
        df = pd.read_sql_query(sql_query, conn)
        return df
    finally:
        conn.close()


def get_sample_rows(table_name: str, limit: int = 5, db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Retrieve sample rows from a table."""
    conn = get_db_connection(db_path)
    try:
        query = f"SELECT * FROM {table_name} LIMIT {int(limit)};"
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    msg = init_db(force=True)
    print(msg)
    print("\n--- SCHEMA DDL ---")
    print(get_schema_ddl())
