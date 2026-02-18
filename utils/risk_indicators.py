"""
Risk Indicators Calculator

Computes portfolio risk metrics from historical price data already in the DB.
All calculations use daily returns over configurable lookback windows.

Metrics computed:
    volatility      - Annualised standard deviation of daily returns (%)
    beta            - Systematic market risk vs SPY
    sharpe_ratio    - Risk-adjusted return (annualised, using 10Y Treasury)
    max_drawdown    - Worst peak-to-trough decline (%)
    calmar_ratio    - Annualised return / max drawdown (quality filter)
    var_95          - Value at Risk at 95% confidence, 1-day horizon (%)
    correlation     - Pairwise return correlations across all symbols
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple

from loguru import logger
from utils.technical_indicators import fetch_price_data


# ---------------------------------------------------------------------------
# Core calculations
# ---------------------------------------------------------------------------

def calculate_returns(df: pd.DataFrame) -> pd.Series:
    """Compute daily returns from a price DataFrame, indexed by date."""
    s = df.set_index('date')['close']
    return s.pct_change().dropna()


def calculate_volatility(
    returns: pd.Series, annualise: bool = True
) -> float:
    """
    Annualised volatility (standard deviation of daily returns).

    Args:
        returns: Daily return series
        annualise: If True, multiply by sqrt(252)

    Returns:
        Volatility as a fraction (e.g. 0.15 = 15%)
    """
    vol = returns.std()
    return float(vol * np.sqrt(252)) if annualise else float(vol)


def calculate_beta(
    returns: pd.Series, benchmark_returns: pd.Series
) -> float:
    """
    Beta coefficient relative to a benchmark (typically SPY).

    Beta = Cov(r, r_market) / Var(r_market)

    Args:
        returns: Daily returns for the symbol
        benchmark_returns: Daily returns for the benchmark

    Returns:
        Beta (float). 1.0 = same risk as market.
    """
    # Align series on common dates
    aligned = pd.concat([returns, benchmark_returns], axis=1).dropna()
    if aligned.shape[0] < 20:
        logger.warning("Insufficient data for beta calculation")
        return float('nan')

    r = aligned.iloc[:, 0]
    m = aligned.iloc[:, 1]

    cov_matrix = np.cov(r, m)
    return float(cov_matrix[0, 1] / cov_matrix[1, 1])


def calculate_sharpe(
    returns: pd.Series, risk_free_annual: float = 0.045
) -> float:
    """
    Annualised Sharpe ratio.

    Sharpe = (mean_daily_excess_return / std_daily_return) * sqrt(252)

    Args:
        returns: Daily return series
        risk_free_annual: Annual risk-free rate (fraction, e.g. 0.045)

    Returns:
        Annualised Sharpe ratio
    """
    if len(returns) < 20:
        return float('nan')

    rf_daily = risk_free_annual / 252
    excess = returns - rf_daily
    if excess.std() == 0:
        return float('nan')

    return float((excess.mean() / excess.std()) * np.sqrt(252))


def calculate_max_drawdown(returns: pd.Series) -> Tuple[float, pd.Timestamp, pd.Timestamp]:
    """
    Maximum drawdown: worst peak-to-trough decline.

    Args:
        returns: Daily return series

    Returns:
        (max_drawdown, peak_date, trough_date) where max_drawdown is negative.
        e.g. (-0.35, ...) means a 35% loss peak-to-trough.
    """
    cumulative = (1 + returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdowns = (cumulative - rolling_max) / rolling_max

    min_idx = drawdowns.idxmin()
    max_dd = float(drawdowns.min())

    # Find peak date (last time rolling_max was above the trough level)
    peak_candidates = rolling_max[:min_idx]
    peak_idx = peak_candidates.idxmax() if not peak_candidates.empty else min_idx

    return max_dd, peak_idx, min_idx


def calculate_calmar(
    returns: pd.Series, max_drawdown: float
) -> float:
    """
    Calmar ratio: annualised return / abs(max drawdown).

    Higher = better risk-adjusted performance.
    """
    if max_drawdown == 0 or np.isnan(max_drawdown):
        return float('nan')

    annual_return = (1 + returns.mean()) ** 252 - 1
    return float(annual_return / abs(max_drawdown))


def calculate_var_95(returns: pd.Series) -> float:
    """
    Value at Risk at 95% confidence, 1-day horizon.

    Returns: VaR as a positive fraction (e.g. 0.02 = 2% 1-day loss).
    """
    if len(returns) < 20:
        return float('nan')
    return float(-np.percentile(returns.dropna(), 5))


def calculate_correlation_matrix(
    symbols: list, days: int = 252
) -> pd.DataFrame:
    """
    Compute pairwise Pearson correlation of daily returns across symbols.

    Args:
        symbols: List of ticker symbols to include
        days: Lookback window

    Returns:
        Correlation DataFrame (symbols × symbols), or empty DataFrame on failure.
    """
    series = {}
    for sym in symbols:
        try:
            df = fetch_price_data(sym, days=days)
            series[sym] = df.set_index('date')['close'].pct_change().dropna()
        except Exception as e:
            logger.warning(f"Skipping {sym} in correlation matrix: {e}")

    if len(series) < 2:
        logger.warning("Need at least 2 symbols for correlation matrix")
        return pd.DataFrame()

    combined = pd.DataFrame(series).dropna()
    return combined.corr()


# ---------------------------------------------------------------------------
# High-level: compute all risk metrics for one symbol
# ---------------------------------------------------------------------------

def compute_risk_metrics(
    symbol: str,
    days: int = 252,
    risk_free_annual: float = 0.045,
    benchmark_symbol: str = 'SPY',
) -> Dict:
    """
    Compute the full suite of risk metrics for a symbol.

    Args:
        symbol: Ticker
        days: Lookback window in trading days (~252 = 1 year)
        risk_free_annual: Annual risk-free rate (fraction)
        benchmark_symbol: Benchmark for beta calculation

    Returns:
        dict with all computed metrics (NaN where not computable)
    """
    try:
        df = fetch_price_data(symbol, days=days)
    except ValueError as e:
        logger.error(f"{symbol}: {e}")
        return _empty_metrics(symbol, str(e))

    returns = calculate_returns(df)

    # Fetch benchmark for beta
    if symbol != benchmark_symbol:
        try:
            spy_df = fetch_price_data(benchmark_symbol, days=days)
            spy_returns = calculate_returns(spy_df)
            beta = calculate_beta(returns, spy_returns)
        except Exception:
            beta = float('nan')
    else:
        beta = 1.0  # SPY vs SPY is always 1

    vol = calculate_volatility(returns)
    sharpe = calculate_sharpe(returns, risk_free_annual)
    max_dd, peak_dt, trough_dt = calculate_max_drawdown(returns)
    calmar = calculate_calmar(returns, max_dd)
    var95 = calculate_var_95(returns)

    # Annualised return over the period
    annual_return = float((1 + returns.mean()) ** 252 - 1)

    return {
        'symbol': symbol,
        'lookback_days': len(returns),
        'annual_return': annual_return,
        'volatility': vol,
        'beta': beta,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_dd,
        'max_drawdown_peak': peak_dt,
        'max_drawdown_trough': trough_dt,
        'calmar_ratio': calmar,
        'var_95': var95,
        'risk_free_rate': risk_free_annual,
    }


def _empty_metrics(symbol: str, error: str) -> dict:
    return {
        'symbol': symbol,
        'error': error,
        'annual_return': float('nan'),
        'volatility': float('nan'),
        'beta': float('nan'),
        'sharpe_ratio': float('nan'),
        'max_drawdown': float('nan'),
        'calmar_ratio': float('nan'),
        'var_95': float('nan'),
    }
