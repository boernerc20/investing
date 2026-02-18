"""
Technical Indicators Calculator

Calculates technical analysis indicators from price data.
Built incrementally - start with basics, add more as needed.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from typing import Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()

# Create SQLAlchemy engine for pandas
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'investing_db')
DB_USER = os.getenv('DB_USER', 'investing_user')
DB_PASSWORD = os.getenv('DB_PASSWORD')

engine = create_engine(
    f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
)


def fetch_price_data(
    symbol: str,
    days: int = 252,
    end_date: Optional[datetime] = None
) -> pd.DataFrame:
    """
    Fetch historical price data from database.

    Args:
        symbol: Stock/ETF ticker symbol
        days: Number of days of history to fetch
        end_date: End date (default: today)

    Returns:
        DataFrame with columns: date, open, high, low, close, volume
    """
    if end_date is None:
        end_date = datetime.now()

    start_date = end_date - timedelta(days=days + 100)  # Extra buffer for calculations

    query = """
        SELECT date, open, high, low, close, adjusted_close, volume
        FROM daily_prices
        WHERE symbol = %(symbol)s
          AND date >= %(start_date)s
          AND date <= %(end_date)s
        ORDER BY date ASC
    """

    df = pd.read_sql_query(
        query,
        engine,
        params={
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date
        }
    )

    if df.empty:
        raise ValueError(f"No price data found for {symbol}")

    # Convert date to datetime
    df['date'] = pd.to_datetime(df['date'])

    return df


# =============================================================================
# MOVING AVERAGES
# =============================================================================

def calculate_sma(
    df: pd.DataFrame,
    period: int,
    column: str = 'close'
) -> pd.Series:
    """
    Calculate Simple Moving Average.

    Args:
        df: DataFrame with price data
        period: Number of periods for the average
        column: Column to calculate on (default: 'close')

    Returns:
        Series with SMA values

    Example:
        >>> df = fetch_price_data('SPY', days=100)
        >>> df['sma_20'] = calculate_sma(df, 20)
        >>> df['sma_50'] = calculate_sma(df, 50)
    """
    return df[column].rolling(window=period, min_periods=period).mean()


def calculate_ema(
    df: pd.DataFrame,
    period: int,
    column: str = 'close'
) -> pd.Series:
    """
    Calculate Exponential Moving Average.

    Args:
        df: DataFrame with price data
        period: Number of periods for the average
        column: Column to calculate on (default: 'close')

    Returns:
        Series with EMA values

    Example:
        >>> df = fetch_price_data('SPY', days=100)
        >>> df['ema_12'] = calculate_ema(df, 12)
        >>> df['ema_26'] = calculate_ema(df, 26)
    """
    return df[column].ewm(span=period, adjust=False, min_periods=period).mean()


# =============================================================================
# MACD
# =============================================================================

def calculate_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = 'close'
) -> pd.DataFrame:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Standard settings: fast=12, slow=26, signal=9

    Components:
        macd_line   = EMA(fast) - EMA(slow)      → direction & momentum
        signal_line = EMA(9) of macd_line         → trigger for buy/sell
        histogram   = macd_line - signal_line     → strength of the move

    Buy signal:  macd_line crosses ABOVE signal_line (histogram goes positive)
    Sell signal: macd_line crosses BELOW signal_line (histogram goes negative)

    Args:
        df: DataFrame with price data
        fast: Fast EMA period (default: 12)
        slow: Slow EMA period (default: 26)
        signal: Signal line EMA period (default: 9)
        column: Column to calculate on (default: 'close')

    Returns:
        DataFrame with macd_line, signal_line, histogram columns added
    """
    ema_fast = df[column].ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = df[column].ewm(span=slow, adjust=False, min_periods=slow).mean()

    df['macd_line'] = ema_fast - ema_slow
    df['macd_signal'] = df['macd_line'].ewm(span=signal, adjust=False, min_periods=signal).mean()
    df['macd_histogram'] = df['macd_line'] - df['macd_signal']

    return df


# =============================================================================
# RSI
# =============================================================================

def calculate_rsi(
    df: pd.DataFrame,
    period: int = 14,
    column: str = 'close'
) -> pd.Series:
    """
    Calculate RSI (Relative Strength Index).

    Standard period: 14 days

    Scale: 0 to 100
        Above 70 = overbought (price may be due for a pullback)
        Below 30 = oversold  (price may be due for a bounce)
        Around 50 = neutral

    Formula:
        delta      = daily price change
        avg_gain   = average of up-days over period
        avg_loss   = average of down-days over period (as positive number)
        RS         = avg_gain / avg_loss
        RSI        = 100 - (100 / (1 + RS))

    Args:
        df: DataFrame with price data
        period: Lookback period (default: 14)
        column: Column to calculate on (default: 'close')

    Returns:
        Series with RSI values (0-100)
    """
    delta = df[column].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


# =============================================================================
# BOLLINGER BANDS
# =============================================================================

def calculate_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
    column: str = 'close'
) -> pd.DataFrame:
    """
    Calculate Bollinger Bands.

    Standard settings: 20-day SMA ± 2 standard deviations

    Components:
        bb_middle  = SMA(20)                  → the baseline / trend
        bb_upper   = SMA(20) + (2 × std dev) → resistance / overbought zone
        bb_lower   = SMA(20) - (2 × std dev) → support / oversold zone
        bb_width   = (upper - lower) / middle → volatility measure (%)
        bb_pct     = (close - lower) / (upper - lower)  → 0=at lower, 1=at upper

    Signals:
        Price touches upper band = overbought / resistance
        Price touches lower band = oversold / support
        Bands narrow (squeeze)   = low volatility, big move often follows
        Bands widen              = high volatility, trend is strong

    Args:
        df: DataFrame with price data
        period: SMA period for the middle band (default: 20)
        std_dev: Number of standard deviations for bands (default: 2.0)
        column: Column to calculate on (default: 'close')

    Returns:
        DataFrame with bb_middle, bb_upper, bb_lower, bb_width, bb_pct columns added
    """
    df['bb_middle'] = df[column].rolling(window=period, min_periods=period).mean()
    rolling_std = df[column].rolling(window=period, min_periods=period).std()

    df['bb_upper'] = df['bb_middle'] + (std_dev * rolling_std)
    df['bb_lower'] = df['bb_middle'] - (std_dev * rolling_std)

    # Width: how wide the bands are as % of middle band (volatility gauge)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100

    # %B: where price sits within the bands (0 = at lower, 0.5 = at middle, 1 = at upper)
    df['bb_pct'] = (df[column] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

    return df


# =============================================================================
# VOLUME ANALYSIS
# =============================================================================

def calculate_volume_indicators(
    df: pd.DataFrame,
    period: int = 20
) -> pd.DataFrame:
    """
    Calculate volume-based indicators.

    Components:
        vol_sma      = average daily volume over period (the "normal" baseline)
        vol_ratio    = today's volume / vol_sma  (is this move backed by conviction?)
        obv          = On Balance Volume — running total of volume flow
        obv_sma      = SMA of OBV (smoothed trend of volume flow)

    Vol Ratio interpretation:
        > 2.0  = very high volume — strong conviction behind the move
        1.5–2.0 = above average — meaningful participation
        0.5–1.5 = normal range
        < 0.5  = low volume — weak conviction, move may not hold

    OBV interpretation:
        Rising OBV = volume flowing into the asset (buyers in control)
        Falling OBV = volume flowing out of the asset (sellers in control)
        OBV divergence from price = early warning of potential reversal:
            Price rising but OBV falling = buyers are weakening (bearish divergence)
            Price falling but OBV rising = sellers are weakening (bullish divergence)

    Args:
        df: DataFrame with price data including 'volume' and 'close' columns
        period: Lookback period for averages (default: 20)

    Returns:
        DataFrame with vol_sma, vol_ratio, obv, obv_sma columns added
    """
    # Average volume (the baseline)
    df['vol_sma'] = df['volume'].rolling(window=period, min_periods=period).mean()

    # Volume ratio: today vs average (how unusual is today's volume?)
    df['vol_ratio'] = df['volume'] / df['vol_sma']

    # On Balance Volume: add volume on up days, subtract on down days
    direction = np.sign(df['close'].diff())   # +1 up, -1 down, 0 unchanged
    df['obv'] = (df['volume'] * direction).fillna(0).cumsum()
    df['obv_sma'] = df['obv'].rolling(window=period, min_periods=period).mean()

    return df


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def add_all_moving_averages(
    df: pd.DataFrame,
    periods: list = [10, 20, 50, 200]
) -> pd.DataFrame:
    """
    Add all common moving averages to DataFrame.

    Args:
        df: DataFrame with price data
        periods: List of periods to calculate (default: [10, 20, 50, 200])

    Returns:
        DataFrame with new SMA and EMA columns added

    Example:
        >>> df = fetch_price_data('SPY', days=252)
        >>> df = add_all_moving_averages(df)
        >>> print(df.columns)
        # Now has: sma_10, sma_20, sma_50, sma_200, ema_10, ema_20, ema_50, ema_200
    """
    for period in periods:
        df[f'sma_{period}'] = calculate_sma(df, period)
        df[f'ema_{period}'] = calculate_ema(df, period)

    return df


def get_latest_indicators(symbol: str) -> dict:
    """
    Get latest indicator values for a symbol.
    Quick snapshot for CLI testing.

    Args:
        symbol: Stock/ETF ticker

    Returns:
        Dictionary with latest values

    Example:
        >>> indicators = get_latest_indicators('SPY')
        >>> print(f"SPY: ${indicators['close']:.2f}")
        >>> print(f"SMA 50: ${indicators['sma_50']:.2f}")
    """
    # Fetch data
    df = fetch_price_data(symbol, days=252)

    # Calculate indicators
    df = add_all_moving_averages(df)

    # Get latest row
    latest = df.iloc[-1]

    return {
        'symbol': symbol,
        'date': latest['date'],
        'close': float(latest['close']),
        'sma_10': float(latest['sma_10']) if not pd.isna(latest['sma_10']) else None,
        'sma_20': float(latest['sma_20']) if not pd.isna(latest['sma_20']) else None,
        'sma_50': float(latest['sma_50']) if not pd.isna(latest['sma_50']) else None,
        'sma_200': float(latest['sma_200']) if not pd.isna(latest['sma_200']) else None,
        'ema_10': float(latest['ema_10']) if not pd.isna(latest['ema_10']) else None,
        'ema_20': float(latest['ema_20']) if not pd.isna(latest['ema_20']) else None,
        'ema_50': float(latest['ema_50']) if not pd.isna(latest['ema_50']) else None,
        'ema_200': float(latest['ema_200']) if not pd.isna(latest['ema_200']) else None,
    }


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == '__main__':
    """
    Quick CLI testing:
    python utils/technical_indicators.py
    """
    print("\n" + "="*70)
    print("TECHNICAL INDICATORS - TESTING")
    print("="*70)

    # Test with SPY
    symbol = 'SPY'
    print(f"\nFetching data for {symbol}...")

    try:
        df = fetch_price_data(symbol, days=252)
        print(f"✓ Fetched {len(df)} days of data")
        print(f"  Date range: {df['date'].min().date()} to {df['date'].max().date()}")

        # Calculate moving averages
        print(f"\nCalculating moving averages...")
        df = add_all_moving_averages(df)

        # Show latest values
        latest = df.iloc[-1]
        print(f"\n{symbol} - Latest Values ({latest['date'].date()}):")
        print(f"  Close:    ${latest['close']:>8.2f}")
        print(f"  SMA 10:   ${latest['sma_10']:>8.2f}")
        print(f"  SMA 20:   ${latest['sma_20']:>8.2f}")
        print(f"  SMA 50:   ${latest['sma_50']:>8.2f}")
        print(f"  SMA 200:  ${latest['sma_200']:>8.2f}")
        print(f"  EMA 10:   ${latest['ema_10']:>8.2f}")
        print(f"  EMA 20:   ${latest['ema_20']:>8.2f}")
        print(f"  EMA 50:   ${latest['ema_50']:>8.2f}")
        print(f"  EMA 200:  ${latest['ema_200']:>8.2f}")

        # Moving average trend
        print(f"\nMoving Average Signals:")
        if not pd.isna(latest['sma_50']):
            if latest['close'] > latest['sma_50']:
                print(f"  ✓ Price above SMA 50 (bullish)")
            else:
                print(f"  ✗ Price below SMA 50 (bearish)")
        else:
            print(f"  ⚠ Not enough data for SMA 50 (need 50+ days)")

        if not pd.isna(latest['sma_50']) and not pd.isna(latest['sma_200']):
            if latest['sma_50'] > latest['sma_200']:
                print(f"  ✓ Golden Cross territory (SMA 50 > SMA 200)")
            else:
                print(f"  ✗ Death Cross territory (SMA 50 < SMA 200)")
        else:
            print(f"  ⚠ Not enough data for SMA 200 comparison (need 200+ days)")

        # Calculate and show MACD
        print(f"\nCalculating MACD (12, 26, 9)...")
        df = calculate_macd(df)
        latest = df.iloc[-1]

        if not pd.isna(latest['macd_line']):
            print(f"\nMACD Values ({latest['date'].date()}):")
            print(f"  MACD Line:   {latest['macd_line']:>8.3f}")
            print(f"  Signal Line: {latest['macd_signal']:>8.3f}")
            print(f"  Histogram:   {latest['macd_histogram']:>8.3f}")

            print(f"\nMACD Signals:")
            if latest['macd_line'] > latest['macd_signal']:
                print(f"  ✓ MACD above signal line (bullish momentum)")
            else:
                print(f"  ✗ MACD below signal line (bearish momentum)")

            if latest['macd_line'] > 0:
                print(f"  ✓ MACD line positive (above zero line)")
            else:
                print(f"  ✗ MACD line negative (below zero line)")

            if latest['macd_histogram'] > 0:
                print(f"  ✓ Histogram positive (momentum building)")
            else:
                print(f"  ✗ Histogram negative (momentum fading)")
        else:
            print(f"  ⚠ Not enough data for MACD (need 35+ days)")

        # Calculate and show RSI
        print(f"\nCalculating RSI (14)...")
        df['rsi_14'] = calculate_rsi(df)
        latest = df.iloc[-1]

        if not pd.isna(latest['rsi_14']):
            rsi = latest['rsi_14']
            print(f"\nRSI Values ({latest['date'].date()}):")
            print(f"  RSI (14):  {rsi:>8.2f}")

            print(f"\nRSI Signal:")
            if rsi >= 70:
                print(f"  ⚠ Overbought (RSI {rsi:.1f} ≥ 70) — may be due for a pullback")
            elif rsi <= 30:
                print(f"  ⚠ Oversold (RSI {rsi:.1f} ≤ 30) — may be due for a bounce")
            elif rsi >= 60:
                print(f"  ✓ Bullish zone ({rsi:.1f}) — momentum leaning up")
            elif rsi <= 40:
                print(f"  ✗ Bearish zone ({rsi:.1f}) — momentum leaning down")
            else:
                print(f"  → Neutral ({rsi:.1f}) — no strong signal")
        else:
            print(f"  ⚠ Not enough data for RSI (need 14+ days)")

        # Calculate and show Bollinger Bands
        print(f"\nCalculating Bollinger Bands (20, 2.0)...")
        df = calculate_bollinger_bands(df)
        latest = df.iloc[-1]

        if not pd.isna(latest['bb_middle']):
            print(f"\nBollinger Bands ({latest['date'].date()}):")
            print(f"  Upper Band:  ${latest['bb_upper']:>8.2f}")
            print(f"  Middle Band: ${latest['bb_middle']:>8.2f}  (SMA 20)")
            print(f"  Lower Band:  ${latest['bb_lower']:>8.2f}")
            print(f"  Band Width:  {latest['bb_width']:>8.2f}%  (volatility)")
            print(f"  %B:          {latest['bb_pct']:>8.2f}   (0=lower, 0.5=mid, 1=upper)")

            print(f"\nBollinger Band Signals:")
            close = latest['close']
            pct_b = latest['bb_pct']

            if close >= latest['bb_upper']:
                print(f"  ⚠ Price at/above upper band — overbought, watch for pullback")
            elif close <= latest['bb_lower']:
                print(f"  ⚠ Price at/below lower band — oversold, watch for bounce")
            else:
                if pct_b >= 0.6:
                    print(f"  ✓ Price in upper half of bands ({pct_b:.2f}) — bullish")
                elif pct_b <= 0.4:
                    print(f"  ✗ Price in lower half of bands ({pct_b:.2f}) — bearish")
                else:
                    print(f"  → Price near middle of bands ({pct_b:.2f}) — neutral")

            if latest['bb_width'] < 5:
                print(f"  ⚠ Bands squeezing ({latest['bb_width']:.1f}%) — big move may be coming")
            elif latest['bb_width'] > 15:
                print(f"  ⚠ Bands very wide ({latest['bb_width']:.1f}%) — high volatility period")
            else:
                print(f"  → Normal band width ({latest['bb_width']:.1f}%)")
        else:
            print(f"  ⚠ Not enough data for Bollinger Bands (need 20+ days)")

        # Calculate and show Volume indicators
        print(f"\nCalculating Volume indicators (20-day)...")
        df = calculate_volume_indicators(df)
        latest = df.iloc[-1]

        if not pd.isna(latest['vol_sma']):
            vol_m = latest['volume'] / 1_000_000
            vol_sma_m = latest['vol_sma'] / 1_000_000

            print(f"\nVolume Values ({latest['date'].date()}):")
            print(f"  Volume:      {vol_m:>8.1f}M shares")
            print(f"  Avg Volume:  {vol_sma_m:>8.1f}M shares  (20-day avg)")
            print(f"  Vol Ratio:   {latest['vol_ratio']:>8.2f}x  (1.0 = normal)")
            print(f"  OBV:         {latest['obv']/1_000_000:>8.1f}M  (cumulative flow)")
            print(f"  OBV vs Avg:  {'Above' if latest['obv'] > latest['obv_sma'] else 'Below'} 20-day OBV average")

            print(f"\nVolume Signals:")
            ratio = latest['vol_ratio']
            if ratio >= 2.0:
                print(f"  ⚠ Very high volume ({ratio:.1f}x) — strong conviction behind move")
            elif ratio >= 1.5:
                print(f"  ✓ Above average volume ({ratio:.1f}x) — meaningful participation")
            elif ratio < 0.5:
                print(f"  ⚠ Very low volume ({ratio:.1f}x) — weak conviction, move may not hold")
            else:
                print(f"  → Normal volume ({ratio:.1f}x)")

            if latest['obv'] > latest['obv_sma']:
                print(f"  ✓ OBV above its average — buyers in control on balance")
            else:
                print(f"  ✗ OBV below its average — sellers in control on balance")
        else:
            print(f"  ⚠ Not enough data for volume indicators (need 20+ days)")

        print("\n" + "="*70)
        print("✓ TEST PASSED - MAs + MACD + RSI + Bollinger Bands + Volume!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n✗ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
