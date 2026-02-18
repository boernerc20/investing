#!/usr/bin/env python3
"""
Backfill Historical Data

Fetches full historical price data using Stooq (free, no API key required).
Use this once to populate your database with historical data for technical analysis.

Usage:
    python scripts/backfill_historical_data.py           # All symbols, 5 years
    python scripts/backfill_historical_data.py --years 2
    python scripts/backfill_historical_data.py SPY VTI   # Specific symbols
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from loguru import logger
from config.logging_config import setup_logging
from database.connection import get_db_connection
import pandas_datareader.data as web
from datetime import datetime, timedelta
import argparse

load_dotenv()
setup_logging()


class HistoricalDataBackfill:
    """Backfill historical price data using Stooq (free, no API key)"""

    def __init__(self):
        self.db = get_db_connection()

    def backfill_prices(self, symbols: list = None, years: int = 5):
        """
        Backfill full historical data for symbols.

        Args:
            symbols: List of symbols to backfill (None = all tracked symbols)
            years: Years of history to fetch (default: 5)
        """
        if symbols is None:
            symbols = self._get_tracked_symbols()

        if not symbols:
            logger.warning("No symbols to backfill")
            return

        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)

        print("\n" + "="*70)
        print("HISTORICAL DATA BACKFILL (Stooq - Free, No API Key)")
        print("="*70)
        print(f"Symbols: {', '.join(symbols)}")
        print(f"History: {years} years ({start_date.date()} to {end_date.date()})")
        print()

        success_count = 0
        error_count = 0

        for i, symbol in enumerate(symbols, 1):
            logger.info(f"[{i}/{len(symbols)}] Fetching {years}yr history for {symbol}")

            try:
                # Stooq uses SYMBOL.US format for US stocks/ETFs
                stooq_symbol = f"{symbol}.US"
                df = web.DataReader(stooq_symbol, 'stooq', start=start_date, end=end_date)

                if df is None or df.empty:
                    logger.warning(f"No data returned for {symbol}")
                    error_count += 1
                    continue

                # Stooq returns descending order - sort ascending
                df = df.sort_index()

                # Rename columns to match our schema
                df = df.rename(columns={
                    'Open': 'open',
                    'High': 'high',
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume',
                })
                df['adjusted_close'] = df['close']
                df['dividend'] = 0.0
                df['split_coefficient'] = 1.0

                # Make date a column (it's the index)
                df = df.reset_index()
                df['date'] = df['Date'].dt.date

                stored = self._store_daily_prices(symbol, df)
                success_count += 1
                logger.info(f"  ✓ {symbol}: {stored['new']} new, {stored['updated']} updated records")

            except Exception as e:
                logger.error(f"Error backfilling {symbol}: {e}")
                error_count += 1
                continue

        print("\n" + "="*70)
        print(f"BACKFILL COMPLETE")
        print(f"  Success: {success_count}/{len(symbols)}")
        print(f"  Errors:  {error_count}/{len(symbols)}")
        print("="*70 + "\n")

        self._show_database_stats()

    def _get_tracked_symbols(self) -> list:
        """Get list of symbols to track from database"""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT symbol FROM securities
            WHERE is_active = TRUE
            ORDER BY symbol
        """)
        symbols = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return symbols

    def _store_daily_prices(self, symbol: str, df) -> dict:
        """Store price data in database with upsert logic"""
        cursor = self.db.cursor()
        new_count = 0
        updated_count = 0

        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO daily_prices (
                    symbol, date, open, high, low, close, adjusted_close,
                    volume, dividend, split_factor, data_source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, date) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    adjusted_close = EXCLUDED.adjusted_close,
                    volume = EXCLUDED.volume,
                    dividend = EXCLUDED.dividend,
                    split_factor = EXCLUDED.split_factor,
                    data_source = EXCLUDED.data_source
                RETURNING (xmax = 0) AS inserted
            """, (
                symbol,
                row['date'],
                float(row['open']),
                float(row['high']),
                float(row['low']),
                float(row['close']),
                float(row['adjusted_close']),
                int(row['volume']),
                float(row['dividend']),
                float(row['split_coefficient']),
                'stooq'
            ))

            result = cursor.fetchone()
            if result and result[0]:
                new_count += 1
            else:
                updated_count += 1

        self.db.commit()
        cursor.close()
        return {'new': new_count, 'updated': updated_count}

    def _show_database_stats(self):
        """Show current database statistics"""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT symbol, COUNT(*) as days, MIN(date) as first_date, MAX(date) as last_date
            FROM daily_prices
            GROUP BY symbol
            ORDER BY symbol
        """)

        print("Database Statistics:")
        print("-" * 70)
        print(f"{'Symbol':<10} {'Days':<8} {'First Date':<15} {'Last Date':<15}")
        print("-" * 70)

        total_records = 0
        for row in cursor.fetchall():
            symbol, days, first_date, last_date = row
            print(f"{symbol:<10} {days:<8} {str(first_date):<15} {str(last_date):<15}")
            total_records += days

        print("-" * 70)
        print(f"Total records: {total_records:,}")
        print()
        cursor.close()


def main():
    parser = argparse.ArgumentParser(description='Backfill historical price data using Stooq')
    parser.add_argument('symbols', nargs='*', help='Specific symbols (default: all tracked)')
    parser.add_argument('--years', type=int, default=5, help='Years of history to fetch (default: 5)')
    args = parser.parse_args()

    backfiller = HistoricalDataBackfill()
    backfiller.backfill_prices(
        symbols=args.symbols if args.symbols else None,
        years=args.years
    )


if __name__ == '__main__':
    main()
