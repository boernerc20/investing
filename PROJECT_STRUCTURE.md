# Project Structure

Actual files as of February 2026 (Phase 3 complete).

```
investing/
│
├── agents/                             # Analysis & collection agents
│   ├── __init__.py
│   ├── agent_config.py                 # Agent model assignments (Haiku/Sonnet/Opus)
│   ├── data_collector.py               # Daily collection: prices (Stooq) + economics (FRED)
│   ├── data_collector_finnhub.py       # Finnhub-specific collection (profiles, Mondays only)
│   ├── technical_analyst.py            # ⭐ Technical analysis agent (-10 to +10)
│   ├── fundamental_analyst.py          # ⭐ Fundamental analysis agent (-5 to +5)
│   ├── risk_analyst.py                 # ⭐ Risk analysis agent (-6 to +6)
│   └── portfolio_advisor.py            # ⭐ Combined signal + Claude Sonnet daily briefing
│
├── utils/                              # Calculation libraries (called by agents)
│   ├── __init__.py
│   ├── technical_indicators.py         # SMA/EMA, MACD, RSI, Bollinger Bands, OBV
│   ├── fundamental_indicators.py       # ETF P/E, yield, expense ratio baselines + scoring
│   ├── risk_indicators.py              # Volatility, Beta, Sharpe, Drawdown, VaR, Correlation
│   ├── api_clients.py                  # Alpha Vantage, Finnhub, FRED, SEC EDGAR clients
│   └── pot_manager.py                  # Investment pots allocation calculator
│
├── database/                           # Database layer
│   ├── __init__.py
│   ├── schema.sql                      # ⭐ Full PostgreSQL + TimescaleDB schema (20+ tables)
│   └── connection.py                   # psycopg2 connection pool manager
│
├── config/                             # Configuration
│   ├── __init__.py
│   └── logging_config.py               # Loguru logging setup
│
├── scripts/                            # One-time and setup scripts
│   ├── __init__.py
│   ├── setup_database.py               # Database + user creation helper
│   ├── backfill_historical_data.py     # 5-year historical price backfill via Stooq
│   ├── setup_daily_collection.sh       # Installs systemd timer for 6 PM auto-collection
│   ├── test_apis.py                    # API connectivity test script
│   └── debug_alpha_vantage.py          # Alpha Vantage troubleshooting helper
│
├── docs/                               # Documentation
│   ├── __init__.py
│   ├── investing_101.md                # ⭐ Beginner investing concepts guide
│   └── technical_indicators.md         # ⭐ Indicator reference: formulas, ranges, SPY examples
│
├── analysis/                           # Reserved for future analysis modules
│   └── __init__.py
│
├── dashboard/                          # Reserved for future Streamlit dashboard
│   └── __init__.py
│
├── models/                             # Reserved for future ML models
│   └── __init__.py
│
├── tests/                              # Unit tests (to be expanded)
│   └── __init__.py
│
├── briefings/                          # Daily briefing text files — gitignored
├── logs/                               # Runtime logs — gitignored
│
├── README.md                           # ⭐ Project overview
├── QUICK_START.md                      # ⭐ Setup guide for new installations
├── PROJECT_STRUCTURE.md                # This file
├── CURRENT_STATUS.md                   # Session-by-session progress log
├── CLAUDE.md                           # Claude Code agent optimisation settings
├── .env.example                        # ⭐ Environment variable template (copy to .env)
├── .gitignore                          # Git ignore rules
├── requirements.txt                    # Python dependencies
├── requirements-optional.txt           # Optional extras
├── Makefile                            # Development shortcuts
└── LICENSE                             # MIT
```

---

## Key Files

| File | Purpose |
|---|---|
| `agents/portfolio_advisor.py` | Main daily command — run this every day |
| `agents/technical_analyst.py` | Technical signals for all 11 ETFs |
| `agents/fundamental_analyst.py` | Valuation signals for all 11 ETFs |
| `agents/risk_analyst.py` | Risk metrics + correlation matrix |
| `agents/data_collector.py` | Fetch fresh prices + economic data |
| `database/schema.sql` | Full DB schema — run once on setup |
| `scripts/backfill_historical_data.py` | Fetch 5 years of price history — run once |
| `utils/fundamental_indicators.py` | ETF baseline P/E/yield data — update quarterly |
| `.env.example` | Copy to `.env`, add your API keys |

---

## Data Flow

```
  STOOQ (free, no limits)
  FRED (economic indicators)     →  data_collector.py  →  PostgreSQL + TimescaleDB
  Finnhub (profiles, Mondays)                               (daily_prices,
                                                             economic_indicators,
                                                             securities tables)
                                                                    ↓
  technical_indicators.py  ─────────────────────────────►  technical_analyst.py
  fundamental_indicators.py ────────────────────────────►  fundamental_analyst.py   ─►  portfolio_advisor.py
  risk_indicators.py  ──────────────────────────────────►  risk_analyst.py                    ↓
                                                                             Claude Sonnet daily briefing
                                                                             agent_recommendations table
                                                                             briefings/YYYY-MM-DD.txt
```

---

## Database Tables

| Table | Type | Contents |
|---|---|---|
| `daily_prices` | TimescaleDB hypertable | OHLCV prices, 5 years, 11 symbols (~13,800 rows) |
| `economic_indicators` | TimescaleDB hypertable | 8 FRED series, 2 years of data |
| `securities` | Regular | ETF metadata (name, sector, description) |
| `financial_metrics` | Regular | P/E, P/B, dividend yield per symbol per date |
| `agent_recommendations` | Regular | All agent signals + reasoning (JSONB) |
| `indicator_metadata` | Regular | FRED series names, frequencies, categories |
| `financial_statements` | Regular | Quarterly financials (for future stock analysis) |
| `portfolio_holdings` | Regular | Current holdings (paper trade tracking) |
| `transactions` | Regular | Trade history |
| `investment_pots` | Regular | 4-pot allocation strategy config |
| `user_profile` | Regular | Risk tolerance, investment goals |

---

## Scoring Summary

### Technical Analyst (`-10` to `+10`)

| Component | Score | Signal |
|---|---|---|
| Moving Averages | -2 to +2 | Golden/Death Cross + price vs SMA50 |
| MACD | -2 to +2 | Line vs signal + line vs zero |
| RSI (14) | -2 to +2 | Oversold/neutral/overbought zones |
| Bollinger Bands | -2 to +2 | %B position within bands |
| Volume / OBV | -2 to +2 | OBV trend + volume conviction |

### Fundamental Analyst (`-5` to `+5`)

| Component | Score | Signal |
|---|---|---|
| Valuation (P/E) | -2 to +2 | vs type-adjusted thresholds (growth/blend/sector/bond) |
| Dividend Yield | -2 to +2 | Absolute level; for BND: spread vs 10Y Treasury |
| Expense Ratio | -1 to +1 | Cost efficiency of the fund |

### Risk Analyst (`-6` to `+6`) — higher = safer

| Component | Score | Signal |
|---|---|---|
| Volatility | -2 to +2 | Annualised std dev of daily returns |
| Max Drawdown | -2 to +2 | Worst peak-to-trough in lookback window |
| Sharpe Ratio | -2 to +2 | Risk-adjusted return vs risk-free rate |

### Portfolio Advisor (combined score `-1.0` to `+1.0`)

```
Combined = 0.40 × (Technical/10) + 0.30 × (Fundamental/5) + 0.30 × (Risk/6)
```

---

## Systemd Timer

The daily data collector runs automatically as a user service:

```
~/.config/systemd/user/investing-collector.service
~/.config/systemd/user/investing-collector.timer
```

Schedule: Mon–Fri at 18:00, `Persistent=true` (catches up if system was off).

Check status:
```bash
systemctl --user list-timers investing-collector.timer
journalctl --user -u investing-collector.service --since today
```
