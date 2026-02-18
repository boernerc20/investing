#!/usr/bin/env python3
"""
Technical Analysis Agent

Combines all technical indicators into a scored signal for each symbol.
Produces an overall rating: STRONG BUY / BUY / NEUTRAL / SELL / STRONG SELL

Scoring system (each indicator contributes -2 to +2 points):
    Moving Averages  : -2 to +2
    MACD             : -2 to +2
    RSI              : -2 to +2
    Bollinger Bands  : -2 to +2
    Volume           : -2 to +2
    ─────────────────────────
    Total            : -10 to +10

    ≥ +6  → STRONG BUY
    +2 to +5  → BUY
    -1 to +1  → NEUTRAL
    -5 to -2  → SELL
    ≤ -6  → STRONG SELL

Usage:
    python agents/technical_analyst.py           # Analyze all tracked symbols
    python agents/technical_analyst.py SPY VTI   # Specific symbols
    python agents/technical_analyst.py --symbol SPY --verbose
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from loguru import logger
from config.logging_config import setup_logging
from utils.technical_indicators import (
    fetch_price_data,
    add_all_moving_averages,
    calculate_macd,
    calculate_rsi,
    calculate_bollinger_bands,
    calculate_volume_indicators,
)
from database.connection import get_db_connection
import pandas as pd
import argparse
from datetime import datetime
import anthropic
import os

load_dotenv()
setup_logging()


class TechnicalAnalyst:
    """Scores all technical indicators and produces a unified signal."""

    SIGNALS = {
        (6, 10):  'STRONG BUY',
        (2, 5):   'BUY',
        (-1, 1):  'NEUTRAL',
        (-5, -2): 'SELL',
        (-10, -6):'STRONG SELL',
    }

    def analyze(self, symbol: str, days: int = 252, verbose: bool = False) -> dict:
        """
        Run full technical analysis on a symbol.

        Args:
            symbol: Ticker symbol
            days: Days of history to analyze
            verbose: Print detailed breakdown

        Returns:
            dict with signal, score, and reasoning
        """
        try:
            df = fetch_price_data(symbol, days=days)
        except ValueError as e:
            logger.error(f"{symbol}: {e}")
            return {'symbol': symbol, 'signal': 'ERROR', 'score': 0, 'reasons': [str(e)]}

        # Calculate all indicators
        df = add_all_moving_averages(df)
        df = calculate_macd(df)
        df['rsi_14'] = calculate_rsi(df)
        df = calculate_bollinger_bands(df)
        df = calculate_volume_indicators(df)

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        # Score each component
        ma_score,  ma_reasons  = self._score_moving_averages(latest)
        macd_score, macd_reasons = self._score_macd(latest, prev)
        rsi_score,  rsi_reasons  = self._score_rsi(latest)
        bb_score,   bb_reasons   = self._score_bollinger(latest)
        vol_score,  vol_reasons  = self._score_volume(latest)

        total_score = ma_score + macd_score + rsi_score + bb_score + vol_score
        signal = self._score_to_signal(total_score)

        result = {
            'symbol': symbol,
            'date': latest['date'],
            'close': float(latest['close']),
            'signal': signal,
            'score': total_score,
            'component_scores': {
                'moving_averages': ma_score,
                'macd': macd_score,
                'rsi': rsi_score,
                'bollinger': bb_score,
                'volume': vol_score,
            },
            'reasons': ma_reasons + macd_reasons + rsi_reasons + bb_reasons + vol_reasons,
            'key_values': {
                'sma_50': round(float(latest['sma_50']), 2) if not pd.isna(latest['sma_50']) else None,
                'sma_200': round(float(latest['sma_200']), 2) if not pd.isna(latest['sma_200']) else None,
                'macd_line': round(float(latest['macd_line']), 3) if not pd.isna(latest['macd_line']) else None,
                'rsi': round(float(latest['rsi_14']), 1) if not pd.isna(latest['rsi_14']) else None,
                'bb_pct': round(float(latest['bb_pct']), 2) if not pd.isna(latest['bb_pct']) else None,
                'bb_width': round(float(latest['bb_width']), 2) if not pd.isna(latest['bb_width']) else None,
                'vol_ratio': round(float(latest['vol_ratio']), 2) if not pd.isna(latest['vol_ratio']) else None,
            }
        }

        if verbose:
            self._print_verbose(result, ma_score, macd_score, rsi_score, bb_score, vol_score, narrative=False)

        return result

    def analyze_all(self, verbose: bool = False) -> list:
        """Analyze all tracked symbols and return sorted results."""
        symbols = self._get_tracked_symbols()
        results = []

        for symbol in symbols:
            logger.info(f"Analyzing {symbol}...")
            result = self.analyze(symbol, verbose=verbose)
            results.append(result)

        # Sort by score descending (best opportunities first)
        results.sort(key=lambda x: x['score'], reverse=True)
        return results

    # -------------------------------------------------------------------------
    # SCORING METHODS
    # -------------------------------------------------------------------------

    def _score_moving_averages(self, latest) -> tuple[int, list]:
        """Score: -2 to +2"""
        score = 0
        reasons = []

        if pd.isna(latest['sma_50']) or pd.isna(latest['sma_200']):
            return 0, ['MA: insufficient data']

        # Golden/Death Cross (+1/-1)
        if latest['sma_50'] > latest['sma_200']:
            score += 1
            reasons.append('MA: Golden Cross (SMA50 > SMA200) +1')
        else:
            score -= 1
            reasons.append('MA: Death Cross (SMA50 < SMA200) -1')

        # Price vs SMA 50 (+1/-1)
        if latest['close'] > latest['sma_50']:
            score += 1
            reasons.append('MA: Price above SMA50 +1')
        else:
            score -= 1
            reasons.append('MA: Price below SMA50 -1')

        return score, reasons

    def _score_macd(self, latest, prev) -> tuple[int, list]:
        """Score: -2 to +2"""
        score = 0
        reasons = []

        if pd.isna(latest['macd_line']) or pd.isna(latest['macd_signal']):
            return 0, ['MACD: insufficient data']

        # MACD line vs signal (+1/-1)
        if latest['macd_line'] > latest['macd_signal']:
            score += 1
            reasons.append('MACD: line above signal +1')
        else:
            score -= 1
            reasons.append('MACD: line below signal -1')

        # MACD line vs zero (+1/-1)
        if latest['macd_line'] > 0:
            score += 1
            reasons.append('MACD: line positive (above zero) +1')
        else:
            score -= 1
            reasons.append('MACD: line negative (below zero) -1')

        return score, reasons

    def _score_rsi(self, latest) -> tuple[int, list]:
        """Score: -2 to +2"""
        score = 0
        reasons = []

        if pd.isna(latest['rsi_14']):
            return 0, ['RSI: insufficient data']

        rsi = latest['rsi_14']

        if rsi <= 30:
            score += 2
            reasons.append(f'RSI: oversold ({rsi:.1f}) strong buy signal +2')
        elif rsi <= 45:
            score += 1
            reasons.append(f'RSI: approaching oversold ({rsi:.1f}) +1')
        elif rsi >= 70:
            score -= 2
            reasons.append(f'RSI: overbought ({rsi:.1f}) caution -2')
        elif rsi >= 55:
            score -= 1
            reasons.append(f'RSI: approaching overbought ({rsi:.1f}) -1')
        else:
            score += 0
            reasons.append(f'RSI: neutral ({rsi:.1f}) 0')

        return score, reasons

    def _score_bollinger(self, latest) -> tuple[int, list]:
        """Score: -2 to +2"""
        score = 0
        reasons = []

        if pd.isna(latest['bb_pct']):
            return 0, ['BB: insufficient data']

        pct_b = latest['bb_pct']

        # Price position within bands
        if pct_b <= 0.05:
            score += 2
            reasons.append(f'BB: at/below lower band (%B={pct_b:.2f}) oversold +2')
        elif pct_b <= 0.3:
            score += 1
            reasons.append(f'BB: near lower band (%B={pct_b:.2f}) +1')
        elif pct_b >= 0.95:
            score -= 2
            reasons.append(f'BB: at/above upper band (%B={pct_b:.2f}) overbought -2')
        elif pct_b >= 0.7:
            score -= 1
            reasons.append(f'BB: near upper band (%B={pct_b:.2f}) -1')
        else:
            score += 0
            reasons.append(f'BB: middle of bands (%B={pct_b:.2f}) 0')

        return score, reasons

    def _score_volume(self, latest) -> tuple[int, list]:
        """Score: -2 to +2"""
        score = 0
        reasons = []

        if pd.isna(latest['vol_ratio']) or pd.isna(latest['obv']):
            return 0, ['Volume: insufficient data']

        # OBV trend vs its average (+1/-1)
        if latest['obv'] > latest['obv_sma']:
            score += 1
            reasons.append('Vol: OBV above average (buyers in control) +1')
        else:
            score -= 1
            reasons.append('Vol: OBV below average (sellers in control) -1')

        # Volume on the current price direction
        ratio = latest['vol_ratio']
        close_vs_open = latest['close'] - latest['open']

        if ratio >= 1.5 and close_vs_open > 0:
            score += 1
            reasons.append(f'Vol: high volume up day ({ratio:.1f}x) conviction +1')
        elif ratio >= 1.5 and close_vs_open < 0:
            score -= 1
            reasons.append(f'Vol: high volume down day ({ratio:.1f}x) selling pressure -1')
        else:
            reasons.append(f'Vol: normal volume ({ratio:.1f}x) 0')

        return score, reasons

    def _score_to_signal(self, score: int) -> str:
        if score >= 6:
            return 'STRONG BUY'
        elif score >= 2:
            return 'BUY'
        elif score >= -1:
            return 'NEUTRAL'
        elif score >= -5:
            return 'SELL'
        else:
            return 'STRONG SELL'

    def get_narrative(self, result: dict) -> str:
        """
        Call Claude Haiku to generate a plain-English interpretation
        of the technical analysis scores.

        Costs ~$0.001 per symbol (Haiku pricing).

        Args:
            result: Output from analyze()

        Returns:
            2-3 sentence narrative explanation
        """
        kv = result['key_values']
        cs = result['component_scores']

        prompt = f"""You are a concise investment analyst assistant helping a beginner investor understand technical signals.

Symbol: {result['symbol']}
Date: {result['date'].date()}
Price: ${result['close']:.2f}
Overall Signal: {result['signal']} (score {result['score']:+d}/10)

Indicator scores:
- Moving Averages: {cs['moving_averages']:+d}/2 (SMA50=${kv['sma_50']}, SMA200=${kv['sma_200']})
- MACD: {cs['macd']:+d}/2 (line={kv['macd_line']})
- RSI: {cs['rsi']:+d}/2 (RSI={kv['rsi']})
- Bollinger Bands: {cs['bollinger']:+d}/2 (%B={kv['bb_pct']}, width={kv['bb_width']}%)
- Volume: {cs['volume']:+d}/2 (ratio={kv['vol_ratio']}x)

Reasoning: {'; '.join(result['reasons'])}

Write 2-3 sentences in plain English for a beginner. Explain what these signals mean RIGHT NOW for this ETF and what to watch for next. Be specific about the numbers. Do not use jargon without explaining it."""

        try:
            client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text.strip()
        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            return f"(Narrative unavailable: {e})"

    def _get_tracked_symbols(self) -> list:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT symbol FROM securities WHERE is_active = TRUE ORDER BY symbol")
        symbols = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return symbols

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------

    def _print_verbose(self, result, ma_score, macd_score, rsi_score, bb_score, vol_score, narrative: bool = False):
        kv = result['key_values']
        signal = result['signal']
        score = result['score']

        signal_icons = {
            'STRONG BUY': '[++]',
            'BUY': '[ +]',
            'NEUTRAL': '[ ~]',
            'SELL': '[ -]',
            'STRONG SELL': '[--]',
        }
        icon = signal_icons.get(signal, '[?]')

        print(f"\n{'='*70}")
        print(f"  {result['symbol']}  |  ${result['close']:.2f}  |  {result['date'].date()}")
        print(f"  Signal: {icon} {signal}  (Score: {score:+d}/10)")
        print(f"{'='*70}")

        print(f"\n  Component Scores:")
        print(f"  {'Moving Averages':<20} {ma_score:+d}  (SMA50={'$'+str(kv['sma_50']) if kv['sma_50'] else 'n/a'}, SMA200={'$'+str(kv['sma_200']) if kv['sma_200'] else 'n/a'})")
        print(f"  {'MACD':<20} {macd_score:+d}  (line={kv['macd_line'] or 'n/a'})")
        print(f"  {'RSI':<20} {rsi_score:+d}  (RSI={kv['rsi'] or 'n/a'})")
        print(f"  {'Bollinger Bands':<20} {bb_score:+d}  (%B={kv['bb_pct'] or 'n/a'}, width={kv['bb_width'] or 'n/a'}%)")
        print(f"  {'Volume':<20} {vol_score:+d}  (ratio={kv['vol_ratio'] or 'n/a'}x)")

        print(f"\n  Reasoning:")
        for r in result['reasons']:
            print(f"    • {r}")

        if narrative and 'narrative' in result:
            print(f"\n  Claude Analysis:")
            print(f"  {result['narrative']}")
        print()


def print_summary_table(results: list):
    """Print a compact summary table of all analyzed symbols."""
    signal_icons = {
        'STRONG BUY': '++',
        'BUY': ' +',
        'NEUTRAL': ' ~',
        'SELL': ' -',
        'STRONG SELL': '--',
        'ERROR': ' !',
    }

    print(f"\n{'='*70}")
    print(f"  TECHNICAL ANALYSIS SUMMARY  —  {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*70}")
    print(f"  {'Symbol':<8} {'Price':>8} {'Score':>6} {'Signal':<13} {'RSI':>6} {'%B':>6} {'VolR':>6}")
    print(f"  {'-'*62}")

    for r in results:
        icon = signal_icons.get(r['signal'], ' ?')
        kv = r.get('key_values', {})
        rsi = f"{kv['rsi']:.0f}" if kv.get('rsi') else '---'
        pct_b = f"{kv['bb_pct']:.2f}" if kv.get('bb_pct') else '---'
        vol = f"{kv['vol_ratio']:.1f}x" if kv.get('vol_ratio') else '---'
        print(f"  {r['symbol']:<8} ${r['close']:>7.2f} {r['score']:>+5d}  [{icon}] {r['signal']:<12} {rsi:>6} {pct_b:>6} {vol:>6}")

    print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description='Technical Analysis Agent')
    parser.add_argument('symbols', nargs='*', help='Symbols to analyze (default: all tracked)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed breakdown per symbol')
    parser.add_argument('--narrative', '-n', action='store_true', help='Add Claude Haiku interpretation (uses API credits)')
    args = parser.parse_args()

    analyst = TechnicalAnalyst()

    if args.symbols:
        results = [analyst.analyze(s.upper()) for s in args.symbols]
    else:
        results = analyst.analyze_all()

    # Optionally fetch Claude narratives
    if args.narrative:
        print("Fetching Claude narratives (Haiku)...")
        for r in results:
            if r['signal'] != 'ERROR':
                r['narrative'] = analyst.get_narrative(r)

    # Print verbose details if requested
    if args.verbose:
        for r in results:
            cs = r.get('component_scores', {})
            analyst._print_verbose(
                r,
                cs.get('moving_averages', 0),
                cs.get('macd', 0),
                cs.get('rsi', 0),
                cs.get('bollinger', 0),
                cs.get('volume', 0),
                narrative=args.narrative
            )

    print_summary_table(results)

    # Show narratives in summary if requested but not verbose
    if args.narrative and not args.verbose:
        print("Claude Analysis:")
        print("-" * 70)
        for r in results:
            if 'narrative' in r:
                print(f"\n{r['symbol']}: {r['narrative']}")


if __name__ == '__main__':
    main()
