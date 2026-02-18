#!/usr/bin/env python3
"""
Portfolio Advisor — Combined Signal Agent

Combines technical, fundamental, and risk signals across all tracked ETFs
and uses Claude Sonnet to produce a structured daily investment briefing.

The briefing covers:
  1. Market Overview  — what the macro/technical environment looks like
  2. Top Opportunities — best-scoring ETFs with reasoning
  3. Key Risks        — concerns to watch (volatility, drawdowns, valuation)
  4. Personal Advice  — guidance for the user's current investment phase
                        (emergency fund building → VTI/VXUS/BND accumulation)

Signal combination (weighted):
    Technical  (40%) : short-term momentum
    Fundamental(30%) : medium-term valuation
    Risk       (30%) : portfolio safety

Usage:
    python agents/portfolio_advisor.py              # Full daily briefing
    python agents/portfolio_advisor.py --scores     # Show combined scores only
    python agents/portfolio_advisor.py --save       # Save briefing to file
    python agents/portfolio_advisor.py --no-llm     # Skip Claude (scores only)
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
import argparse
import json
from datetime import datetime, date
from typing import Optional

import anthropic
from dotenv import load_dotenv
from loguru import logger

from config.logging_config import setup_logging
from database.connection import db_pool, get_db_connection
from agents.technical_analyst import TechnicalAnalyst
from agents.fundamental_analyst import FundamentalAnalyst
from agents.risk_analyst import RiskAnalyst
from utils.fundamental_indicators import get_risk_free_rate

load_dotenv()
setup_logging()


# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

WEIGHT_TECHNICAL    = 0.40
WEIGHT_FUNDAMENTAL  = 0.30
WEIGHT_RISK         = 0.30

# Normalise each score to [-1, +1] before weighting
TECH_MAX    = 10.0   # TA scores range -10 to +10
FUND_MAX    = 5.0    # FA scores range -5 to +5
RISK_MAX    = 6.0    # Risk scores range -6 to +6


class PortfolioAdvisor:
    """
    Orchestrates all three analysis agents and combines results into a
    unified per-symbol score and a holistic Claude Sonnet daily briefing.
    """

    def __init__(self):
        self.tech_agent  = TechnicalAnalyst()
        self.fund_agent  = FundamentalAnalyst()
        self.risk_agent  = RiskAnalyst()

    # -----------------------------------------------------------------------
    # Combined analysis
    # -----------------------------------------------------------------------

    def run_all(self, days: int = 252) -> list:
        """
        Run all three agents on all tracked symbols.

        Returns a list of combined result dicts, sorted by combined score.
        """
        symbols = self._get_tracked_symbols()
        rf = get_risk_free_rate()

        logger.info(f"Running full analysis on {len(symbols)} symbols...")

        combined = []
        for sym in symbols:
            logger.info(f"  Combining signals: {sym}")
            tech  = self.tech_agent.analyze(sym)
            fund  = self.fund_agent.analyze(sym)
            risk  = self.risk_agent.analyze(sym, days=days, risk_free_rate=rf)
            merged = self._combine(sym, tech, fund, risk)
            combined.append(merged)

        combined.sort(key=lambda x: x['combined_score'], reverse=True)
        return combined

    def _combine(self, symbol: str, tech: dict, fund: dict, risk: dict) -> dict:
        """
        Merge results from the three agents into a single combined record.
        """
        # Normalised scores in [-1, +1]
        t_norm = tech['score'] / TECH_MAX   if tech.get('score') is not None else 0.0
        f_norm = fund['score'] / FUND_MAX   if fund.get('score') is not None else 0.0
        r_norm = risk['score'] / RISK_MAX   if risk.get('score') is not None else 0.0

        combined = (
            WEIGHT_TECHNICAL   * t_norm +
            WEIGHT_FUNDAMENTAL * f_norm +
            WEIGHT_RISK        * r_norm
        )

        return {
            'symbol': symbol,
            'combined_score':     round(combined, 3),   # -1.0 to +1.0
            'combined_signal':    self._combined_signal(combined),
            'technical':          tech,
            'fundamental':        fund,
            'risk':               risk,
            'scores_normalised':  {
                'technical':    round(t_norm, 3),
                'fundamental':  round(f_norm, 3),
                'risk':         round(r_norm, 3),
            },
        }

    def _combined_signal(self, score: float) -> str:
        if score >= 0.4:
            return 'STRONG BUY'
        elif score >= 0.15:
            return 'BUY'
        elif score >= -0.15:
            return 'NEUTRAL'
        elif score >= -0.4:
            return 'SELL'
        else:
            return 'STRONG SELL'

    # -----------------------------------------------------------------------
    # Economic context
    # -----------------------------------------------------------------------

    def get_economic_context(self) -> dict:
        """
        Pull the latest economic indicator values from the database.
        Returns a dict used to enrich the Claude prompt.
        """
        indicators = {
            'FEDFUNDS': ('Fed Funds Rate', '%'),
            'CPIAUCSL': ('CPI Inflation (YoY proxy)', 'index'),
            'UNRATE':   ('Unemployment Rate', '%'),
            'VIXCLS':   ('VIX (Fear Index)', 'points'),
            'GS10':     ('10-Year Treasury Rate', '%'),
            'GS2':      ('2-Year Treasury Rate', '%'),
            'UMCSENT':  ('Consumer Sentiment', 'index'),
        }

        conn = get_db_connection()
        cursor = conn.cursor()
        ctx = {}

        for code, (name, unit) in indicators.items():
            try:
                cursor.execute("""
                    SELECT value, date
                    FROM economic_indicators
                    WHERE indicator_code = %s
                    ORDER BY date DESC LIMIT 1
                """, (code,))
                row = cursor.fetchone()
                if row:
                    ctx[code] = {
                        'name': name,
                        'value': float(row[0]),
                        'unit': unit,
                        'date': str(row[1]),
                    }
            except Exception as e:
                logger.warning(f"Could not fetch {code}: {e}")

        cursor.close()
        db_pool.return_connection(conn)
        return ctx

    # -----------------------------------------------------------------------
    # Claude Sonnet daily briefing
    # -----------------------------------------------------------------------

    def generate_briefing(
        self,
        combined_results: list,
        economic_context: dict,
    ) -> str:
        """
        Use Claude Sonnet to generate the daily investment briefing.

        Args:
            combined_results: Sorted list of combined analysis dicts
            economic_context: Latest economic indicator values

        Returns:
            Formatted briefing text
        """
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return "(Claude API key not set — briefing unavailable)"

        # Build compact signal summary for the prompt
        signal_rows = []
        for r in combined_results:
            t = r['technical']
            f = r['fundamental']
            ri = r['risk']
            m = ri.get('metrics', {})
            signal_rows.append(
                f"  {r['symbol']:<5} combined={r['combined_score']:+.2f} "
                f"({r['combined_signal']:<11}) | "
                f"tech={t['score']:+d}({t['signal']}) "
                f"fund={f['score']:+d}({f['signal']}) "
                f"risk={ri['score']:+d}({ri['risk_level']}) | "
                f"vol={m.get('volatility', float('nan'))*100:.0f}% "
                f"beta={m.get('beta', float('nan')):.2f}"
            )

        signals_str = "\n".join(signal_rows)

        # Economic context summary
        econ_lines = []
        for code, info in economic_context.items():
            econ_lines.append(
                f"  {info['name']}: {info['value']:.2f}{info['unit']} "
                f"(as of {info['date']})"
            )
        econ_str = "\n".join(econ_lines) if econ_lines else "  (no economic data)"

        # Top 3 and bottom 3 for the briefing
        top3 = [r['symbol'] for r in combined_results[:3]]
        bot3 = [r['symbol'] for r in combined_results[-3:]]

        prompt = f"""You are a thoughtful investment advisor producing a daily portfolio briefing for a beginner long-term investor. Today is {date.today()}.

INVESTOR PROFILE:
- Building an emergency fund ($5,000/month → $30,000 target, 6-month timeline)
- Will start investing $850/month once emergency fund is complete (~Month 7)
- Planned allocation: 100% index ETFs (VTI 50%, VXUS 30%, BND 20%)
- Risk tolerance: moderate-conservative, long-term (10+ years)
- Currently paper-trading to learn — not yet investing real money

COMBINED SIGNAL SCORES (technical 40% + fundamental 30% + risk 30%):
{signals_str}

Top signals: {', '.join(top3)}
Weak signals: {', '.join(bot3)}

ECONOMIC INDICATORS (latest available):
{econ_str}

Write a structured daily briefing with these 4 sections:

**1. Market Overview (2-3 sentences)**
Summarise the overall market environment using the economic indicators and technical signals. Is the market broadly bullish, bearish, or mixed? What's the macro backdrop? Mention VIX and interest rates specifically.

**2. Top Opportunities (3-4 bullet points)**
Highlight the best-positioned ETFs from the combined scores. For each, explain WHY it looks attractive — what combination of technical momentum, valuation, and risk profile makes it stand out. Be specific with numbers.

**3. Key Risks to Watch (3-4 bullet points)**
Identify the main concerns from the data — overvalued sectors, elevated volatility, economic warning signs. Be concrete about what numbers concern you and why.

**4. Guidance for Your Situation (2-3 sentences)**
Given that the investor is still in the emergency fund phase (not yet investing real money), what's the practical takeaway? What should they be observing or learning from today's data? When they do start investing VTI/VXUS/BND in ~6 months, does today's data change any of their thinking?

Keep it educational but concrete. Use actual numbers from the data. Avoid jargon without explanation. Maximum 400 words."""

        try:
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model='claude-sonnet-4-5-20250929',
                max_tokens=600,
                messages=[{'role': 'user', 'content': prompt}],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            logger.error(f"Claude Sonnet briefing failed: {e}")
            return f"(Briefing unavailable: {e})"

    # -----------------------------------------------------------------------
    # Database persistence
    # -----------------------------------------------------------------------

    def save_briefing(self, briefing: str, combined_results: list):
        """
        Save the daily briefing and per-symbol recommendations to the DB.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        today = date.today()

        try:
            # Save overall briefing as a pseudo-recommendation for "PORTFOLIO"
            cursor.execute("""
                INSERT INTO agent_recommendations
                    (agent_name, symbol, recommendation_type,
                     confidence_score, reasoning, supporting_data, created_at)
                VALUES ('portfolio_advisor', NULL, 'BRIEFING',
                        1.0, %s, %s, NOW())
            """, (briefing, json.dumps({
                'date': str(today),
                'top_symbols': [r['symbol'] for r in combined_results[:3]],
                'all_signals': [
                    {
                        'symbol': r['symbol'],
                        'combined_score': r['combined_score'],
                        'signal': r['combined_signal'],
                    }
                    for r in combined_results
                ],
            })))

            # Save per-symbol combined recommendation
            for r in combined_results:
                signal_map = {
                    'STRONG BUY': 'BUY', 'BUY': 'BUY',
                    'NEUTRAL': 'HOLD',
                    'SELL': 'SELL', 'STRONG SELL': 'SELL',
                }
                rec_type = signal_map.get(r['combined_signal'], 'HOLD')
                confidence = (r['combined_score'] + 1) / 2  # map -1..+1 → 0..1

                cursor.execute("""
                    INSERT INTO agent_recommendations
                        (agent_name, symbol, recommendation_type,
                         confidence_score, reasoning, supporting_data, created_at)
                    VALUES ('portfolio_advisor', %s, %s, %s, %s, %s, NOW())
                """, (
                    r['symbol'],
                    rec_type,
                    round(max(0, min(1, confidence)), 4),
                    f"Combined: {r['combined_signal']} ({r['combined_score']:+.2f}). "
                    f"Tech: {r['technical']['signal']}, "
                    f"Fund: {r['fundamental']['signal']}, "
                    f"Risk: {r['risk']['risk_level']}",
                    json.dumps({
                        'technical_score':    r['technical']['score'],
                        'fundamental_score':  r['fundamental']['score'],
                        'risk_score':         r['risk']['score'],
                        'combined_score':     r['combined_score'],
                    }),
                ))

            conn.commit()
            logger.info(f"Saved {len(combined_results)} recommendations to DB")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save recommendations: {e}")
        finally:
            cursor.close()
            conn.close()

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

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
# Combined score summary table
# ---------------------------------------------------------------------------

def print_combined_table(results: list):
    signal_icons = {
        'STRONG BUY': '++', 'BUY': ' +', 'NEUTRAL': ' ~',
        'SELL': ' -', 'STRONG SELL': '--',
    }
    print(f"\n{'='*80}")
    print(f"  COMBINED PORTFOLIO SIGNALS  —  {datetime.now().strftime('%Y-%m-%d')}")
    print(f"  Weights: Technical 40% | Fundamental 30% | Risk 30%")
    print(f"{'='*80}")
    print(
        f"  {'Symbol':<7} {'Score':>7} {'Signal':<14} "
        f"{'Tech':>5} {'Fund':>5} {'Risk':>5} {'Vol':>6} {'Beta':>6}"
    )
    print(f"  {'-'*72}")

    for r in results:
        icon = signal_icons.get(r['combined_signal'], '??')
        t = r['technical']
        f = r['fundamental']
        ri = r['risk']
        m = ri.get('metrics', {})
        vol = f"{m.get('volatility', float('nan'))*100:.0f}%"
        beta = f"{m.get('beta', float('nan')):.2f}"

        print(
            f"  {r['symbol']:<7} {r['combined_score']:>+6.2f}  [{icon}] {r['combined_signal']:<13} "
            f"{t['score']:>+4d}  {f['score']:>+4d}  {ri['score']:>+4d} "
            f"{vol:>6} {beta:>6}"
        )

    print(f"{'='*80}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Portfolio Advisor — Combined Technical + Fundamental + Risk'
    )
    parser.add_argument('--scores', '-s', action='store_true',
                        help='Print combined scores table only (skip Claude briefing)')
    parser.add_argument('--save', action='store_true',
                        help='Save briefing and recommendations to database')
    parser.add_argument('--no-llm', action='store_true',
                        help='Skip Claude call entirely (equivalent to --scores)')
    parser.add_argument('--days', '-d', type=int, default=252,
                        help='Risk lookback window in trading days (default: 252)')
    parser.add_argument('--output', '-o', type=str,
                        help='Save briefing text to a file')
    args = parser.parse_args()

    advisor = PortfolioAdvisor()

    print("Running all three analysis agents...")
    combined = advisor.run_all(days=args.days)

    print_combined_table(combined)

    skip_llm = args.scores or args.no_llm

    if not skip_llm:
        print("Fetching economic context...")
        econ = advisor.get_economic_context()

        print("Generating Claude Sonnet daily briefing...\n")
        briefing = advisor.generate_briefing(combined, econ)

        print("=" * 80)
        print("  DAILY PORTFOLIO BRIEFING")
        print("=" * 80)
        print(briefing)
        print("=" * 80)

        if args.save:
            advisor.save_briefing(briefing, combined)
            print("\nBriefing and recommendations saved to database.")

        if args.output:
            out_path = Path(args.output).expanduser()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                f"DAILY PORTFOLIO BRIEFING — {date.today()}\n"
                f"{'='*60}\n\n"
                f"{briefing}\n\n"
                f"{'='*60}\n"
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            )
            print(f"Briefing saved to: {out_path}")

    elif args.save:
        # Save score data only (no briefing text)
        advisor.save_briefing("(No briefing — scores-only run)", combined)
        print("Recommendations saved to database.")


if __name__ == '__main__':
    main()
