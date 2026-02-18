# Investment Portfolio Analysis System

A personal investment research system that collects market data, runs technical/fundamental/risk analysis on 11 tracked ETFs, and produces a daily AI-written briefing using Claude.

Built for long-term index fund investing — designed to help understand markets during a paper-trading phase before deploying real capital.

---

## What It Does

**Automated daily data collection** (runs at 6 PM weekdays via systemd):
- ETF prices for 11 symbols via Stooq (no API rate limits)
- 8 FRED economic indicators (Fed rate, inflation, unemployment, VIX, yield curve, GDP, consumer sentiment)
- ETF profiles via Finnhub

**Three analysis agents** that score each ETF independently:

| Agent | Question answered | Score range |
|---|---|---|
| Technical Analyst | Is the timing right? (momentum, trend) | -10 to +10 |
| Fundamental Analyst | Is the price fair? (P/E, yield, cost) | -5 to +5 |
| Risk Analyst | How dangerous is this to hold? | -6 to +6 |

**Portfolio Advisor** — combines all three into a weighted daily briefing written by Claude Sonnet, covering market overview, top opportunities, key risks, and personalised guidance.

---

## ETFs Tracked

| Symbol | Name | Type |
|---|---|---|
| VTI | Vanguard Total Stock Market | Blend |
| VXUS | Vanguard Total International | International |
| BND | Vanguard Total Bond Market | Bond |
| SPY | SPDR S&P 500 | Blend |
| QQQ | Invesco NASDAQ-100 | Growth |
| VIG | Vanguard Dividend Appreciation | Dividend |
| XLE | Energy Select Sector SPDR | Sector |
| XLF | Financial Select Sector SPDR | Sector |
| XLI | Industrial Select Sector SPDR | Sector |
| XLK | Technology Select Sector SPDR | Growth |
| XLV | Health Care Select Sector SPDR | Sector |

---

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL with TimescaleDB extension
- API keys: [FRED](https://fred.stlouisfed.org/docs/api/api_key.html), [Finnhub](https://finnhub.io/register), [Anthropic](https://console.anthropic.com/)

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/investing.git
cd investing

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys and database credentials

# 5. Set up PostgreSQL database
createdb investing_db
psql -U your_user -d investing_db -f database/schema.sql

# 6. Backfill 5 years of historical price data
python scripts/backfill_historical_data.py

# 7. Set up automated daily collection (Linux systemd)
bash scripts/setup_daily_collection.sh
```

### Run your first analysis

```bash
# Full daily briefing — all 3 agents + Claude Sonnet narrative
python agents/portfolio_advisor.py --save --output briefings/$(date +%Y-%m-%d).txt

# Quick combined scores table (no Claude API call)
python agents/portfolio_advisor.py --scores
```

---

## Daily Usage

After the 6 PM timer runs (or a manual `python agents/data_collector.py`):

```bash
source venv/bin/activate

# THE daily command
python agents/portfolio_advisor.py --save --output briefings/$(date +%Y-%m-%d).txt
```

### Individual Agents

```bash
# Technical analysis — all 11 ETFs
python agents/technical_analyst.py

# Technical — single symbol, verbose + Claude Haiku narrative
python agents/technical_analyst.py SPY --verbose --narrative

# Fundamental analysis — all ETFs
python agents/fundamental_analyst.py --verbose

# Risk analysis — all ETFs with correlation matrix
python agents/risk_analyst.py --corr

# Risk — 2-year lookback window
python agents/risk_analyst.py --days 504 --verbose
```

---

## Sample Output

```
================================================================================
  COMBINED PORTFOLIO SIGNALS  —  2026-02-17
  Weights: Technical 40% | Fundamental 30% | Risk 30%
================================================================================
  Symbol    Score Signal          Tech  Fund  Risk    Vol   Beta
  ------------------------------------------------------------------------
  VXUS     +0.51  [++] STRONG BUY      +3    +4    +3    16%   0.67
  XLE      +0.47  [++] STRONG BUY      +3    +5    +1    25%   0.78
  VIG      +0.36  [ +] BUY             +2    +3    +2    16%   0.75
  BND      +0.24  [ +] BUY             +2    +1    +2     4%   0.02
  VTI      +0.14  [ ~] NEUTRAL         -2    +2    +2    19%   1.00
================================================================================
```

Followed by a structured 4-section briefing from Claude covering market overview, top opportunities, key risks, and guidance for the current investment phase.

---

## Project Structure

```
investing/
├── agents/
│   ├── data_collector.py          # Automated data collection (Stooq + FRED + Finnhub)
│   ├── technical_analyst.py       # Technical indicators agent (-10 to +10)
│   ├── fundamental_analyst.py     # ETF fundamentals agent (-5 to +5)
│   ├── risk_analyst.py            # Portfolio risk agent (-6 to +6)
│   └── portfolio_advisor.py       # Combined signal + Claude Sonnet daily briefing
│
├── utils/
│   ├── technical_indicators.py    # SMA, EMA, MACD, RSI, Bollinger Bands, Volume/OBV
│   ├── fundamental_indicators.py  # ETF P/E, yield, expense ratio data + scoring
│   ├── risk_indicators.py         # Volatility, Beta, Sharpe, Max Drawdown, VaR, Corr
│   └── api_clients.py             # Alpha Vantage, Finnhub, FRED, SEC EDGAR clients
│
├── database/
│   ├── schema.sql                 # PostgreSQL + TimescaleDB schema (20+ tables)
│   └── connection.py              # Connection pool manager
│
├── config/
│   └── logging_config.py          # Loguru setup
│
├── scripts/
│   ├── setup_database.py          # Database initialisation
│   ├── backfill_historical_data.py # 5-year historical price backfill via Stooq
│   └── setup_daily_collection.sh  # systemd timer installation
│
├── docs/
│   ├── investing_101.md           # Beginner investing guide
│   └── technical_indicators.md    # Indicator reference with formulas + examples
│
├── briefings/                     # Daily briefing text files (gitignored)
├── logs/                          # Runtime logs (gitignored)
├── .env.example                   # Environment variables template
└── requirements.txt
```

---

## Technical Indicators

The technical agent scores 5 indicator groups:

| Indicator | Signal logic | Score |
|---|---|---|
| Moving Averages | SMA50 vs SMA200 (Golden/Death Cross), price vs SMA50 | -2 to +2 |
| MACD | Line vs signal, line vs zero | -2 to +2 |
| RSI (14) | Oversold (<30) = buy, overbought (>70) = caution | -2 to +2 |
| Bollinger Bands | %B position within bands | -2 to +2 |
| Volume / OBV | OBV trend, volume conviction on up/down days | -2 to +2 |

## Risk Metrics

Computed from 1-year (default) or 2-year historical price data:

| Metric | Description |
|---|---|
| Volatility | Annualised standard deviation of daily returns |
| Beta | Systematic risk vs SPY benchmark |
| Sharpe Ratio | Risk-adjusted return (vs 10-year Treasury rate) |
| Max Drawdown | Worst peak-to-trough decline with exact dates |
| VaR 95% | Expected 1-day loss at 95% confidence |
| Correlation Matrix | Pairwise return correlations across all 11 ETFs |

---

## Data Sources

| Source | Used for | Cost |
|---|---|---|
| Stooq | Daily ETF prices (primary) | Free, no limits |
| FRED | 8 economic indicator series | Free |
| Finnhub | ETF profiles, 52-week performance | Free (60 req/min) |
| Anthropic | Claude Haiku (narratives) + Sonnet (briefings) | Pay-per-use |

Alpha Vantage and SEC EDGAR clients are also included but not in the primary data pipeline.

---

## Database

PostgreSQL 18 + TimescaleDB. Key tables:

- `daily_prices` — TimescaleDB hypertable, 13,800+ records (5 years, 11 symbols)
- `economic_indicators` — TimescaleDB hypertable, 8 FRED series
- `financial_metrics` — Fundamental metrics per symbol per date
- `agent_recommendations` — All agent signals with reasoning (JSONB)
- `securities` — ETF metadata

---

## Disclaimer

This is a personal educational tool, not financial advice. All signals are backward-looking. Past performance does not guarantee future results. Do your own research before making investment decisions.

---

## License

MIT — see `LICENSE`
