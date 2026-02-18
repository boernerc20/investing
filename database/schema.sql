-- Investment Portfolio Database Schema
-- PostgreSQL + TimescaleDB for time-series data

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- =============================================================================
-- MARKET DATA TABLES
-- =============================================================================

-- Daily price data for stocks/ETFs
CREATE TABLE daily_prices (
    symbol VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open NUMERIC(12, 4) NOT NULL,
    high NUMERIC(12, 4) NOT NULL,
    low NUMERIC(12, 4) NOT NULL,
    close NUMERIC(12, 4) NOT NULL,
    adjusted_close NUMERIC(12, 4) NOT NULL,
    volume BIGINT NOT NULL,
    dividend NUMERIC(12, 4) DEFAULT 0,
    split_factor NUMERIC(8, 4) DEFAULT 1,
    data_source VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, date)
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('daily_prices', 'date', if_not_exists => TRUE);

-- Intraday price data (for future use)
CREATE TABLE intraday_prices (
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open NUMERIC(12, 4) NOT NULL,
    high NUMERIC(12, 4) NOT NULL,
    low NUMERIC(12, 4) NOT NULL,
    close NUMERIC(12, 4) NOT NULL,
    volume BIGINT NOT NULL,
    data_source VARCHAR(20),
    PRIMARY KEY (symbol, timestamp)
);

SELECT create_hypertable('intraday_prices', 'timestamp', if_not_exists => TRUE);

-- Company/ETF metadata
CREATE TABLE securities (
    symbol VARCHAR(10) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(20) NOT NULL, -- 'stock', 'etf', 'index'
    exchange VARCHAR(20),
    sector VARCHAR(50),
    industry VARCHAR(100),
    market_cap NUMERIC(18, 2),
    description TEXT,
    website VARCHAR(255),
    ipo_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- FUNDAMENTAL DATA TABLES
-- =============================================================================

-- Company financial statements (quarterly)
CREATE TABLE financial_statements (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL REFERENCES securities(symbol),
    fiscal_period VARCHAR(10) NOT NULL, -- 'Q1', 'Q2', 'Q3', 'Q4', 'FY'
    fiscal_year INTEGER NOT NULL,
    report_date DATE NOT NULL,
    filing_date DATE,

    -- Income Statement
    revenue NUMERIC(18, 2),
    cost_of_revenue NUMERIC(18, 2),
    gross_profit NUMERIC(18, 2),
    operating_expenses NUMERIC(18, 2),
    operating_income NUMERIC(18, 2),
    net_income NUMERIC(18, 2),
    eps_basic NUMERIC(12, 4),
    eps_diluted NUMERIC(12, 4),

    -- Balance Sheet
    total_assets NUMERIC(18, 2),
    current_assets NUMERIC(18, 2),
    cash_and_equivalents NUMERIC(18, 2),
    total_liabilities NUMERIC(18, 2),
    current_liabilities NUMERIC(18, 2),
    long_term_debt NUMERIC(18, 2),
    shareholders_equity NUMERIC(18, 2),

    -- Cash Flow Statement
    operating_cash_flow NUMERIC(18, 2),
    investing_cash_flow NUMERIC(18, 2),
    financing_cash_flow NUMERIC(18, 2),
    free_cash_flow NUMERIC(18, 2),

    data_source VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, fiscal_year, fiscal_period)
);

-- Financial metrics and ratios
CREATE TABLE financial_metrics (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL REFERENCES securities(symbol),
    date DATE NOT NULL,

    -- Valuation Ratios
    pe_ratio NUMERIC(10, 2),
    forward_pe NUMERIC(10, 2),
    peg_ratio NUMERIC(10, 2),
    price_to_book NUMERIC(10, 2),
    price_to_sales NUMERIC(10, 2),
    ev_to_ebitda NUMERIC(10, 2),

    -- Profitability Metrics
    gross_margin NUMERIC(8, 4),
    operating_margin NUMERIC(8, 4),
    net_profit_margin NUMERIC(8, 4),
    roe NUMERIC(8, 4), -- Return on Equity
    roa NUMERIC(8, 4), -- Return on Assets
    roic NUMERIC(8, 4), -- Return on Invested Capital

    -- Financial Health
    current_ratio NUMERIC(8, 4),
    quick_ratio NUMERIC(8, 4),
    debt_to_equity NUMERIC(8, 4),
    interest_coverage NUMERIC(8, 4),

    -- Growth Metrics
    revenue_growth_yoy NUMERIC(8, 4),
    earnings_growth_yoy NUMERIC(8, 4),

    -- Dividend Metrics
    dividend_yield NUMERIC(8, 4),
    dividend_payout_ratio NUMERIC(8, 4),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, date)
);

-- =============================================================================
-- ECONOMIC DATA TABLES
-- =============================================================================

-- Economic indicators from FRED
CREATE TABLE economic_indicators (
    indicator_code VARCHAR(50) NOT NULL, -- FRED series ID
    date DATE NOT NULL,
    value NUMERIC(18, 6) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (indicator_code, date)
);

SELECT create_hypertable('economic_indicators', 'date', if_not_exists => TRUE);

-- Indicator metadata
CREATE TABLE indicator_metadata (
    indicator_code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    units VARCHAR(50),
    frequency VARCHAR(20), -- 'daily', 'weekly', 'monthly', 'quarterly'
    category VARCHAR(50), -- 'inflation', 'gdp', 'employment', 'rates'
    source VARCHAR(50) DEFAULT 'FRED'
);

-- =============================================================================
-- SENTIMENT & NEWS DATA
-- =============================================================================

-- News articles
CREATE TABLE news_articles (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) REFERENCES securities(symbol),
    published_at TIMESTAMPTZ NOT NULL,
    headline TEXT NOT NULL,
    summary TEXT,
    url VARCHAR(500),
    source VARCHAR(100),
    sentiment_score NUMERIC(5, 4), -- -1.0 to +1.0
    sentiment_label VARCHAR(20), -- 'bullish', 'bearish', 'neutral'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_news_symbol_date ON news_articles(symbol, published_at DESC);

-- Daily aggregated sentiment scores
CREATE TABLE daily_sentiment (
    symbol VARCHAR(10) NOT NULL REFERENCES securities(symbol),
    date DATE NOT NULL,
    sentiment_score NUMERIC(5, 4), -- -1.0 to +1.0
    article_count INTEGER,
    bullish_count INTEGER,
    bearish_count INTEGER,
    neutral_count INTEGER,
    data_source VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, date)
);

-- =============================================================================
-- PORTFOLIO MANAGEMENT TABLES
-- =============================================================================

-- Portfolio holdings
CREATE TABLE portfolio_holdings (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL REFERENCES securities(symbol),
    shares NUMERIC(18, 6) NOT NULL,
    average_cost NUMERIC(12, 4) NOT NULL,
    current_price NUMERIC(12, 4),
    market_value NUMERIC(18, 2),
    unrealized_gain_loss NUMERIC(18, 2),
    allocation_percentage NUMERIC(5, 2),
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Transaction history
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL REFERENCES securities(symbol),
    transaction_type VARCHAR(10) NOT NULL, -- 'BUY', 'SELL', 'DIVIDEND'
    transaction_date DATE NOT NULL,
    shares NUMERIC(18, 6) NOT NULL,
    price_per_share NUMERIC(12, 4) NOT NULL,
    total_amount NUMERIC(18, 2) NOT NULL,
    fees NUMERIC(12, 2) DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Portfolio snapshots (daily)
CREATE TABLE portfolio_snapshots (
    snapshot_date DATE PRIMARY KEY,
    total_value NUMERIC(18, 2) NOT NULL,
    cash_balance NUMERIC(18, 2) NOT NULL,
    invested_amount NUMERIC(18, 2) NOT NULL,
    total_gain_loss NUMERIC(18, 2) NOT NULL,
    total_gain_loss_percent NUMERIC(8, 4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TECHNICAL INDICATORS TABLE
-- =============================================================================

-- Calculated technical indicators
CREATE TABLE technical_indicators (
    symbol VARCHAR(10) NOT NULL REFERENCES securities(symbol),
    date DATE NOT NULL,

    -- Moving Averages
    sma_20 NUMERIC(12, 4),
    sma_50 NUMERIC(12, 4),
    sma_200 NUMERIC(12, 4),
    ema_12 NUMERIC(12, 4),
    ema_26 NUMERIC(12, 4),

    -- MACD
    macd NUMERIC(12, 4),
    macd_signal NUMERIC(12, 4),
    macd_histogram NUMERIC(12, 4),

    -- RSI
    rsi_14 NUMERIC(8, 4),

    -- Bollinger Bands
    bb_upper NUMERIC(12, 4),
    bb_middle NUMERIC(12, 4),
    bb_lower NUMERIC(12, 4),

    -- Volume
    volume_sma_20 BIGINT,
    obv BIGINT, -- On-Balance Volume

    -- Trend Indicators
    adx NUMERIC(8, 4), -- Average Directional Index

    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, date)
);

-- =============================================================================
-- AGENT DECISIONS & RECOMMENDATIONS
-- =============================================================================

-- Agent recommendations/signals
CREATE TABLE agent_recommendations (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(50) NOT NULL,
    symbol VARCHAR(10) REFERENCES securities(symbol),
    recommendation_type VARCHAR(20) NOT NULL, -- 'BUY', 'SELL', 'HOLD'
    confidence_score NUMERIC(5, 4), -- 0.0 to 1.0
    target_price NUMERIC(12, 4),
    stop_loss NUMERIC(12, 4),
    reasoning TEXT,
    supporting_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Portfolio optimization results
CREATE TABLE optimization_results (
    id SERIAL PRIMARY KEY,
    optimization_date DATE NOT NULL,
    agent_name VARCHAR(50) NOT NULL,
    recommended_allocation JSONB NOT NULL, -- {symbol: percentage}
    expected_return NUMERIC(8, 4),
    expected_volatility NUMERIC(8, 4),
    sharpe_ratio NUMERIC(8, 4),
    rationale TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- USER SETTINGS & CONFIGURATION
-- =============================================================================

-- User investment profile
CREATE TABLE user_profile (
    id SERIAL PRIMARY KEY,
    monthly_income NUMERIC(12, 2) NOT NULL,
    monthly_investment_amount NUMERIC(12, 2) NOT NULL,
    emergency_fund_target NUMERIC(18, 2) NOT NULL,
    emergency_fund_current NUMERIC(18, 2) NOT NULL,
    risk_tolerance VARCHAR(20) NOT NULL, -- 'conservative', 'moderate', 'aggressive'
    investment_horizon_years INTEGER NOT NULL,
    investment_goals TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Investment pots configuration
CREATE TABLE investment_pots (
    id SERIAL PRIMARY KEY,
    pot_name VARCHAR(50) NOT NULL UNIQUE,
    pot_type VARCHAR(30) NOT NULL, -- 'index_core', 'growth', 'value', 'experimental'
    target_allocation_percent NUMERIC(5, 2) NOT NULL,
    current_value NUMERIC(18, 2) DEFAULT 0,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

-- Insert default pots
INSERT INTO investment_pots (pot_name, pot_type, target_allocation_percent, description) VALUES
('Index Fund Core', 'index_core', 40.00, 'VTI, VXUS, BND - Set-it-and-forget-it'),
('Growth Stocks', 'growth', 30.00, 'Quality growth companies, 3-5 year hold'),
('Value Opportunities', 'value', 20.00, 'Undervalued stocks, contrarian plays'),
('Learning/Experimental', 'experimental', 10.00, 'Individual picks, learning tuition');

-- =============================================================================
-- INDEXES FOR PERFORMANCE
-- =============================================================================

CREATE INDEX idx_daily_prices_symbol ON daily_prices(symbol);
CREATE INDEX idx_financial_statements_symbol ON financial_statements(symbol);
CREATE INDEX idx_financial_metrics_symbol ON financial_metrics(symbol);
CREATE INDEX idx_transactions_date ON transactions(transaction_date DESC);
CREATE INDEX idx_agent_recommendations_symbol ON agent_recommendations(symbol);
CREATE INDEX idx_agent_recommendations_date ON agent_recommendations(created_at DESC);

-- =============================================================================
-- VIEWS FOR COMMON QUERIES
-- =============================================================================

-- Current portfolio summary
CREATE VIEW v_portfolio_summary AS
SELECT
    h.symbol,
    s.name,
    s.sector,
    h.shares,
    h.average_cost,
    h.current_price,
    h.market_value,
    h.unrealized_gain_loss,
    h.allocation_percentage,
    (h.current_price - h.average_cost) / h.average_cost * 100 AS return_percent
FROM portfolio_holdings h
JOIN securities s ON h.symbol = s.symbol
WHERE h.shares > 0
ORDER BY h.market_value DESC;

-- Latest technical signals
CREATE VIEW v_latest_signals AS
SELECT
    ti.symbol,
    s.name,
    dp.close AS current_price,
    ti.sma_20,
    ti.sma_50,
    ti.sma_200,
    ti.rsi_14,
    ti.macd,
    ti.macd_signal,
    CASE
        WHEN ti.rsi_14 > 70 THEN 'Overbought'
        WHEN ti.rsi_14 < 30 THEN 'Oversold'
        ELSE 'Neutral'
    END AS rsi_signal,
    CASE
        WHEN dp.close > ti.sma_50 AND ti.sma_50 > ti.sma_200 THEN 'Bullish'
        WHEN dp.close < ti.sma_50 AND ti.sma_50 < ti.sma_200 THEN 'Bearish'
        ELSE 'Neutral'
    END AS trend_signal,
    ti.date
FROM technical_indicators ti
JOIN securities s ON ti.symbol = s.symbol
JOIN daily_prices dp ON ti.symbol = dp.symbol AND ti.date = dp.date
WHERE ti.date = (SELECT MAX(date) FROM technical_indicators WHERE symbol = ti.symbol);

-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Update portfolio holding market value
CREATE OR REPLACE FUNCTION update_holding_market_value()
RETURNS TRIGGER AS $$
BEGIN
    NEW.market_value = NEW.shares * NEW.current_price;
    NEW.unrealized_gain_loss = NEW.market_value - (NEW.shares * NEW.average_cost);
    NEW.last_updated = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_holding_value
BEFORE UPDATE OF shares, current_price ON portfolio_holdings
FOR EACH ROW
EXECUTE FUNCTION update_holding_market_value();

-- Calculate allocation percentages
CREATE OR REPLACE FUNCTION calculate_allocation_percentages()
RETURNS VOID AS $$
DECLARE
    total_value NUMERIC(18, 2);
BEGIN
    SELECT SUM(market_value) INTO total_value FROM portfolio_holdings WHERE shares > 0;

    IF total_value > 0 THEN
        UPDATE portfolio_holdings
        SET allocation_percentage = (market_value / total_value) * 100
        WHERE shares > 0;
    END IF;
END;
$$ LANGUAGE plpgsql;
