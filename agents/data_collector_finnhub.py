#!/usr/bin/env python3
"""
Alternative Data Collector Using Finnhub

Use this if Alpha Vantage isn't working.
Finnhub free tier: 60 calls/min (much better than Alpha Vantage's 5/min!)
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from loguru import logger
from config.logging_config import setup_logging
from database.connection import get_db_connection
from utils.api_clients import finnhub, fred
import time

load_dotenv()


class FinnhubDataCollector:
    """Data collector using Finnhub as primary source"""

    def __init__(self):
        self.db = get_db_connection()
        setup_logging()
        logger.info("Finnhub Data Collector initialized")

    def collect_market_data_finnhub(self, symbols: list = None):
        """
        Collect price data using Finnhub candles API

        Finnhub provides historical daily candles (OHLCV)
        """
        if symbols is None:
            symbols = self._get_tracked_symbols()

        if not symbols:
            logger.warning("No symbols to collect")
            return

        logger.info(f"Collecting market data for {len(symbols)} symbols (Finnhub)")

        # Get last 100 days of data
        end_time = int(datetime.now().timestamp())
        start_time = int((datetime.now() - timedelta(days=100)).timestamp())

        for symbol in symbols:
            try:
                logger.info(f"Fetching {symbol} from Finnhub")

                # Finnhub candles endpoint
                import requests
                response = requests.get(
                    'https://finnhub.io/api/v1/stock/candle',
                    params={
                        'symbol': symbol,
                        'resolution': 'D',  # Daily
                        'from': start_time,
                        'to': end_time,
                        'token': os.getenv('FINNHUB_API_KEY')
                    },
                    timeout=30
                )

                data = response.json()

                if data.get('s') != 'ok':
                    logger.warning(f"No data for {symbol}: {data.get('s')}")
                    continue

                # Store in database
                self._store_finnhub_candles(symbol, data)

                # Rate limiting (60 calls/min = 1 per second)
                time.sleep(1.1)

            except Exception as e:
                logger.error(f"Error collecting {symbol}: {e}")
                continue

        logger.info("✓ Market data collection complete (Finnhub)")

    def _store_finnhub_candles(self, symbol: str, data: dict):
        """Store Finnhub candle data in database"""
        cursor = self.db.cursor()

        timestamps = data.get('t', [])
        opens = data.get('o', [])
        highs = data.get('h', [])
        lows = data.get('l', [])
        closes = data.get('c', [])
        volumes = data.get('v', [])

        inserted = 0

        for i in range(len(timestamps)):
            try:
                date = datetime.fromtimestamp(timestamps[i]).date()

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
                        volume = EXCLUDED.volume
                """, (
                    symbol,
                    date,
                    float(opens[i]),
                    float(highs[i]),
                    float(lows[i]),
                    float(closes[i]),
                    float(closes[i]),  # Finnhub doesn't provide adjusted, use close
                    int(volumes[i]),
                    0.0,  # No dividend data from this endpoint
                    1.0,  # No split data
                    'finnhub'
                ))

                inserted += 1

            except Exception as e:
                logger.error(f"Error storing {symbol} on {date}: {e}")
                continue

        self.db.commit()
        cursor.close()

        logger.info(f"  {symbol}: {inserted} days stored")

    def collect_economic_indicators(self):
        """Collect economic indicators from FRED (same as before)"""
        indicators = self._get_tracked_indicators()

        if not indicators:
            logger.warning("No economic indicators configured")
            return

        logger.info(f"Collecting {len(indicators)} economic indicators")

        start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')

        for indicator_code, name in indicators:
            try:
                logger.info(f"Fetching {name} ({indicator_code})")

                df = fred.get_series(indicator_code, observation_start=start_date)

                if df is None:
                    continue

                self._store_economic_data(indicator_code, df)

            except Exception as e:
                logger.error(f"Error collecting {indicator_code}: {e}")
                continue

        logger.info("✓ Economic data collection complete")

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
                inserted += 1
            except Exception as e:
                logger.error(f"Error storing {indicator_code} on {date}: {e}")
                continue

        self.db.commit()
        cursor.close()
        logger.info(f"  {indicator_code}: {inserted} observations stored")

    def run_daily_collection(self):
        """Run full daily data collection using Finnhub"""
        logger.info("=" * 70)
        logger.info("STARTING DAILY DATA COLLECTION (FINNHUB)")
        logger.info("=" * 70)

        start_time = datetime.now()

        try:
            # 1. Collect market data from Finnhub
            logger.info("\n[1/2] Collecting market data (Finnhub)...")
            self.collect_market_data_finnhub()

            # 2. Collect economic indicators from FRED
            logger.info("\n[2/2] Collecting economic indicators (FRED)...")
            self.collect_economic_indicators()

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
    collector = FinnhubDataCollector()

    try:
        collector.run_daily_collection()
    except KeyboardInterrupt:
        logger.info("\n⚠ Collection interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Collection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
