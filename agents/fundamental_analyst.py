#!/usr/bin/env python3
"""
Fundamental Analysis Agent

Scores ETF fundamentals and produces BUY / NEUTRAL / SELL signals.
Designed specifically for ETFs — uses P/E ratio, dividend yield,
and expense ratio rather than balance-sheet ratios that apply to
individual stocks.

Scoring system (each component contributes -2 to +2 points):
    Valuation (P/E)   : -2 to +2
    Yield             : -2 to +2
    Efficiency (ER)   : -1 to +1
    ─────────────────────────────
    Total             : -5 to +5

    ≥ +4  → STRONG BUY
    +2 to +3  → BUY
    -1 to +1  → NEUTRAL
    -3 to -2  → SELL
    ≤ -4  → STRONG SELL

Usage:
    python agents/fundamental_analyst.py              # All tracked symbols
    python agents/fundamental_analyst.py SPY QQQ      # Specific symbols
    python agents/fundamental_analyst.py SPY --verbose
    python agents/fundamental_analyst.py --narrative  # Add Claude Haiku
    python agents/fundamental_analyst.py --refresh    # Force fresh API fetch
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
import argparse
from datetime import datetime
from typing import Optional

import anthropic
from dotenv import load_dotenv
from loguru import logger

from config.logging_config import setup_logging
from database.connection import db_pool, get_db_connection
from utils.fundamental_indicators import (
    get_etf_metrics,
    get_risk_free_rate,
    PE_THRESHOLDS,
    ETF_BASELINES,
)

load_dotenv()
setup_logging()


class FundamentalAnalyst:
    """
    Scores ETF fundamentals into a single actionable signal.

    For bond ETFs: yield vs risk-free rate is the primary signal.
    For equity ETFs: P/E relative to the market baseline is primary.
    """

    def analyze(self, symbol: str, force_refresh: bool = False) -> dict:
        """
        Run fundamental analysis on one symbol.

        Args:
            symbol: ETF ticker
            force_refresh: If True, also fetch live Finnhub performance data

        Returns:
            dict with signal, score, component_scores, reasons, key_values
        """
        metrics = get_etf_metrics(symbol, include_performance=force_refresh)

        if metrics is None:
            logger.error(f"{symbol}: could not retrieve fundamental metrics")
            return {
                'symbol': symbol,
                'signal': 'ERROR',
                'score': 0,
                'reasons': ['Could not retrieve fundamental data'],
                'key_values': {},
                'component_scores': {},
            }

        etf_type = metrics.get('etf_type', 'blend')
        rf_rate = get_risk_free_rate() * 100  # back to percent for display

        val_score, val_reasons   = self._score_valuation(metrics, etf_type)
        yield_score, yield_reasons = self._score_yield(metrics, etf_type, rf_rate)
        er_score, er_reasons     = self._score_expense_ratio(metrics)

        total = val_score + yield_score + er_score
        signal = self._score_to_signal(total)

        return {
            'symbol': symbol,
            'signal': signal,
            'score': total,
            'component_scores': {
                'valuation': val_score,
                'yield': yield_score,
                'expense_ratio': er_score,
            },
            'reasons': val_reasons + yield_reasons + er_reasons,
            'key_values': {
                'pe_ratio':       metrics.get('pe_ratio'),
                'pb_ratio':       metrics.get('pb_ratio'),
                'dividend_yield': metrics.get('dividend_yield'),
                'expense_ratio':  metrics.get('expense_ratio'),
                'week52_return':  metrics.get('week52_return'),
                'risk_free_rate': round(rf_rate, 2),
            },
            'etf_type': etf_type,
            'data_date': metrics.get('date') or metrics.get('fetched_at'),
        }

    def analyze_all(self, force_refresh: bool = False) -> list:
        """Analyze all tracked symbols, sorted best-to-worst."""
        symbols = self._get_tracked_symbols()
        results = []
        for symbol in symbols:
            logger.info(f"Fundamental analysis: {symbol}")
            results.append(self.analyze(symbol, force_refresh=force_refresh))
        results.sort(key=lambda x: x['score'], reverse=True)
        return results

    # -----------------------------------------------------------------------
    # SCORING
    # -----------------------------------------------------------------------

    def _score_valuation(self, metrics: dict, etf_type: str) -> tuple[int, list]:
        """
        Score the valuation component (-2 to +2).

        Bond ETFs: P/E is not meaningful, return neutral (0).
        Equity ETFs: compare P/E to type-adjusted thresholds.
        """
        if etf_type == 'bond':
            return 0, ['Valuation: P/E not applicable for bond ETF (0)']

        pe = metrics.get('pe_ratio')
        if pe is None:
            return 0, ['Valuation: P/E data unavailable (0)']

        t = PE_THRESHOLDS.get(etf_type, PE_THRESHOLDS['blend'])

        if pe < t['cheap']:
            score = 2
            reason = f'Valuation: P/E={pe:.1f} — cheap vs {etf_type} peers (threshold <{t["cheap"]}) +2'
        elif pe < t['fair_high']:
            score = 1
            reason = f'Valuation: P/E={pe:.1f} — fair value ({t["cheap"]}–{t["fair_high"]}) +1'
        elif pe < t['expensive']:
            score = -1
            reason = f'Valuation: P/E={pe:.1f} — stretched ({t["fair_high"]}–{t["expensive"]}) -1'
        else:
            score = -2
            reason = f'Valuation: P/E={pe:.1f} — expensive (>{t["expensive"]}) -2'

        return score, [reason]

    def _score_yield(self, metrics: dict, etf_type: str, rf_rate: float) -> tuple[int, list]:
        """
        Score the dividend yield component (-2 to +2).

        Bond ETFs: compared to risk-free rate (spread matters).
        Equity ETFs: absolute level + context (growth ETFs have low yield).
        """
        div_yield = metrics.get('dividend_yield')
        reasons = []

        if div_yield is None:
            return 0, ['Yield: dividend data unavailable (0)']

        if etf_type == 'bond':
            # Bond ETF: yield spread over risk-free rate
            spread = div_yield - rf_rate
            if spread > 1.5:
                score = 2
                reasons.append(f'Yield: {div_yield:.2f}% — strong spread over {rf_rate:.2f}% T-rate (+{spread:.1f}%) +2')
            elif spread > 0.3:
                score = 1
                reasons.append(f'Yield: {div_yield:.2f}% — modest spread over {rf_rate:.2f}% T-rate (+{spread:.1f}%) +1')
            elif spread >= -0.3:
                score = 0
                reasons.append(f'Yield: {div_yield:.2f}% — at parity with {rf_rate:.2f}% T-rate (0)')
            elif spread >= -1.0:
                score = -1
                reasons.append(f'Yield: {div_yield:.2f}% — below T-rate {rf_rate:.2f}% ({spread:.1f}%) -1')
            else:
                score = -2
                reasons.append(f'Yield: {div_yield:.2f}% — significantly below T-rate {rf_rate:.2f}% ({spread:.1f}%) -2')

        elif etf_type == 'growth':
            # Growth ETFs: low yield is expected — don't penalise much
            if div_yield >= 1.5:
                score = 1
                reasons.append(f'Yield: {div_yield:.2f}% — healthy for growth ETF +1')
            elif div_yield >= 0.3:
                score = 0
                reasons.append(f'Yield: {div_yield:.2f}% — typical for growth ETF (0)')
            else:
                score = 0
                reasons.append(f'Yield: {div_yield:.2f}% — minimal (expected for growth) (0)')

        else:
            # Equity blend / sector / international / dividend
            if div_yield >= 3.0:
                score = 2
                reasons.append(f'Yield: {div_yield:.2f}% — high income return +2')
            elif div_yield >= 1.5:
                score = 1
                reasons.append(f'Yield: {div_yield:.2f}% — healthy yield +1')
            elif div_yield >= 0.5:
                score = 0
                reasons.append(f'Yield: {div_yield:.2f}% — modest (0)')
            else:
                score = -1
                reasons.append(f'Yield: {div_yield:.2f}% — very low yield -1')

        return score, reasons

    def _score_expense_ratio(self, metrics: dict) -> tuple[int, list]:
        """
        Score the expense ratio component (-1 to +1).

        Lower ER = more of your money stays invested.
        """
        er = metrics.get('expense_ratio')
        if er is None:
            return 0, ['Expense Ratio: unknown (0)']

        if er <= 0.05:
            return 1, [f'Expense Ratio: {er:.4f}% — ultra-low cost +1']
        elif er <= 0.15:
            return 1, [f'Expense Ratio: {er:.4f}% — low cost +1']
        elif er <= 0.30:
            return 0, [f'Expense Ratio: {er:.4f}% — average cost (0)']
        else:
            return -1, [f'Expense Ratio: {er:.4f}% — above average cost -1']

    def _score_to_signal(self, score: int) -> str:
        if score >= 4:
            return 'STRONG BUY'
        elif score >= 2:
            return 'BUY'
        elif score >= -1:
            return 'NEUTRAL'
        elif score >= -3:
            return 'SELL'
        else:
            return 'STRONG SELL'

    # -----------------------------------------------------------------------
    # NARRATIVE (Claude Haiku)
    # -----------------------------------------------------------------------

    def get_narrative(self, result: dict) -> str:
        """
        Generate a 2-3 sentence plain-English interpretation via Claude Haiku.
        Cost: ~$0.001 per symbol.
        """
        kv = result['key_values']
        cs = result['component_scores']
        etf_type = result.get('etf_type', 'blend')

        prompt = f"""You are a concise investment analyst helping a beginner investor understand fundamental signals for an ETF.

Symbol: {result['symbol']} ({etf_type} ETF)
Overall Fundamental Signal: {result['signal']} (score {result['score']:+d}/5)

Metrics:
- P/E Ratio: {kv.get('pe_ratio') or 'N/A'}
- P/B Ratio: {kv.get('pb_ratio') or 'N/A'}
- Dividend Yield: {kv.get('dividend_yield') or 'N/A'}%
- Expense Ratio: {kv.get('expense_ratio') or 'N/A'}%
- 52-Week Return: {kv.get('week52_return') or 'N/A'}%
- Current Risk-Free Rate (10Y Treasury): {kv.get('risk_free_rate') or 'N/A'}%

Scoring reasons: {'; '.join(result['reasons'])}

Write 2-3 sentences in plain English for a beginner. Focus on what the fundamentals mean RIGHT NOW — is this ETF priced attractively? What's the income situation? Keep it specific to these numbers. No jargon without explanation."""

        try:
            client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
            msg = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=200,
                messages=[{'role': 'user', 'content': prompt}],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            return f"(Narrative unavailable: {e})"

    # -----------------------------------------------------------------------
    # DISPLAY
    # -----------------------------------------------------------------------

    def _print_verbose(self, result: dict, narrative: bool = False):
        cs = result.get('component_scores', {})
        kv = result.get('key_values', {})
        signal = result['signal']
        score = result['score']

        icons = {
            'STRONG BUY': '[++]', 'BUY': '[ +]', 'NEUTRAL': '[ ~]',
            'SELL': '[ -]', 'STRONG SELL': '[--]',
        }
        icon = icons.get(signal, '[?]')
        etf_type = result.get('etf_type', '?')

        print(f"\n{'='*70}")
        print(f"  {result['symbol']}  ({etf_type})")
        print(f"  Fundamental Signal: {icon} {signal}  (Score: {score:+d}/5)")
        print(f"{'='*70}")
        print(f"\n  Component Scores:")
        print(f"  {'Valuation (P/E)':<24} {cs.get('valuation', 0):+d}  (P/E={kv.get('pe_ratio') or 'N/A'})")
        print(f"  {'Yield':<24} {cs.get('yield', 0):+d}  ({kv.get('dividend_yield') or 'N/A'}% vs {kv.get('risk_free_rate') or 'N/A'}% 10Y)")
        print(f"  {'Expense Ratio':<24} {cs.get('expense_ratio', 0):+d}  ({kv.get('expense_ratio') or 'N/A'}%)")
        print(f"\n  Reasoning:")
        for r in result['reasons']:
            print(f"    • {r}")
        if narrative and 'narrative' in result:
            print(f"\n  Claude Analysis:")
            print(f"  {result['narrative']}")
        print()

    def _get_tracked_symbols(self) -> list:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT symbol FROM securities WHERE is_active = TRUE ORDER BY symbol")
            symbols = [row[0] for row in cursor.fetchall()]
            return symbols
        finally:
            cursor.close()
            db_pool.return_connection(conn)


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def print_summary_table(results: list):
    icons = {
        'STRONG BUY': '++', 'BUY': ' +', 'NEUTRAL': ' ~',
        'SELL': ' -', 'STRONG SELL': '--', 'ERROR': ' !',
    }
    print(f"\n{'='*70}")
    print(f"  FUNDAMENTAL ANALYSIS SUMMARY  —  {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*70}")
    print(f"  {'Symbol':<7} {'Score':>6} {'Signal':<13} {'P/E':>6} {'Yield':>6} {'ER':>6} {'Type':<12}")
    print(f"  {'-'*63}")

    for r in results:
        icon = icons.get(r['signal'], ' ?')
        kv = r.get('key_values', {})
        pe = f"{kv['pe_ratio']:.1f}" if kv.get('pe_ratio') else '---'
        yld = f"{kv['dividend_yield']:.2f}%" if kv.get('dividend_yield') else '---'
        er = f"{kv['expense_ratio']:.3f}%" if kv.get('expense_ratio') else '---'
        etype = r.get('etf_type', '?')
        print(
            f"  {r['symbol']:<7} {r['score']:>+5d}  [{icon}] {r['signal']:<12} "
            f"{pe:>6} {yld:>6} {er:>7} {etype:<12}"
        )

    print(f"{'='*70}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Fundamental Analysis Agent — ETFs')
    parser.add_argument('symbols', nargs='*', help='Symbols to analyze (default: all)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed breakdown per symbol')
    parser.add_argument('--narrative', '-n', action='store_true',
                        help='Add Claude Haiku plain-English interpretation')
    parser.add_argument('--refresh', '-r', action='store_true',
                        help='Force fresh data from Finnhub (bypass cache)')
    args = parser.parse_args()

    analyst = FundamentalAnalyst()

    if args.symbols:
        results = [analyst.analyze(s.upper(), force_refresh=args.refresh) for s in args.symbols]
    else:
        results = analyst.analyze_all(force_refresh=args.refresh)

    if args.narrative:
        print("Fetching Claude narratives (Haiku)...")
        for r in results:
            if r['signal'] != 'ERROR':
                r['narrative'] = analyst.get_narrative(r)

    if args.verbose:
        for r in results:
            analyst._print_verbose(r, narrative=args.narrative)

    print_summary_table(results)

    if args.narrative and not args.verbose:
        print("Claude Analysis:")
        print("-" * 70)
        for r in results:
            if 'narrative' in r:
                print(f"\n{r['symbol']}: {r['narrative']}")


if __name__ == '__main__':
    main()
