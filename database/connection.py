"""
Database Connection Manager

Handles PostgreSQL connections with connection pooling.
"""

import os
import psycopg2
from psycopg2 import pool
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


class DatabasePool:
    """PostgreSQL connection pool singleton"""

    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._pool is None:
            self._initialize_pool()

    def _initialize_pool(self):
        """Initialize connection pool"""
        database_url = os.getenv('DATABASE_URL')

        if not database_url:
            raise ValueError("DATABASE_URL not set in environment")

        try:
            self._pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=database_url
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

    def get_connection(self):
        """Get a connection from the pool"""
        if self._pool is None:
            self._initialize_pool()

        try:
            conn = self._pool.getconn()
            return conn
        except Exception as e:
            logger.error(f"Failed to get connection: {e}")
            raise

    def return_connection(self, conn):
        """Return a connection to the pool"""
        if self._pool:
            self._pool.putconn(conn)

    def close_all(self):
        """Close all connections in pool"""
        if self._pool:
            self._pool.closeall()
            logger.info("All database connections closed")


# Global pool instance
db_pool = DatabasePool()


def get_db_connection():
    """
    Get a database connection

    Returns:
        psycopg2 connection object

    Usage:
        conn = get_db_connection()
        cursor = conn.cursor()
        # ... use connection ...
        cursor.close()
        conn.close()  # Returns to pool
    """
    return db_pool.get_connection()


def execute_query(query: str, params: tuple = None, fetch: bool = True):
    """
    Execute a query and return results

    Args:
        query: SQL query string
        params: Query parameters tuple
        fetch: Whether to fetch results

    Returns:
        List of rows if fetch=True, else None
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(query, params)

        if fetch:
            results = cursor.fetchall()
        else:
            conn.commit()
            results = None

        return results

    except Exception as e:
        conn.rollback()
        logger.error(f"Query execution failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    """Test database connection"""
    from config.logging_config import setup_logging

    setup_logging()

    print("Testing database connection...")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Test query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✓ Connected to: {version}")

        # Test tables exist
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        print(f"✓ Found {len(tables)} tables")

        cursor.close()
        conn.close()

        print("✓ Database connection test successful!")

    except Exception as e:
        print(f"✗ Database connection test failed: {e}")
