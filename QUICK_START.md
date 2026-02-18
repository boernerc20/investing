# Quick Start Guide

Get the system running from a fresh clone.

---

## Prerequisites

- Python 3.12+
- PostgreSQL with [TimescaleDB](https://docs.timescale.com/install/latest/) extension installed
- Free API keys (details below)

---

## 1. Clone and Install

```bash
git clone https://github.com/yourusername/investing.git
cd investing

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

---

## 2. Get API Keys

All keys are free tier:

| Service | Sign up | Used for |
|---|---|---|
| [FRED](https://fred.stlouisfed.org/docs/api/api_key.html) | Free account | Economic indicators |
| [Finnhub](https://finnhub.io/register) | Free account | ETF profiles, 52-week metrics |
| [Anthropic](https://console.anthropic.com/) | Pay-per-use | Claude Haiku + Sonnet narratives |
| [Alpha Vantage](https://www.alphavantage.co/support/#api-key) | Free tier (25/day) | Optional, not in critical path |

Stooq (price data) and FRED require no auth token beyond the FRED API key.

---

## 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` — minimum required fields:

```env
FRED_API_KEY=your_fred_key
FINNHUB_API_KEY=your_finnhub_key
ANTHROPIC_API_KEY=your_anthropic_key

DATABASE_URL=postgresql://investing_user:your_password@localhost:5432/investing_db
DB_HOST=localhost
DB_PORT=5432
DB_NAME=investing_db
DB_USER=investing_user
DB_PASSWORD=your_password
```

---

## 4. Set Up the Database

```bash
# Create the database user and database in PostgreSQL
psql -U postgres -c "CREATE USER investing_user WITH PASSWORD 'your_password';"
psql -U postgres -c "CREATE DATABASE investing_db OWNER investing_user;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE investing_db TO investing_user;"

# Apply the schema (creates all 20+ tables + TimescaleDB hypertables)
psql -U investing_user -d investing_db -h localhost -f database/schema.sql
```

---

## 5. Backfill Historical Data

Downloads 5 years of daily price data for all 11 ETFs from Stooq (no rate limits):

```bash
python scripts/backfill_historical_data.py
```

Expected output: ~13,800 price records across 11 symbols.

---

## 6. Collect Economic Indicators

```bash
python agents/data_collector.py --economics
```

This fetches 2 years of FRED data: Fed Funds Rate, CPI, Unemployment, VIX, 10Y/2Y Treasury, GDP, Consumer Sentiment.

---

## 7. Set Up Automated Daily Collection (Linux)

The systemd timer collects fresh data every weekday at 6 PM:

```bash
bash scripts/setup_daily_collection.sh

# Verify it's active
systemctl --user list-timers investing-collector.timer
```

To collect manually at any time:

```bash
python agents/data_collector.py
```

---

## 8. Run Your First Analysis

```bash
# Full daily briefing — all 3 agents + Claude Sonnet narrative
# (creates briefings/ directory automatically)
python agents/portfolio_advisor.py --save --output briefings/$(date +%Y-%m-%d).txt

# Or just the combined scores table (no Claude API call)
python agents/portfolio_advisor.py --scores
```

---

## Daily Workflow

After market close (6 PM weekdays — timer runs automatically):

```bash
cd ~/projects/investing
source venv/bin/activate
python agents/portfolio_advisor.py --save --output briefings/$(date +%Y-%m-%d).txt
```

Read the 4-section briefing. Done.

---

## All Commands

```bash
# --- Portfolio Advisor (main daily command) ---
python agents/portfolio_advisor.py --save                    # Full briefing + save to DB
python agents/portfolio_advisor.py --scores                  # Scores table only (no Claude)
python agents/portfolio_advisor.py --output briefings/X.txt  # Save to text file

# --- Individual Agents ---
python agents/technical_analyst.py                           # All ETFs
python agents/technical_analyst.py SPY --verbose --narrative # One symbol, detailed

python agents/fundamental_analyst.py                         # All ETFs
python agents/fundamental_analyst.py --verbose --narrative   # With Claude Haiku

python agents/risk_analyst.py                                # All ETFs
python agents/risk_analyst.py --verbose --corr               # Full detail + correlation matrix
python agents/risk_analyst.py --days 504                     # 2-year lookback

# --- Data Collection ---
python agents/data_collector.py                              # Prices + economics + profiles
python agents/data_collector.py --prices                     # Prices only
python agents/data_collector.py --economics                  # Economic indicators only

# --- Database ---
psql -U investing_user -d investing_db -h localhost
systemctl --user list-timers investing-collector.timer
systemctl --user status investing-collector.service
```

---

## Troubleshooting

**Database connection fails**
```bash
sudo systemctl status postgresql
psql -U investing_user -d investing_db -h localhost -c "SELECT version();"
```

**TimescaleDB not found**
```bash
# Install TimescaleDB extension and add to postgresql.conf:
# shared_preload_libraries = 'timescaledb'
```

**Import errors after pulling updates**
```bash
pip install -r requirements.txt --upgrade
```

**Stooq returns no data**
- Stooq occasionally has downtime. Wait and retry.
- Check that market was open (weekdays only, not US holidays).

**Claude API errors**
- Verify `ANTHROPIC_API_KEY` in `.env`
- Check your Anthropic console for credit balance
- The `--scores` flag skips Claude entirely if you need to run offline

---

## Disclaimer

Educational tool only — not financial advice. See `README.md` for full disclaimer.
