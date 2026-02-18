# Investment Portfolio System - Current Status

**Last Updated**: 2026-02-17 (Session 3)

---

## ✅ Completed

### Phase 1: Infrastructure (Session 1 — Feb 11)
- [x] Project structure, Python 3.12 venv, all dependencies
- [x] PostgreSQL 18.1 + TimescaleDB, full schema (20+ tables)
- [x] Database seeded: 11 ETFs, 8 economic indicators, user profile, 4 pots
- [x] API clients: Alpha Vantage, Finnhub, FRED, SEC EDGAR
- [x] Data collector agent (daily prices, economic indicators, company profiles)
- [x] Documentation: README, QUICK_START, PROJECT_STRUCTURE, investing_101

### Phase 2: Data & Automation (Session 2 — Feb 16)
- [x] **Historical backfill**: 5 years of data via Stooq (13,805 records, 11 symbols)
- [x] **Daily auto-collection**: systemd timer, Mon–Fri at 6 PM, `Persistent=true`
  - Prices via Stooq (no API limits), FRED for economics, Finnhub profiles Mondays only
  - Timer: `~/.config/systemd/user/investing-collector.{service,timer}`
- [x] **Technical indicators library** (`utils/technical_indicators.py`)
  - SMA 10/20/50/200, EMA 10/20/50/200
  - MACD (12, 26, 9) — line, signal, histogram
  - RSI (14) — with overbought/oversold zones
  - Bollinger Bands (20, 2.0) — upper/lower/middle, %B, band width
  - Volume analysis — vol ratio, OBV, OBV SMA
- [x] **Technical analyst agent** (`agents/technical_analyst.py`)
  - Scores all 5 indicator groups (-2 to +2 each, total -10 to +10)
  - Signals: STRONG BUY / BUY / NEUTRAL / SELL / STRONG SELL
  - `--verbose` flag: full per-symbol reasoning breakdown
  - `--narrative` flag: Claude Haiku plain-English interpretation via API
- [x] **Indicator documentation** (`docs/technical_indicators.md`)
  - Running reference with explanations, formulas, SPY examples for each indicator
- [x] **Anthropic API** connected (Haiku for narratives, $5 credits loaded)

---

## 📊 Current System State

### Database
- Securities tracked: 11 ETFs (BND, QQQ, SPY, VIG, VTI, VXUS, XLE, XLF, XLI, XLK, XLV)
- Price records: 13,805 (5 years, Feb 2021 – Feb 2026)
- Economic indicators: 8 series, 2 years of data
- Daily timer: runs tomorrow (Tue Feb 17) at 6 PM

### Data Sources
| Source | Used For | Limit |
|--------|---------|-------|
| Stooq | Daily prices (timer + backfill) | None |
| FRED | Economic indicators | Generous |
| Finnhub | Company profiles (Mondays) | 60/min |
| Alpha Vantage | Available but not in critical path | 25/day |

### Sample Output (Feb 16, 2026)
```
Symbol   Price   Score  Signal    RSI    %B    VolR
VIG    $227.26    +4   BUY        56   0.67   1.1x
VXUS   $ 82.40    +3   BUY        66   0.84   1.2x
XLI    $174.17    +3   BUY        69   0.87   1.0x
QQQ    $601.92    -1   NEUTRAL    41   0.15   1.1x
SPY    $681.75    -1   NEUTRAL    44   0.18   1.1x
XLK    $139.56    -1   NEUTRAL    43   0.23   1.1x
```

### Phase 3: Multi-Agent Analysis (Session 3 — Feb 17)
- [x] **Fundamental Analysis**: `utils/fundamental_indicators.py` + `agents/fundamental_analyst.py`
  - ETF-appropriate scoring: P/E (type-adjusted thresholds), dividend yield, expense ratio
  - Baseline data hardcoded from fund providers (Finnhub free tier has no ETF P/E)
  - Scores -5 to +5: STRONG BUY / BUY / NEUTRAL / SELL / STRONG SELL
  - Claude Haiku narrative via `--narrative` flag
- [x] **Risk Analysis**: `utils/risk_indicators.py` + `agents/risk_analyst.py`
  - Volatility (annualised), Beta (vs SPY), Sharpe ratio, Max Drawdown, VaR 95%, Calmar
  - Correlation matrix across all 11 ETFs (`--corr` flag)
  - Risk levels: CONSERVATIVE / MODERATE / ELEVATED / HIGH RISK
  - All computed from existing DB price data — no external API
- [x] **Portfolio Advisor**: `agents/portfolio_advisor.py`
  - Combines tech (40%) + fundamental (30%) + risk (30%) into unified score
  - Claude Sonnet daily briefing: market overview, opportunities, risks, user guidance
  - Saves briefing + per-symbol recommendations to `agent_recommendations` table
  - `--scores` flag for quick table view, `--save` to persist, `--output` for file

---

## 📊 Current System State (Feb 17, 2026)

### Sample Output (Feb 17, 2026 — combined signals)
```
Symbol    Score Signal          Tech  Fund  Risk    Vol   Beta
VXUS     +0.51  STRONG BUY      +3    +4    +3    16%   0.67
XLE      +0.47  STRONG BUY      +3    +5    +1    25%   0.78
VIG      +0.36  BUY             +2    +3    +2    16%   0.75
XLI      +0.36  BUY             +2    +3    +2    19%   0.89
BND      +0.24  BUY             +2    +1    +2     4%   0.02
VTI      +0.14  NEUTRAL         -2    +2    +2    19%   1.00
QQQ      +0.07  NEUTRAL         -1    +1    +1    23%   1.17
```

---

## 🎯 Phase 4: Next Session

---

## 📋 Backlog (Phase 4+)

### Dashboard (Month 2)
- [ ] Streamlit dashboard — portfolio overview, charts, agent signals
- [ ] Price charts with indicators overlaid
- [ ] Daily briefing page (render the portfolio_advisor briefing)

### Automation & Notifications (Month 2)
- [ ] Wire portfolio_advisor into the daily systemd timer (post-collection)
- [ ] Daily summary email/notification after 6 PM collection
- [ ] Alert on significant signal changes (e.g. Death Cross, RSI < 30)

### Advanced (Month 3+)
- [ ] Backtesting — test the scoring system against historical data
- [ ] Opus portfolio optimizer — full allocation recommendations
- [ ] Sentiment analysis — Finnhub news → Claude Haiku sentiment score
- [ ] Update ETF_BASELINES in fundamental_indicators.py quarterly

---

## 💰 Investment Timeline (Unchanged)

**Now – Month 6**: Emergency fund ($5k/month → $30k). Paper trade with this system.
**Month 7+**: Begin investing $850/month. 100% index funds (VTI, VXUS, BND).
**Month 12+**: Full 4-pot strategy, guided by this system.

---

## 🔧 Key Commands

```bash
# --- DAILY BRIEFING (run these after market close) ---

# Full daily briefing: all 3 agents + Claude Sonnet narrative
python agents/portfolio_advisor.py --save

# Quick combined scores table (no Claude call)
python agents/portfolio_advisor.py --scores

# Save briefing to a text file
python agents/portfolio_advisor.py --output briefing.txt

# --- INDIVIDUAL AGENTS ---

# Technical analysis — all 11 ETFs
python agents/technical_analyst.py

# Technical — specific symbol, verbose + Claude narrative
python agents/technical_analyst.py SPY --verbose --narrative

# Fundamental analysis — all ETFs
python agents/fundamental_analyst.py

# Fundamental — verbose with Claude Haiku narrative
python agents/fundamental_analyst.py --verbose --narrative

# Risk analysis — all ETFs
python agents/risk_analyst.py

# Risk — verbose with full metrics + correlation matrix
python agents/risk_analyst.py --verbose --corr

# Risk — 2-year lookback
python agents/risk_analyst.py --days 504

# --- DATA COLLECTION ---

# Collect fresh data manually
python agents/data_collector.py

# Check timer status
systemctl --user list-timers investing-collector.timer

# Check database
psql -U investing_user -d investing_db -h localhost
```

---

## 🚀 How to Start Next Session

Tell Claude Code:
> "Check CURRENT_STATUS.md and let's build the Streamlit dashboard"

The system will pick up exactly where we left off.
