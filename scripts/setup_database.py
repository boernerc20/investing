#!/usr/bin/env python3
"""
Database Setup Script

Initializes PostgreSQL database with TimescaleDB extension and creates schema.
Run this script once before starting the application.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv(project_root / ".env")


def create_database():
    """Create the investing database if it doesn't exist"""

    # Connect to default postgres database
    conn = psycopg2.connect(
        host="localhost",
        database="postgres",
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "")
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    db_name = "investing_db"

    # Check if database exists
    cursor.execute(
        "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
        (db_name,)
    )
    exists = cursor.fetchone()

    if not exists:
        print(f"Creating database: {db_name}")
        cursor.execute(f"CREATE DATABASE {db_name}")
        print(f"✓ Database '{db_name}' created successfully")
    else:
        print(f"✓ Database '{db_name}' already exists")

    cursor.close()
    conn.close()


def setup_schema():
    """Execute schema.sql to create tables and views"""

    # Parse DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set in .env file")
        sys.exit(1)

    # Connect to investing database
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    # Read and execute schema file
    schema_file = project_root / "database" / "schema.sql"

    if not schema_file.exists():
        print(f"ERROR: Schema file not found: {schema_file}")
        sys.exit(1)

    print(f"Executing schema from: {schema_file}")

    with open(schema_file, 'r') as f:
        schema_sql = f.read()

    try:
        cursor.execute(schema_sql)
        conn.commit()
        print("✓ Schema created successfully")

        # Verify tables were created
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)

        tables = cursor.fetchall()
        print(f"\n✓ Created {len(tables)} tables:")
        for table in tables:
            print(f"  - {table[0]}")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: Failed to create schema: {e}")
        sys.exit(1)

    finally:
        cursor.close()
        conn.close()


def seed_initial_data():
    """Insert initial reference data"""

    database_url = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    print("\nSeeding initial data...")

    # Common economic indicators to track
    indicators = [
        ('GDPC1', 'Real Gross Domestic Product', 'Billions of Chained 2017 Dollars', 'quarterly', 'gdp'),
        ('UNRATE', 'Unemployment Rate', 'Percent', 'monthly', 'employment'),
        ('CPIAUCSL', 'Consumer Price Index for All Urban Consumers', 'Index 1982-1984=100', 'monthly', 'inflation'),
        ('FEDFUNDS', 'Federal Funds Effective Rate', 'Percent', 'monthly', 'rates'),
        ('GS10', '10-Year Treasury Constant Maturity Rate', 'Percent', 'daily', 'rates'),
        ('GS2', '2-Year Treasury Constant Maturity Rate', 'Percent', 'daily', 'rates'),
        ('UMCSENT', 'University of Michigan: Consumer Sentiment', 'Index 1966:Q1=100', 'monthly', 'sentiment'),
        ('VIXCLS', 'CBOE Volatility Index: VIX', 'Index', 'daily', 'volatility'),
    ]

    cursor.executemany("""
        INSERT INTO indicator_metadata (indicator_code, name, units, frequency, category)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (indicator_code) DO NOTHING
    """, indicators)

    # Common ETFs to track
    etfs = [
        ('SPY', 'SPDR S&P 500 ETF Trust', 'etf', 'NYSE', 'Equity', 'Broad Market'),
        ('VTI', 'Vanguard Total Stock Market ETF', 'etf', 'NYSE', 'Equity', 'Broad Market'),
        ('VXUS', 'Vanguard Total International Stock ETF', 'etf', 'NASDAQ', 'Equity', 'International'),
        ('BND', 'Vanguard Total Bond Market ETF', 'etf', 'NASDAQ', 'Fixed Income', 'Bonds'),
        ('QQQ', 'Invesco QQQ Trust', 'etf', 'NASDAQ', 'Technology', 'Growth'),
        ('XLK', 'Technology Select Sector SPDR Fund', 'etf', 'NYSE', 'Technology', 'Sector'),
        ('XLF', 'Financial Select Sector SPDR Fund', 'etf', 'NYSE', 'Financials', 'Sector'),
        ('XLV', 'Health Care Select Sector SPDR Fund', 'etf', 'NYSE', 'Healthcare', 'Sector'),
        ('XLE', 'Energy Select Sector SPDR Fund', 'etf', 'NYSE', 'Energy', 'Sector'),
        ('XLI', 'Industrial Select Sector SPDR Fund', 'etf', 'NYSE', 'Industrials', 'Sector'),
        ('VIG', 'Vanguard Dividend Appreciation ETF', 'etf', 'NYSE', 'Equity', 'Dividend'),
    ]

    cursor.executemany("""
        INSERT INTO securities (symbol, name, type, exchange, sector, industry)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (symbol) DO NOTHING
    """, etfs)

    # User profile (initial setup)
    cursor.execute("""
        INSERT INTO user_profile (
            monthly_income,
            monthly_investment_amount,
            emergency_fund_target,
            emergency_fund_current,
            risk_tolerance,
            investment_horizon_years,
            investment_goals
        ) VALUES (
            5850.00,
            0.00,  -- Start with 0, build emergency fund first
            30000.00,  -- 6 months expenses (~$5000/month)
            0.00,
            'moderate',
            30,  -- Long-term investing
            'Build emergency fund, then invest for long-term wealth building. Learn investing fundamentals.'
        )
        ON CONFLICT DO NOTHING
    """)

    conn.commit()
    cursor.close()
    conn.close()

    print("✓ Initial data seeded")


def main():
    print("=" * 70)
    print("INVESTMENT DATABASE SETUP")
    print("=" * 70)

    try:
        # Step 1: Create database
        create_database()

        # Step 2: Create schema
        setup_schema()

        # Step 3: Seed initial data
        seed_initial_data()

        print("\n" + "=" * 70)
        print("✓ DATABASE SETUP COMPLETE")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Update .env with your API keys")
        print("2. Run: python agents/data_collector.py")
        print("3. Run: python dashboard/app.py")

    except Exception as e:
        print(f"\n✗ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
