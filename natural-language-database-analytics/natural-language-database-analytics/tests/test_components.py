"""
Unit Tests for Natural Language Database Analytics Agent.

Tests:
1. Database initialization, relational schema, seeding, and query execution.
2. SQL security validator enforcing read-only SELECT queries and blocking injections.
3. Chart generator automated visualization heuristics.
"""

import os
import unittest
import pandas as pd

from src.database import init_db, get_schema_ddl, execute_query, get_schema_metadata
from src.sql_validator import validate_sql
from src.chart_generator import auto_generate_chart, create_bar_chart, create_line_chart


class TestDatabaseModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db_path = os.path.join(os.path.dirname(__file__), "test_sales.db")
        init_db(cls.test_db_path, force=True)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
            except Exception:
                pass

    def test_database_tables_seeded(self):
        meta = get_schema_metadata(self.test_db_path)
        expected_tables = ["customers", "categories", "products", "orders", "order_items"]
        for tbl in expected_tables:
            self.assertIn(tbl, meta, f"Table {tbl} was not found in database.")
            self.assertGreater(meta[tbl]["row_count"], 0, f"Table {tbl} has no seeded records.")

    def test_schema_ddl_extraction(self):
        ddl = get_schema_ddl(self.test_db_path)
        self.assertIn("CREATE TABLE customers", ddl)
        self.assertIn("CREATE TABLE orders", ddl)
        self.assertIn("CREATE TABLE order_items", ddl)

    def test_execute_query(self):
        query = """
            SELECT c.region, COUNT(o.order_id) AS order_count, ROUND(SUM(oi.total_price), 2) AS revenue
            FROM customers c
            JOIN orders o ON c.customer_id = o.customer_id
            JOIN order_items oi ON o.order_id = oi.order_id
            GROUP BY c.region
            ORDER BY revenue DESC;
        """
        df = execute_query(query, self.test_db_path)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertIn("region", df.columns)
        self.assertIn("revenue", df.columns)


class TestSQLValidator(unittest.TestCase):
    def test_valid_select_query(self):
        sql = "SELECT customer_id, name, region FROM customers WHERE region = 'North';"
        is_valid, sanitized, err = validate_sql(sql)
        self.assertTrue(is_valid)
        self.assertIsNone(err)
        self.assertEqual(sanitized, "SELECT customer_id, name, region FROM customers WHERE region = 'North'")

    def test_valid_cte_query(self):
        sql = """
            WITH monthly_summary AS (
                SELECT strftime('%Y-%m', order_date) as month, SUM(total_price) as total
                FROM orders o JOIN order_items oi ON o.order_id = oi.order_id
                GROUP BY month
            )
            SELECT month, total FROM monthly_summary WHERE total > 1000;
        """
        is_valid, sanitized, err = validate_sql(sql)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_markdown_fence_cleaning(self):
        raw = "```sql\nSELECT * FROM products;\n```"
        is_valid, sanitized, err = validate_sql(raw)
        self.assertTrue(is_valid)
        self.assertEqual(sanitized, "SELECT * FROM products")

    def test_reject_drop_table(self):
        sql = "DROP TABLE customers;"
        is_valid, _, err = validate_sql(sql)
        self.assertFalse(is_valid)
        self.assertIsNotNone(err)

    def test_reject_delete_statement(self):
        sql = "DELETE FROM orders WHERE order_id = 1;"
        is_valid, _, err = validate_sql(sql)
        self.assertFalse(is_valid)
        self.assertIsNotNone(err)

    def test_reject_update_statement(self):
        sql = "UPDATE products SET unit_price = 0 WHERE product_id = 1;"
        is_valid, _, err = validate_sql(sql)
        self.assertFalse(is_valid)
        self.assertIsNotNone(err)

    def test_reject_insert_statement(self):
        sql = "INSERT INTO categories (category_name) VALUES ('Hacked');"
        is_valid, _, err = validate_sql(sql)
        self.assertFalse(is_valid)
        self.assertIsNotNone(err)

    def test_reject_multi_statement_injection(self):
        sql = "SELECT * FROM orders; DROP TABLE customers;"
        is_valid, _, err = validate_sql(sql)
        self.assertFalse(is_valid)
        self.assertIn("Multiple", err)

    def test_reject_pragma(self):
        sql = "PRAGMA table_info(customers);"
        is_valid, _, err = validate_sql(sql)
        self.assertFalse(is_valid)


class TestChartGenerator(unittest.TestCase):
    def test_scalar_kpi_metric(self):
        df = pd.DataFrame({"total_revenue": [125430.50]})
        fig, chart_type = auto_generate_chart(df)
        self.assertIsNotNone(fig)
        self.assertEqual(chart_type, "Metric KPI Card")

    def test_categorical_bar_chart(self):
        df = pd.DataFrame({
            "region": ["North", "South", "East", "West"],
            "revenue": [25000, 18000, 32000, 21000]
        })
        fig, chart_type = auto_generate_chart(df)
        self.assertIsNotNone(fig)
        self.assertIn("Bar Chart", chart_type)

    def test_time_series_line_chart(self):
        df = pd.DataFrame({
            "order_date": ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"],
            "monthly_sales": [12000, 15000, 19000, 17500]
        })
        fig, chart_type = auto_generate_chart(df)
        self.assertIsNotNone(fig)
        self.assertIn("Line Chart", chart_type)

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        fig, chart_type = auto_generate_chart(df)
        self.assertIsNone(fig)


if __name__ == "__main__":
    unittest.main()
