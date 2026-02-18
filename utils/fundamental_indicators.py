"""
ETF Fundamental Indicators

Provides fundamental metrics for our 11 tracked ETFs.

Data sources:
  - P/E ratios and dividend yields: hardcoded from fund provider websites
    (Vanguard, iShares, Invesco). These are approximate and updated quarterly.
    P/E changes slowly; yield changes with prices/distributions.
  - Expense ratios: hardcoded (very stable, update only when funds change them).
  - 52-week performance metrics: live from Finnhub (returns, high/low).

Why hardcoded? Finnhub's free tier returns no P/E or yield data for ETFs.
SEC EDGAR covers stocks, not ETFs directly. Hardcoded baseline values are
accurate enough for a learning/paper-trading system.

Developer note: update ETF_BASELINES each quarter by checking:
  - Vanguard: investor.vanguard.com
  - iShares: ishares.com
  - Invesco: invesco.com/us/financial-products/etfs
  - SPDR: ssga.com/us/en/individual/etfs
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
import time
import requests
from typing import Optional, Dict, Any
from datetime import date, datetime

from dotenv import load_dotenv
from loguru import logger

from database.connection import db_pool, get_db_connection

load_dotenv()

# ---------------------------------------------------------------------------
# Static ETF baseline data (approximate, updated Feb 2026)
# ---------------------------------------------------------------------------

ETF_BASELINES: Dict[str, Dict[str, Any]] = {
    # symbol: {pe, yield_pct, expense_ratio, type}
    # pe = trailing P/E of index holdings (N/A for bond ETFs → None)
    # yield_pct = indicated annual dividend yield (%)
    'BND':  {'pe': None, 'yield_pct': 4.1,  'expense_ratio': 0.03,    'type': 'bond'},
    'QQQ':  {'pe': 37.0, 'yield_pct': 0.6,  'expense_ratio': 0.20,    'type': 'growth'},
    'SPY':  {'pe': 23.5, 'yield_pct': 1.3,  'expense_ratio': 0.0945,  'type': 'blend'},
    'VIG':  {'pe': 23.0, 'yield_pct': 1.8,  'expense_ratio': 0.06,    'type': 'dividend'},
    'VTI':  {'pe': 23.0, 'yield_pct': 1.3,  'expense_ratio': 0.03,    'type': 'blend'},
    'VXUS': {'pe': 14.5, 'yield_pct': 3.0,  'expense_ratio': 0.07,    'type': 'international'},
    'XLE':  {'pe': 14.0, 'yield_pct': 3.5,  'expense_ratio': 0.09,    'type': 'sector'},
    'XLF':  {'pe': 16.5, 'yield_pct': 2.0,  'expense_ratio': 0.09,    'type': 'sector'},
    'XLI':  {'pe': 23.0, 'yield_pct': 1.5,  'expense_ratio': 0.09,    'type': 'sector'},
    'XLK':  {'pe': 33.0, 'yield_pct': 0.7,  'expense_ratio': 0.09,    'type': 'growth'},
    'XLV':  {'pe': 21.0, 'yield_pct': 1.6,  'expense_ratio': 0.09,    'type': 'sector'},
}

# P/E thresholds by ETF type — what counts as cheap/expensive
# Growth and tech ETFs historically trade at a premium (higher thresholds)
PE_THRESHOLDS: Dict[str, Dict[str, float]] = {
    'growth':        {'cheap': 28, 'fair_low': 28, 'fair_high': 40, 'expensive': 40},
    'blend':         {'cheap': 18, 'fair_low': 18, 'fair_high': 26, 'expensive': 26},
    'sector':        {'cheap': 17, 'fair_low': 17, 'fair_high': 25, 'expensive': 25},
    'dividend':      {'cheap': 18, 'fair_low': 18, 'fair_high': 26, 'expensive': 26},
    'international': {'cheap': 12, 'fair_low': 12, 'fair_high': 18, 'expensive': 18},
    'bond':          {'cheap': None, 'fair_low': None, 'fair_high': None, 'expensive': None},
}


# ---------------------------------------------------------------------------
# Finnhub supplementary data (52-week performance)
# ---------------------------------------------------------------------------

_last_finnhub_call = 0.0


def _rate_limit():
    global _last_finnhub_call
    elapsed = time.time() - _last_finnhub_call
    if elapsed < 1.1:  # ~55 calls/min, safely within 60/min limit
        time.sleep(1.1 - elapsed)
    _last_finnhub_call = time.time()


def fetch_performance_metrics(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Fetch available price-performance metrics from Finnhub for an ETF.

    Returns 52-week return, high/low, beta, short-term returns.
    These DO work for ETFs (unlike P/E which doesn't).
    """
    api_key = os.getenv('FINNHUB_API_KEY')
    if not api_key:
        logger.warning("FINNHUB_API_KEY not set — skipping performance metrics")
        return None

    _rate_limit()

    try:
        resp = requests.get(
            'https://finnhub.io/api/v1/stock/metric',
            params={'symbol': symbol, 'metric': 'all', 'token': api_key},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        m = data.get('metric', {})
        if not m:
            return None

        return {
            'week52_return':   m.get('52WeekPriceReturnDaily'),
            'week52_high':     m.get('52WeekHigh'),
            'week52_low':      m.get('52WeekLow'),
            'week13_return':   m.get('13WeekPriceReturnDaily'),
            'month1_return':   m.get('monthToDatePriceReturnDaily'),
            'ytd_return':      m.get('yearToDatePriceReturnDaily'),
            'beta':            m.get('beta'),
        }
    except Exception as e:
        logger.warning(f"Could not fetch Finnhub performance for {symbol}: {e}")
        return None


# ---------------------------------------------------------------------------
# Main metrics assembly
# ---------------------------------------------------------------------------

def get_etf_metrics(symbol: str, include_performance: bool = False) -> Optional[Dict[str, Any]]:
    """
    Return the full set of fundamental metrics for an ETF.

    Args:
        symbol: ETF ticker
        include_performance: If True, also call Finnhub for 52-week metrics

    Returns:
        Combined metrics dict, or None if symbol is unknown.
    """
    baseline = ETF_BASELINES.get(symbol)
    if baseline is None:
        logger.warning(f"No baseline data for {symbol}")
        return None

    result = {
        'symbol':        symbol,
        'pe_ratio':      baseline['pe'],
        'dividend_yield': baseline['yield_pct'],
        'expense_ratio': baseline['expense_ratio'],
        'etf_type':      baseline['type'],
        'source':        'baseline',
        'date':          date.today(),
        'week52_return': None,
        'week52_high':   None,
        'week52_low':    None,
        'ytd_return':    None,
    }

    if include_performance:
        perf = fetch_performance_metrics(symbol)
        if perf:
            result.update({k: v for k, v in perf.items() if v is not None})
            result['source'] = 'baseline+finnhub'

    return result


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def store_financial_metrics(metrics: Dict[str, Any]) -> bool:
    """Upsert ETF financial metrics into the financial_metrics table."""
    symbol = metrics.get('symbol')
    today = date.today()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO financial_metrics (
                symbol, date,
                pe_ratio, dividend_yield,
                created_at
            ) VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (symbol, date) DO UPDATE SET
                pe_ratio       = EXCLUDED.pe_ratio,
                dividend_yield = EXCLUDED.dividend_yield
        """, (symbol, today, metrics.get('pe_ratio'), metrics.get('dividend_yield')))
        conn.commit()
        logger.debug(f"Stored financial metrics for {symbol}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to store metrics for {symbol}: {e}")
        return False
    finally:
        cursor.close()
        db_pool.return_connection(conn)


# ---------------------------------------------------------------------------
# Economic data helper
# ---------------------------------------------------------------------------

def get_risk_free_rate() -> float:
    """
    Return the latest 10-year Treasury rate from the database.
    Falls back to 4.5% if unavailable.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT value FROM economic_indicators
            WHERE indicator_code = 'GS10'
            ORDER BY date DESC LIMIT 1
        """)
        row = cursor.fetchone()
        return float(row[0]) / 100.0 if row and row[0] is not None else 0.045
    except Exception:
        return 0.045
    finally:
        cursor.close()
        db_pool.return_connection(conn)
