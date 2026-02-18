#!/usr/bin/env python3
"""
Risk Analysis Agent

Computes and scores portfolio risk metrics for all tracked ETFs.
Uses historical price data already in the database — no external API needed.

Risk Score (-6 to +6, higher = safer / lower risk):
    Volatility  : -2 to +2  (lower vol = higher score)
    Max Drawdown: -2 to +2  (smaller drawdown = higher score)
    Sharpe Ratio: -2 to +2  (higher Sharpe = higher score)
    ─────────────────────────────
    Total       : -6 to +6

Risk Level:
    +4 to +6  → CONSERVATIVE  (low risk)
    +1 to +3  → MODERATE
    -2 to  0  → ELEVATED
    -6 to -3  → HIGH RISK

Usage:
    python agents/risk_analyst.py               # All symbols, 1-year window
    python agents/risk_analyst.py SPY VTI BND   # Specific symbols
    python agents/risk_analyst.py --verbose     # Full metric breakdown
    python agents/risk_analyst.py --corr        # Show correlation matrix
    python agents/risk_analyst.py --days 504    # 2-year lookback
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
import math
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from loguru import logger

from config.logging_config import setup_logging
from database.connection import db_pool, get_db_connection
from utils.risk_indicators import (
    compute_risk_metrics,
    calculate_correlation_matrix,
)
from utils.fundamental_indicators import get_risk_free_rate

load_dotenv()
setup_logging()


class RiskAnalyst:
    """
    Scores each ETF on risk dimensions and produces a risk-level assessment.

    Higher score = LOWER risk (safer for a conservative long-term investor).
    """

    def analyze(
        self,
        symbol: str,
        days: int = 252,
        risk_free_rate: Optional[float] = None,
    ) -> dict:
        """
        Full risk analysis for one symbol.

        Args:
            symbol: ETF ticker
            days: Lookback window in trading days
            risk_free_rate: Annual rate as fraction; fetched from DB if None

        Returns:
            dict with risk level, score, component scores, reasoning
        """
        rf = risk_free_rate if risk_free_rate is not None else get_risk_free_rate()
        metrics = compute_risk_metrics(symbol, days=days, risk_free_annual=rf)

        if 'error' in metrics:
            return {
                'symbol': symbol,
                'risk_level': 'ERROR',
                'score': 0,
                'component_scores': {},
                'reasons': [metrics['error']],
                'metrics': metrics,
            }

        vol_score, vol_reasons   = self._score_volatility(metrics['volatility'])
        dd_score, dd_reasons     = self._score_max_drawdown(metrics['max_drawdown'])
        sh_score, sh_reasons     = self._score_sharpe(metrics['sharpe_ratio'])

        total = vol_score + dd_score + sh_score
        risk_level = self._score_to_level(total)

        return {
            'symbol': symbol,
            'risk_level': risk_level,
            'score': total,
            'component_scores': {
                'volatility': vol_score,
                'max_drawdown': dd_score,
                'sharpe': sh_score,
            },
            'reasons': vol_reasons + dd_reasons + sh_reasons,
            'metrics': metrics,
        }

    def analyze_all(self, days: int = 252) -> list:
        """Analyze all tracked symbols. Returns list sorted safest-first."""
        symbols = self._get_tracked_symbols()
        rf = get_risk_free_rate()
        results = []
        for symbol in symbols:
            logger.info(f"Risk analysis: {symbol}")
            results.append(self.analyze(symbol, days=days, risk_free_rate=rf))
        # Sort by score descending (safest first)
        results.sort(key=lambda x: x['score'], reverse=True)
        return results

    # -----------------------------------------------------------------------
    # SCORING
    # -----------------------------------------------------------------------

    def _score_volatility(self, vol: float) -> tuple[int, list]:
        """
        Score annualised volatility (-2 to +2). Lower vol = higher score.

        Reference: US bond ETFs ~4-8%, broad equity ~12-18%, sector/growth ~20-30%+
        """
        if math.isnan(vol):
            return 0, ['Volatility: insufficient data (0)']

        pct = vol * 100  # convert to %
        if pct < 8:
            score, label = 2, 'very low (bonds/defensive)'
        elif pct < 14:
            score, label = 1, 'low-moderate'
        elif pct < 20:
            score, label = 0, 'market-average'
        elif pct < 28:
            score, label = -1, 'elevated'
        else:
            score, label = -2, 'high'

        return score, [f'Volatility: {pct:.1f}% annualised — {label} {score:+d}']

    def _score_max_drawdown(self, max_dd: float) -> tuple[int, list]:
        """
        Score maximum drawdown (-2 to +2). Smaller drawdown = higher score.
        max_dd is negative (e.g. -0.35 = -35%).
        """
        if math.isnan(max_dd):
            return 0, ['Max Drawdown: insufficient data (0)']

        pct = max_dd * 100  # negative %

        if pct > -10:
            score, label = 2, 'minimal drawdown'
        elif pct > -20:
            score, label = 1, 'moderate drawdown'
        elif pct > -30:
            score, label = 0, 'significant drawdown'
        elif pct > -40:
            score, label = -1, 'large drawdown'
        else:
            score, label = -2, 'severe drawdown'

        return score, [f'Max Drawdown: {pct:.1f}% — {label} {score:+d}']

    def _score_sharpe(self, sharpe: float) -> tuple[int, list]:
        """
        Score the Sharpe ratio (-2 to +2). Higher Sharpe = higher score.
        """
        if math.isnan(sharpe):
            return 0, ['Sharpe: insufficient data (0)']

        if sharpe > 1.5:
            score, label = 2, 'excellent risk-adjusted return'
        elif sharpe > 0.5:
            score, label = 1, 'good risk-adjusted return'
        elif sharpe > 0.0:
            score, label = 0, 'modest risk-adjusted return'
        elif sharpe > -0.5:
            score, label = -1, 'below risk-free return'
        else:
            score, label = -2, 'poor risk-adjusted return'

        return score, [f'Sharpe Ratio: {sharpe:.2f} — {label} {score:+d}']

    def _score_to_level(self, score: int) -> str:
        if score >= 4:
            return 'CONSERVATIVE'
        elif score >= 1:
            return 'MODERATE'
        elif score >= -2:
            return 'ELEVATED'
        else:
            return 'HIGH RISK'

    # -----------------------------------------------------------------------
    # DISPLAY
    # -----------------------------------------------------------------------

    def _print_verbose(self, result: dict):
        m = result['metrics']
        cs = result.get('component_scores', {})
        score = result['score']
        level = result['risk_level']

        level_icons = {
            'CONSERVATIVE': '[low]',
            'MODERATE': '[med]',
            'ELEVATED': '[hi!]',
            'HIGH RISK': '[!!!]',
        }
        icon = level_icons.get(level, '[???]')

        print(f"\n{'='*70}")
        print(f"  {result['symbol']}  —  Risk Level: {icon} {level}  (Score: {score:+d}/6)")
        print(f"{'='*70}")
        print(f"\n  Risk Component Scores:")
        print(f"  {'Volatility':<24} {cs.get('volatility', 0):+d}  ({m.get('volatility', float('nan'))*100:.1f}% annualised)")
        print(f"  {'Max Drawdown':<24} {cs.get('max_drawdown', 0):+d}  ({m.get('max_drawdown', float('nan'))*100:.1f}%)")
        print(f"  {'Sharpe Ratio':<24} {cs.get('sharpe', 0):+d}  ({m.get('sharpe_ratio', float('nan')):.2f})")

        print(f"\n  Full Metrics:")
        print(f"    Annual Return    : {m.get('annual_return', float('nan'))*100:+.1f}%")
        print(f"    Beta (vs SPY)    : {m.get('beta', float('nan')):.2f}")
        print(f"    VaR 95% (1-day)  : -{m.get('var_95', float('nan'))*100:.2f}%")
        print(f"    Calmar Ratio     : {m.get('calmar_ratio', float('nan')):.2f}")

        dd_peak = m.get('max_drawdown_peak')
        dd_trough = m.get('max_drawdown_trough')
        if dd_peak and dd_trough:
            try:
                peak_str = dd_peak.strftime('%Y-%m-%d') if hasattr(dd_peak, 'strftime') else str(dd_peak)[:10]
                trough_str = dd_trough.strftime('%Y-%m-%d') if hasattr(dd_trough, 'strftime') else str(dd_trough)[:10]
                print(f"    Worst Drawdown   : {peak_str} → {trough_str}")
            except Exception:
                pass

        print(f"\n  Reasoning:")
        for r in result['reasons']:
            print(f"    • {r}")
        print()

    def _get_tracked_symbols(self) -> list:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT symbol FROM securities WHERE is_active = TRUE ORDER BY symbol")
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()
            db_pool.return_connection(conn)


# ---------------------------------------------------------------------------
# Summary tables
# ---------------------------------------------------------------------------

def print_summary_table(results: list):
    level_icons = {
        'CONSERVATIVE': 'LOW',
        'MODERATE': 'MED',
        'ELEVATED': 'HI!',
        'HIGH RISK': '!!!',
        'ERROR': 'ERR',
    }
    print(f"\n{'='*75}")
    print(f"  RISK ANALYSIS SUMMARY  —  {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*75}")
    print(f"  {'Symbol':<7} {'Score':>6} {'Risk Level':<14} {'Volatility':>10} {'Beta':>6} {'Sharpe':>7} {'Max DD':>8}")
    print(f"  {'-'*68}")

    for r in results:
        m = r.get('metrics', {})
        icon = level_icons.get(r['risk_level'], '???')
        vol = f"{m.get('volatility', float('nan'))*100:.1f}%"
        beta = f"{m.get('beta', float('nan')):.2f}"
        sharpe = f"{m.get('sharpe_ratio', float('nan')):.2f}"
        dd = f"{m.get('max_drawdown', float('nan'))*100:.1f}%"

        print(
            f"  {r['symbol']:<7} {r['score']:>+5d}  [{icon}] {r['risk_level']:<13} "
            f"{vol:>10} {beta:>6} {sharpe:>7} {dd:>8}"
        )

    print(f"{'='*75}\n")


def print_correlation_matrix(corr: 'pd.DataFrame'):
    """Print a compact correlation heatmap using ASCII characters."""
    if corr.empty:
        print("(Correlation matrix unavailable)")
        return

    symbols = list(corr.columns)
    print(f"\n{'='*75}")
    print(f"  RETURN CORRELATION MATRIX  (1-year daily returns)")
    print(f"  1.00=perfect  0.90+=high  0.50-0.89=medium  <0.50=low")
    print(f"{'='*75}")

    # Header row
    col_w = 6
    header = f"  {'':>6}" + "".join(f" {s:>{col_w}}" for s in symbols)
    print(header)

    for row_sym in symbols:
        row_str = f"  {row_sym:>6}"
        for col_sym in symbols:
            val = corr.loc[row_sym, col_sym]
            row_str += f" {val:>{col_w}.2f}"
        print(row_str)

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Risk Analysis Agent')
    parser.add_argument('symbols', nargs='*', help='Symbols to analyze (default: all)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show full metric breakdown per symbol')
    parser.add_argument('--corr', '-c', action='store_true',
                        help='Show correlation matrix for all tracked symbols')
    parser.add_argument('--days', '-d', type=int, default=252,
                        help='Lookback window in trading days (default: 252 = 1yr)')
    args = parser.parse_args()

    analyst = RiskAnalyst()

    if args.symbols:
        rf = get_risk_free_rate()
        results = [analyst.analyze(s.upper(), days=args.days, risk_free_rate=rf)
                   for s in args.symbols]
    else:
        results = analyst.analyze_all(days=args.days)

    if args.verbose:
        for r in results:
            analyst._print_verbose(r)

    print_summary_table(results)

    if args.corr:
        symbols_for_corr = (
            [s.upper() for s in args.symbols] if args.symbols
            else analyst._get_tracked_symbols()
        )
        print("Computing correlation matrix...")
        corr = calculate_correlation_matrix(symbols_for_corr, days=args.days)
        print_correlation_matrix(corr)


if __name__ == '__main__':
    main()
