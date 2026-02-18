#!/usr/bin/env python3
"""
Data Collection Orchestrator

Coordinates all data collection agents to gather market data, fundamentals,
economic indicators, and sentiment data.

Usage:
    python agents/data_collector.py              # Collect all data
    python agents/data_collector.py --prices     # Only price data
    python agents/data_collector.py --economics  # Only economic data
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from loguru import logger
from config.logging_config import setup_logging
from database.connection import get_db_connection
from utils.api_clients import finnhub, fred
import pandas_datareader.data as web

load_dotenv()


class DataCollector:
    """Orchestrates data collection from multiple sources"""

    def __init__(self):
        self.db = get_db_connection()
        setup_logging()
        logger.info("Data Collector initialized")

    def collect_market_data(self, symbols: list = None):
        """
        Collect daily price data for stocks/ETFs

        Args:
            symbols: List of tickers, or None to use default watchlist
        """
        if symbols is None:
            # Get tracked securities from database
            symbols = self._get_tracked_symbols()

        if not symbols:
            logger.warning("No symbols to collect")
            return

        logger.info(f"Collecting market data for {len(symbols)} symbols (via Stooq)")

        # Fetch last 30 days - enough to catch any missed days, fast to process
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        for symbol in symbols:
            try:
                stooq_symbol = f"{symbol}.US"
                df = web.DataReader(stooq_symbol, 'stooq', start=start_date, end=end_date)

                if df is None or df.empty:
                    logger.warning(f"Skipping {symbol} - no data")
                    continue

                # Normalize columns to match schema
                df = df.sort_index()
                df = df.rename(columns={
                    'Open': 'open', 'High': 'high', 'Low': 'low',
                    'Close': 'close', 'Volume': 'volume'
                })
                df['adjusted_close'] = df['close']
                df['dividend'] = 0.0
                df['split_coefficient'] = 1.0

                self._store_daily_prices(symbol, df)

            except Exception as e:
                logger.error(f"Error collecting data for {symbol}: {e}")
                continue

        logger.info(f"✓ Market data collection complete")

    def collect_economic_indicators(self):
        """Collect economic indicators from FRED"""

        # Get indicator list from database
        indicators = self._get_tracked_indicators()

        if not indicators:
            logger.warning("No economic indicators configured")
            return

        logger.info(f"Collecting {len(indicators)} economic indicators")

        # Fetch last 2 years of data
        start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')

        for indicator_code, name in indicators:
            try:
                logger.info(f"Fetching {name} ({indicator_code})")

                df = fred.get_series(
                    indicator_code,
                    observation_start=start_date
                )

                if df is None:
                    continue

                # Store in database
                self._store_economic_data(indicator_code, df)

            except Exception as e:
                logger.error(f"Error collecting {indicator_code}: {e}")
                continue

        logger.info(f"✓ Economic data collection complete")

    def collect_company_profiles(self, symbols: list = None):
        """Update company metadata from Finnhub"""

        if symbols is None:
            symbols = self._get_tracked_symbols()

        logger.info(f"Updating profiles for {len(symbols)} securities")

        for symbol in symbols:
            try:
                profile = finnhub.get_company_profile(symbol)

                if profile:
                    self._update_security_metadata(symbol, profile)

            except Exception as e:
                logger.error(f"Error updating profile for {symbol}: {e}")
                continue

        logger.info(f"✓ Profile updates complete")

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

    def _get_tracked_indicators(self) -> list:
        """Get list of economic indicators to track"""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT indicator_code, name
            FROM indicator_metadata
            ORDER BY indicator_code
        """)
        indicators = cursor.fetchall()
        cursor.close()
        return indicators

    def _store_daily_prices(self, symbol: str, df):
        """Store daily price data in database"""
        cursor = self.db.cursor()

        inserted = 0
        updated = 0

        for date, row in df.iterrows():
            try:
                # Handle both datetime index and date objects
                record_date = date.date() if hasattr(date, 'date') else date

                cursor.execute("""
                    INSERT INTO daily_prices (
                        symbol, date, open, high, low, close,
                        adjusted_close, volume, dividend, split_factor,
                        data_source
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, date)
                    DO UPDATE SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        adjusted_close = EXCLUDED.adjusted_close,
                        volume = EXCLUDED.volume,
                        dividend = EXCLUDED.dividend,
                        split_factor = EXCLUDED.split_factor
                """, (
                    symbol,
                    record_date,
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['adjusted_close']),
                    int(row['volume']),
                    float(row.get('dividend', 0)),
                    float(row.get('split_coefficient', 1)),
                    'stooq'
                ))

                if cursor.rowcount > 0:
                    inserted += 1
                else:
                    updated += 1

            except Exception as e:
                logger.error(f"Error storing price for {symbol} on {date}: {e}")
                continue

        self.db.commit()
        cursor.close()

        logger.info(f"  {symbol}: {inserted} new, {updated} updated")

    def _store_economic_data(self, indicator_code: str, df):
        """Store economic indicator data"""
        cursor = self.db.cursor()

        inserted = 0

        for date, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT INTO economic_indicators (
                        indicator_code, date, value
                    ) VALUES (%s, %s, %s)
                    ON CONFLICT (indicator_code, date)
                    DO UPDATE SET value = EXCLUDED.value
                """, (
                    indicator_code,
                    date.date(),
                    float(row.iloc[0])
                ))

                if cursor.rowcount > 0:
                    inserted += 1

            except Exception as e:
                logger.error(f"Error storing {indicator_code} on {date}: {e}")
                continue

        self.db.commit()
        cursor.close()

        logger.info(f"  {indicator_code}: {inserted} observations stored")

    def _update_security_metadata(self, symbol: str, profile: dict):
        """Update security metadata from company profile"""
        cursor = self.db.cursor()

        try:
            cursor.execute("""
                UPDATE securities SET
                    name = %s,
                    exchange = %s,
                    sector = %s,
                    industry = %s,
                    market_cap = %s,
                    website = %s,
                    ipo_date = %s,
                    updated_at = NOW()
                WHERE symbol = %s
            """, (
                profile.get('name'),
                profile.get('exchange'),
                profile.get('finnhubIndustry'),
                profile.get('finnhubIndustry'),  # Use same for industry
                profile.get('marketCapitalization'),
                profile.get('weburl'),
                profile.get('ipo'),
                symbol
            ))

            self.db.commit()

        except Exception as e:
            logger.error(f"Error updating metadata for {symbol}: {e}")
            self.db.rollback()

        cursor.close()

    def run_daily_collection(self):
        """Run full daily data collection routine"""
        logger.info("=" * 70)
        logger.info("STARTING DAILY DATA COLLECTION")
        logger.info("=" * 70)

        start_time = datetime.now()

        try:
            # 1. Collect market data (prices)
            logger.info("\n[1/3] Collecting market data...")
            self.collect_market_data()

            # 2. Collect economic indicators
            logger.info("\n[2/3] Collecting economic indicators...")
            self.collect_economic_indicators()

            # 3. Update company profiles (weekly only - they rarely change)
            if datetime.now().weekday() == 0:  # Monday only
                logger.info("\n[3/3] Updating company profiles (weekly)...")
                self.collect_company_profiles()
            else:
                logger.info("\n[3/3] Skipping profile updates (runs Mondays only)")

            elapsed = (datetime.now() - start_time).total_seconds()

            logger.info("\n" + "=" * 70)
            logger.info(f"✓ DATA COLLECTION COMPLETE ({elapsed:.1f}s)")
            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"Data collection failed: {e}")
            raise
        finally:
            self.db.close()


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description='Investment Data Collector')
    parser.add_argument(
        '--prices',
        action='store_true',
        help='Collect only market prices'
    )
    parser.add_argument(
        '--economics',
        action='store_true',
        help='Collect only economic indicators'
    )
    parser.add_argument(
        '--profiles',
        action='store_true',
        help='Update only company profiles'
    )
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='Specific symbols to collect (e.g., AAPL MSFT)'
    )

    args = parser.parse_args()

    collector = DataCollector()

    try:
        # Run specific collection or full daily routine
        if args.prices:
            collector.collect_market_data(symbols=args.symbols)
        elif args.economics:
            collector.collect_economic_indicators()
        elif args.profiles:
            collector.collect_company_profiles(symbols=args.symbols)
        else:
            # Run full daily collection
            collector.run_daily_collection()

    except KeyboardInterrupt:
        logger.info("\n⚠ Collection interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Collection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
