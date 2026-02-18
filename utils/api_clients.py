"""
API Client Wrappers for Financial Data Sources

Handles API authentication, rate limiting, and error handling.
"""

import os
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv
from loguru import logger
import pandas as pd

load_dotenv()


class RateLimitedClient:
    """Base class for rate-limited API clients"""

    def __init__(self, calls_per_minute: int):
        self.calls_per_minute = calls_per_minute
        self.min_delay = 60.0 / calls_per_minute
        self.last_call_time = 0

    def wait_if_needed(self):
        """Enforce rate limiting between API calls"""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_delay:
            wait_time = self.min_delay - elapsed
            logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        self.last_call_time = time.time()


class AlphaVantageClient(RateLimitedClient):
    """Alpha Vantage API client for stock data"""

    def __init__(self):
        super().__init__(calls_per_minute=5)  # Free tier: 5 calls/min
        self.api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        self.base_url = 'https://www.alphavantage.co/query'

        if not self.api_key:
            logger.warning("ALPHA_VANTAGE_API_KEY not set")

    def get_daily_prices(
        self,
        symbol: str,
        outputsize: str = 'compact'
    ) -> Optional[pd.DataFrame]:
        """
        Get daily price data for a symbol

        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            outputsize: 'compact' (100 days) or 'full' (20+ years)

        Returns:
            DataFrame with OHLCV data or None if error
        """
        self.wait_if_needed()

        # Use TIME_SERIES_DAILY (free tier) instead of TIME_SERIES_DAILY_ADJUSTED (premium)
        params = {
            'function': 'TIME_SERIES_DAILY',
            'symbol': symbol,
            'outputsize': outputsize,
            'apikey': self.api_key
        }

        try:
            logger.info(f"Fetching daily prices for {symbol}")
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Check for API errors
            if 'Error Message' in data:
                logger.error(f"Alpha Vantage error: {data['Error Message']}")
                return None

            if 'Note' in data:
                logger.warning(f"Alpha Vantage rate limit: {data['Note']}")
                return None

            # Parse time series data
            time_series = data.get('Time Series (Daily)', {})
            if not time_series:
                logger.warning(f"No data returned for {symbol}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame.from_dict(time_series, orient='index')
            df.index = pd.to_datetime(df.index)
            df.index.name = 'date'

            # Rename columns (free tier doesn't have adjusted/dividend/split)
            df.columns = ['open', 'high', 'low', 'close', 'volume']

            # Add missing columns (not available in free tier)
            df['adjusted_close'] = df['close']  # Use close as adjusted
            df['dividend'] = 0.0
            df['split_coefficient'] = 1.0

            # Convert to numeric
            df = df.astype(float)

            # Sort by date ascending
            df = df.sort_index()

            logger.info(f"✓ Retrieved {len(df)} days for {symbol}")
            return df

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing data for {symbol}: {e}")
            return None


class FinnhubClient(RateLimitedClient):
    """Finnhub API client for real-time and fundamental data"""

    def __init__(self):
        super().__init__(calls_per_minute=60)  # Free tier: 60 calls/min
        self.api_key = os.getenv('FINNHUB_API_KEY')
        self.base_url = 'https://finnhub.io/api/v1'

        if not self.api_key:
            logger.warning("FINNHUB_API_KEY not set")

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get real-time quote for a symbol"""
        self.wait_if_needed()

        try:
            logger.info(f"Fetching quote for {symbol}")
            response = requests.get(
                f"{self.base_url}/quote",
                params={'symbol': symbol, 'token': self.api_key},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            if data.get('c') == 0:  # No data
                logger.warning(f"No quote data for {symbol}")
                return None

            return {
                'current_price': data.get('c'),
                'change': data.get('d'),
                'percent_change': data.get('dp'),
                'high': data.get('h'),
                'low': data.get('l'),
                'open': data.get('o'),
                'previous_close': data.get('pc'),
                'timestamp': datetime.fromtimestamp(data.get('t', 0))
            }

        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None

    def get_company_profile(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get company profile and metadata"""
        self.wait_if_needed()

        try:
            logger.info(f"Fetching profile for {symbol}")
            response = requests.get(
                f"{self.base_url}/stock/profile2",
                params={'symbol': symbol, 'token': self.api_key},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                return None

            return data

        except Exception as e:
            logger.error(f"Error fetching profile for {symbol}: {e}")
            return None

    def get_historical_candles(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        resolution: str = 'D'
    ) -> Optional[pd.DataFrame]:
        """
        Get historical OHLCV candle data (free tier supported).

        Args:
            symbol: Stock ticker (e.g., 'SPY')
            from_date: Start date
            to_date: End date
            resolution: D=daily, W=weekly, M=monthly

        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        self.wait_if_needed()

        params = {
            'symbol': symbol,
            'resolution': resolution,
            'from': int(from_date.timestamp()),
            'to': int(to_date.timestamp()),
            'token': self.api_key
        }

        try:
            logger.info(f"Fetching historical candles for {symbol}")
            response = requests.get(
                f"{self.base_url}/stock/candle",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            if data.get('s') == 'no_data':
                logger.warning(f"No candle data for {symbol}")
                return None

            if data.get('s') != 'ok':
                logger.warning(f"Unexpected status for {symbol}: {data.get('s')}")
                return None

            df = pd.DataFrame({
                'date': pd.to_datetime(data['t'], unit='s').date,
                'open': data['o'],
                'high': data['h'],
                'low': data['l'],
                'close': data['c'],
                'volume': data['v'],
            })

            df['adjusted_close'] = df['close']
            df['dividend'] = 0.0
            df['split_coefficient'] = 1.0

            logger.info(f"✓ Retrieved {len(df)} days for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching candles for {symbol}: {e}")
            return None

    def get_news(
        self,
        symbol: str,
        from_date: str,
        to_date: str
    ) -> List[Dict[str, Any]]:
        """
        Get company news

        Args:
            symbol: Stock ticker
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
        """
        self.wait_if_needed()

        try:
            logger.info(f"Fetching news for {symbol}")
            response = requests.get(
                f"{self.base_url}/company-news",
                params={
                    'symbol': symbol,
                    'from': from_date,
                    'to': to_date,
                    'token': self.api_key
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return []


class FREDClient(RateLimitedClient):
    """Federal Reserve Economic Data (FRED) API client"""

    def __init__(self):
        super().__init__(calls_per_minute=120)  # Very generous limit
        self.api_key = os.getenv('FRED_API_KEY')
        self.base_url = 'https://api.stlouisfed.org/fred'

        if not self.api_key:
            logger.warning("FRED_API_KEY not set")

    def get_series(
        self,
        series_id: str,
        observation_start: Optional[str] = None,
        observation_end: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        Get economic time series data

        Args:
            series_id: FRED series ID (e.g., 'GDPC1', 'UNRATE')
            observation_start: Start date (YYYY-MM-DD)
            observation_end: End date (YYYY-MM-DD)

        Returns:
            DataFrame with date index and value column
        """
        self.wait_if_needed()

        params = {
            'series_id': series_id,
            'api_key': self.api_key,
            'file_type': 'json'
        }

        if observation_start:
            params['observation_start'] = observation_start
        if observation_end:
            params['observation_end'] = observation_end

        try:
            logger.info(f"Fetching FRED series {series_id}")
            response = requests.get(
                f"{self.base_url}/series/observations",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            observations = data.get('observations', [])
            if not observations:
                logger.warning(f"No data for {series_id}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(observations)
            df['date'] = pd.to_datetime(df['date'])
            df['value'] = pd.to_numeric(df['value'], errors='coerce')

            # Filter out missing values (marked as '.')
            df = df[df['value'].notna()]

            # Set date as index
            df = df.set_index('date')[['value']]
            df.columns = [series_id]

            logger.info(f"✓ Retrieved {len(df)} observations for {series_id}")
            return df

        except Exception as e:
            logger.error(f"Error fetching FRED series {series_id}: {e}")
            return None


class SECEdgarClient:
    """SEC EDGAR API client for financial filings"""

    def __init__(self):
        self.base_url = 'https://data.sec.gov'
        # SEC requires User-Agent header
        self.headers = {
            'User-Agent': 'Investment Portfolio System contact@example.com'
        }
        self.rate_limit = 10  # 10 requests per second max
        self.last_call_time = 0

    def wait_if_needed(self):
        """Enforce SEC rate limiting"""
        elapsed = time.time() - self.last_call_time
        min_delay = 1.0 / self.rate_limit
        if elapsed < min_delay:
            time.sleep(min_delay - elapsed)
        self.last_call_time = time.time()

    def get_company_facts(self, cik: str) -> Optional[Dict[str, Any]]:
        """
        Get company facts (XBRL data)

        Args:
            cik: Company CIK number (10 digits, zero-padded)

        Returns:
            Dictionary of company facts
        """
        self.wait_if_needed()

        # Ensure CIK is 10 digits with leading zeros
        cik = str(cik).zfill(10)

        try:
            logger.info(f"Fetching SEC facts for CIK {cik}")
            response = requests.get(
                f"{self.base_url}/api/xbrl/companyfacts/CIK{cik}.json",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"No SEC data for CIK {cik}")
            else:
                logger.error(f"HTTP error for CIK {cik}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching SEC facts for CIK {cik}: {e}")
            return None


# Singleton instances for import
alpha_vantage = AlphaVantageClient()
finnhub = FinnhubClient()
fred = FREDClient()
sec_edgar = SECEdgarClient()


if __name__ == "__main__":
    """Test API clients"""
    from config.logging_config import setup_logging

    setup_logging()

    print("Testing API Clients")
    print("=" * 70)

    # Test Alpha Vantage
    print("\n1. Testing Alpha Vantage (SPY daily prices)...")
    df = alpha_vantage.get_daily_prices('SPY', outputsize='compact')
    if df is not None:
        print(f"   ✓ Retrieved {len(df)} days")
        print(f"   Latest: {df.index[-1].date()} - Close: ${df['close'].iloc[-1]:.2f}")

    # Test Finnhub
    print("\n2. Testing Finnhub (AAPL quote)...")
    quote = finnhub.get_quote('AAPL')
    if quote:
        print(f"   ✓ Current price: ${quote['current_price']:.2f}")
        print(f"   Change: {quote['percent_change']:.2f}%")

    # Test FRED
    print("\n3. Testing FRED (GDP data)...")
    df = fred.get_series('GDPC1', observation_start='2020-01-01')
    if df is not None:
        print(f"   ✓ Retrieved {len(df)} observations")
        print(f"   Latest GDP: ${df.iloc[-1].values[0]:,.0f}B")

    print("\n" + "=" * 70)
    print("API client tests complete!")
