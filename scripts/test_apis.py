#!/usr/bin/env python3
"""
API Connection Test Script

Tests all configured API keys and verifies they work correctly.
Run this before attempting data collection.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
from dotenv import load_dotenv
from config.logging_config import setup_logging
from utils.api_clients import alpha_vantage, finnhub, fred, sec_edgar

load_dotenv()
setup_logging(level="INFO")


def test_alpha_vantage():
    """Test Alpha Vantage API"""
    print("\n[1/4] Testing Alpha Vantage...")
    print("-" * 70)

    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    if not api_key:
        print("  ✗ API key not configured")
        print("  → Set ALPHA_VANTAGE_API_KEY in .env")
        print("  → Get key at: https://www.alphavantage.co/support/#api-key")
        return False

    print(f"  API Key: {api_key[:8]}...{api_key[-4:]}")

    # Test with SPY
    df = alpha_vantage.get_daily_prices('SPY', outputsize='compact')

    if df is None:
        print("  ✗ Failed to fetch data")
        print("  → Check API key is valid")
        print("  → Verify rate limits (5 calls/min, 25 calls/day)")
        return False

    print(f"  ✓ Retrieved {len(df)} days of SPY data")
    print(f"  Latest: {df.index[-1].date()} - Close: ${df['close'].iloc[-1]:.2f}")
    return True


def test_finnhub():
    """Test Finnhub API"""
    print("\n[2/4] Testing Finnhub...")
    print("-" * 70)

    api_key = os.getenv('FINNHUB_API_KEY')
    if not api_key:
        print("  ✗ API key not configured")
        print("  → Set FINNHUB_API_KEY in .env")
        print("  → Get key at: https://finnhub.io/register")
        return False

    print(f"  API Key: {api_key[:8]}...{api_key[-4:]}")

    # Test with AAPL
    quote = finnhub.get_quote('AAPL')

    if not quote:
        print("  ✗ Failed to fetch quote")
        print("  → Check API key is valid")
        return False

    print(f"  ✓ Retrieved AAPL quote")
    print(f"  Current: ${quote['current_price']:.2f}")
    print(f"  Change: {quote['percent_change']:+.2f}%")

    # Test company profile
    profile = finnhub.get_company_profile('AAPL')
    if profile:
        print(f"  ✓ Retrieved company profile: {profile.get('name')}")

    return True


def test_fred():
    """Test FRED API"""
    print("\n[3/4] Testing FRED...")
    print("-" * 70)

    api_key = os.getenv('FRED_API_KEY')
    if not api_key:
        print("  ✗ API key not configured")
        print("  → Set FRED_API_KEY in .env")
        print("  → Get key at: https://fred.stlouisfed.org/docs/api/api_key.html")
        return False

    print(f"  API Key: {api_key[:8]}...{api_key[-4:]}")

    # Test with GDP
    df = fred.get_series('GDPC1', observation_start='2020-01-01')

    if df is None:
        print("  ✗ Failed to fetch series")
        print("  → Check API key is valid")
        return False

    print(f"  ✓ Retrieved {len(df)} GDP observations")
    print(f"  Latest: {df.index[-1].date()} - ${df.iloc[-1].values[0]:,.0f}B")
    return True


def test_sec_edgar():
    """Test SEC EDGAR API"""
    print("\n[4/4] Testing SEC EDGAR...")
    print("-" * 70)

    print("  Note: No API key needed (public API)")

    # Test with Apple's CIK
    facts = sec_edgar.get_company_facts('0000320193')  # Apple

    if not facts:
        print("  ✗ Failed to fetch company facts")
        print("  → SEC API may be temporarily unavailable")
        return False

    company_name = facts.get('entityName', 'Unknown')
    print(f"  ✓ Retrieved facts for: {company_name}")
    return True


def test_database():
    """Test database connection"""
    print("\n[BONUS] Testing Database Connection...")
    print("-" * 70)

    try:
        from database.connection import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor()

        # Test query
        cursor.execute("SELECT COUNT(*) FROM securities;")
        count = cursor.fetchone()[0]
        print(f"  ✓ Connected to database")
        print(f"  Securities tracked: {count}")

        # Check for existing price data
        cursor.execute("""
            SELECT COUNT(DISTINCT symbol), COUNT(*)
            FROM daily_prices
        """)
        symbols, rows = cursor.fetchone()
        print(f"  Price data: {rows} rows for {symbols} symbols")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"  ✗ Database connection failed: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 70)
    print("API CONNECTION TEST SUITE")
    print("=" * 70)

    results = {
        'Alpha Vantage': test_alpha_vantage(),
        'Finnhub': test_finnhub(),
        'FRED': test_fred(),
        'SEC EDGAR': test_sec_edgar(),
        'Database': test_database()
    }

    print("\n" + "=" * 70)
    print("TEST RESULTS SUMMARY")
    print("=" * 70)

    all_passed = True
    for api, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {api:<20} {status}")
        if not passed:
            all_passed = False

    print("=" * 70)

    if all_passed:
        print("\n✓ ALL TESTS PASSED - Ready to collect data!")
        print("\nNext step:")
        print("  python agents/data_collector.py")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED - Fix configuration before proceeding")
        print("\nChecklist:")
        print("  1. Verify API keys in .env file")
        print("  2. Check internet connection")
        print("  3. Verify database is running")
        return 1


if __name__ == "__main__":
    sys.exit(main())
