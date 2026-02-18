"""
Agent Configuration with Optimized Model Selection

Following CLAUDE.md optimization guidelines:
- Haiku: Data collection, scraping, simple tasks (60x cheaper than Opus)
- Sonnet: Analysis, calculations, standard development
- Opus: Portfolio optimization, critical decisions only
"""

from enum import Enum
from typing import Dict, Any
from dataclasses import dataclass


class ClaudeModel(Enum):
    """Claude model tiers for cost optimization"""
    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"


@dataclass
class AgentConfig:
    """Configuration for a single agent"""
    name: str
    model: ClaudeModel
    description: str
    prompt_template: str
    max_tokens: int = 4096
    temperature: float = 0.7
    tools: list = None


# =============================================================================
# DATA COLLECTION AGENTS (HAIKU - Cost Optimized)
# =============================================================================

MARKET_DATA_AGENT = AgentConfig(
    name="market_data_collector",
    model=ClaudeModel.HAIKU,
    description="Collects daily price data from multiple sources",
    prompt_template="""
    Collect market data for the following symbols: {symbols}

    Data sources:
    1. Alpha Vantage (5 calls/min limit)
    2. Finnhub (60 calls/min)
    3. FMP (250 calls/day)

    For each symbol, retrieve:
    - Open, High, Low, Close, Volume
    - Adjusted close (for dividends/splits)
    - Trading date

    Apply rate limiting and cache results.
    Return structured JSON format.
    """,
    max_tokens=2048,
    temperature=0.3  # Low temperature for factual data collection
)

FUNDAMENTALS_AGENT = AgentConfig(
    name="fundamentals_collector",
    model=ClaudeModel.HAIKU,
    description="Scrapes company financial statements from SEC EDGAR",
    prompt_template="""
    Collect fundamental data for: {company_ticker}

    Sources:
    1. SEC EDGAR API (10-K, 10-Q filings)
    2. FMP fundamentals API
    3. Finnhub financials

    Extract:
    - Income Statement (Revenue, EPS, Net Income)
    - Balance Sheet (Assets, Liabilities, Equity)
    - Cash Flow Statement
    - Key Metrics (P/E, P/B, ROE, Debt/Equity)

    Validate data consistency across sources.
    """,
    max_tokens=2048,
    temperature=0.2
)

ECONOMICS_AGENT = AgentConfig(
    name="economics_collector",
    model=ClaudeModel.HAIKU,
    description="Fetches economic indicators from FRED",
    prompt_template="""
    Collect economic indicators from FRED API:

    Required indicators:
    - GDP Growth Rate (GDPC1)
    - Unemployment Rate (UNRATE)
    - CPI Inflation (CPIAUCSL)
    - Fed Funds Rate (FEDFUNDS)
    - 10-Year Treasury Yield (GS10)
    - Consumer Sentiment (UMCSENT)

    Frequency: {frequency} (daily/weekly/monthly)
    Date range: {start_date} to {end_date}

    Store in time-series format.
    """,
    max_tokens=2048,
    temperature=0.1
)

SENTIMENT_AGENT = AgentConfig(
    name="sentiment_collector",
    model=ClaudeModel.HAIKU,
    description="Aggregates news and sentiment data",
    prompt_template="""
    Collect sentiment data for: {symbols}

    Sources:
    1. Finnhub news API (60 calls/min)
    2. Alpha Vantage sentiment API
    3. FMP social sentiment

    For each source:
    - Article headlines and summaries
    - Sentiment scores (-1 to +1)
    - Publication dates
    - Source credibility rating

    Aggregate to daily sentiment score.
    """,
    max_tokens=2048,
    temperature=0.3
)


# =============================================================================
# ANALYSIS AGENTS (SONNET - Balanced Performance)
# =============================================================================

TECHNICAL_ANALYZER = AgentConfig(
    name="technical_analyzer",
    model=ClaudeModel.SONNET,
    description="Calculates technical indicators and identifies patterns",
    prompt_template="""
    Perform technical analysis on: {symbol}
    Price data: {price_data}

    Calculate:
    1. Moving Averages (SMA 20, 50, 200 / EMA 12, 26)
    2. MACD (12, 26, 9)
    3. RSI (14-period)
    4. Bollinger Bands (20, 2)
    5. Volume indicators (OBV, Volume SMA)
    6. Support/Resistance levels

    Identify patterns:
    - Trend direction (uptrend/downtrend/sideways)
    - Crossover signals
    - Overbought/oversold conditions
    - Breakout/breakdown levels

    Provide trading signals: BUY, SELL, HOLD with confidence score.
    """,
    max_tokens=4096,
    temperature=0.5
)

FUNDAMENTAL_ANALYZER = AgentConfig(
    name="fundamental_analyzer",
    model=ClaudeModel.SONNET,
    description="Analyzes company fundamentals and calculates value metrics",
    prompt_template="""
    Analyze fundamentals for: {company_ticker}
    Financial data: {financial_data}
    Industry: {industry}

    Calculate value metrics:
    1. P/E Ratio (compare to industry average)
    2. P/B Ratio
    3. PEG Ratio
    4. Dividend Yield
    5. ROE, ROA, ROIC
    6. Profit Margins
    7. Debt/Equity Ratio
    8. Current Ratio
    9. Free Cash Flow

    Growth analysis:
    - Revenue growth (3-year, 5-year CAGR)
    - Earnings growth
    - Historical consistency

    Competitive position:
    - Industry rank by market cap
    - Competitive moats
    - Market share trends

    Output: Value score (0-100) with detailed explanation.
    """,
    max_tokens=4096,
    temperature=0.6
)

RISK_ANALYZER = AgentConfig(
    name="risk_analyzer",
    model=ClaudeModel.SONNET,
    description="Calculates portfolio risk metrics",
    prompt_template="""
    Calculate risk metrics for portfolio:
    Holdings: {holdings}
    Historical prices: {price_history}

    Calculate:
    1. Portfolio Volatility (standard deviation)
    2. Beta (vs S&P 500)
    3. Sharpe Ratio
    4. Maximum Drawdown
    5. Value at Risk (VaR) at 95% confidence
    6. Correlation matrix between holdings
    7. Sector concentration risk
    8. Geographic concentration

    Recommendations:
    - Over-concentrated positions
    - Highly correlated holdings
    - Diversification opportunities

    Risk level: LOW, MODERATE, HIGH with explanation.
    """,
    max_tokens=4096,
    temperature=0.5
)

SECTOR_ANALYZER = AgentConfig(
    name="sector_analyzer",
    model=ClaudeModel.SONNET,
    description="Analyzes sector trends and rotation signals",
    prompt_template="""
    Analyze sector performance and rotation:
    Date range: {date_range}

    Sectors to analyze:
    1. Technology (XLK)
    2. Financials (XLF)
    3. Healthcare (XLV)
    4. Consumer Discretionary (XLY)
    5. Consumer Staples (XLP)
    6. Energy (XLE)
    7. Industrials (XLI)
    8. Materials (XLB)
    9. Real Estate (XLRE)
    10. Utilities (XLU)
    11. Communications (XLC)

    For each sector:
    - Relative strength vs S&P 500
    - Momentum (12-month, 6-month, 3-month)
    - Economic cycle correlation

    Identify:
    - Leading sectors (outperforming)
    - Lagging sectors (underperforming)
    - Rotation signals (momentum shifts)

    Recommend sector allocation adjustments.
    """,
    max_tokens=4096,
    temperature=0.6
)


# =============================================================================
# STRATEGY AGENTS (OPUS - Critical Decisions Only)
# =============================================================================

PORTFOLIO_OPTIMIZER = AgentConfig(
    name="portfolio_optimizer",
    model=ClaudeModel.OPUS,
    description="Optimizes portfolio allocation using modern portfolio theory",
    prompt_template="""
    Optimize portfolio allocation:

    Current portfolio: {current_holdings}
    Available cash: {available_cash}
    Risk tolerance: {risk_tolerance}
    Investment horizon: {investment_horizon}

    Input data:
    - Historical returns and volatilities
    - Correlation matrix
    - Technical analysis signals
    - Fundamental valuations
    - Economic indicators
    - Sector trends

    Optimization objectives:
    1. Maximize risk-adjusted returns (Sharpe ratio)
    2. Respect risk tolerance constraints
    3. Maintain diversification (max 5% per stock)
    4. Tax efficiency (minimize taxable events)
    5. Transaction cost minimization

    Constraints:
    - Emergency fund: Keep ${emergency_fund} liquid
    - No leverage (100% allocation max)
    - Minimum position size: $500

    Provide:
    1. Recommended allocation percentages
    2. Specific buy/sell orders
    3. Rebalancing trades
    4. Expected return and risk metrics
    5. Detailed rationale for each decision

    Educational explanation: Explain WHY these allocations are recommended.
    """,
    max_tokens=8192,
    temperature=0.7
)

MARKET_STRATEGIST = AgentConfig(
    name="market_strategist",
    model=ClaudeModel.OPUS,
    description="Analyzes overall market regime and provides strategic guidance",
    prompt_template="""
    Analyze current market regime and provide strategic guidance:

    Market data:
    - S&P 500 trend and momentum
    - VIX (volatility index)
    - Credit spreads
    - Yield curve shape
    - Economic indicators
    - Fed policy stance

    Sector rotation signals:
    {sector_analysis}

    Sentiment indicators:
    {sentiment_data}

    Determine market regime:
    1. BULL MARKET: Strong uptrend, low volatility
    2. BEAR MARKET: Strong downtrend, high volatility
    3. SIDEWAYS: Range-bound, mixed signals
    4. CORRECTION: -10% to -20% pullback
    5. CRASH: >-20% drawdown

    For current regime, recommend:
    - Optimal equity/bond allocation
    - Sector positioning (offensive vs defensive)
    - Cash allocation
    - Risk management strategies
    - Entry/exit timing considerations

    Scenario planning:
    - Best case scenario (probability)
    - Base case scenario (probability)
    - Worst case scenario (probability)

    Educational context: Explain market cycles and historical patterns.
    """,
    max_tokens=8192,
    temperature=0.8
)

EDUCATION_TUTOR = AgentConfig(
    name="education_tutor",
    model=ClaudeModel.OPUS,
    description="Explains investing concepts and agent decisions in educational format",
    prompt_template="""
    Explain the following investing concept or decision:
    Topic: {topic}
    Context: {context}
    User's experience level: {experience_level}

    Provide comprehensive explanation covering:

    1. **Fundamental Concept**
       - What it is in simple terms
       - Why it matters for investing
       - Common misconceptions

    2. **How It Works**
       - Step-by-step breakdown
       - Mathematical formula (if applicable)
       - Practical example with real numbers

    3. **Application to Your Portfolio**
       - How our agents use this concept
       - Why specific recommendations were made
       - Expected outcomes

    4. **Historical Context**
       - How this played out in past markets
       - Success rates and limitations
       - Notable examples

    5. **Further Learning**
       - Related concepts to explore
       - Recommended resources
       - Practice exercises

    Teaching style:
    - Use analogies and real-world examples
    - Show calculations step-by-step
    - Highlight common pitfalls
    - Encourage critical thinking
    - Connect to user's specific situation ($2,700 biweekly income)

    Make it engaging and build genuine understanding.
    """,
    max_tokens=8192,
    temperature=0.8
)


# =============================================================================
# AGENT REGISTRY
# =============================================================================

AGENT_REGISTRY: Dict[str, AgentConfig] = {
    # Data Collection (Haiku)
    "market_data": MARKET_DATA_AGENT,
    "fundamentals": FUNDAMENTALS_AGENT,
    "economics": ECONOMICS_AGENT,
    "sentiment": SENTIMENT_AGENT,

    # Analysis (Sonnet)
    "technical_analyzer": TECHNICAL_ANALYZER,
    "fundamental_analyzer": FUNDAMENTAL_ANALYZER,
    "risk_analyzer": RISK_ANALYZER,
    "sector_analyzer": SECTOR_ANALYZER,

    # Strategy (Opus)
    "portfolio_optimizer": PORTFOLIO_OPTIMIZER,
    "market_strategist": MARKET_STRATEGIST,
    "education_tutor": EDUCATION_TUTOR,
}


def get_agent_config(agent_name: str) -> AgentConfig:
    """Retrieve agent configuration by name"""
    if agent_name not in AGENT_REGISTRY:
        raise ValueError(f"Agent '{agent_name}' not found in registry")
    return AGENT_REGISTRY[agent_name]


def list_agents_by_model(model: ClaudeModel) -> list[str]:
    """List all agents using a specific model tier"""
    return [
        name for name, config in AGENT_REGISTRY.items()
        if config.model == model
    ]


# Cost estimation (approximate)
MODEL_COSTS = {
    ClaudeModel.HAIKU: {"input": 0.25, "output": 1.25},  # per million tokens
    ClaudeModel.SONNET: {"input": 3.0, "output": 15.0},
    ClaudeModel.OPUS: {"input": 15.0, "output": 75.0},
}


def estimate_agent_cost(agent_name: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost for agent execution"""
    config = get_agent_config(agent_name)
    costs = MODEL_COSTS[config.model]

    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]

    return input_cost + output_cost


if __name__ == "__main__":
    # Print agent summary
    print("=" * 70)
    print("INVESTMENT AGENT SYSTEM - MODEL ALLOCATION")
    print("=" * 70)

    for model in ClaudeModel:
        agents = list_agents_by_model(model)
        print(f"\n{model.value.upper()} Agents ({len(agents)}):")
        print(f"Cost: ${MODEL_COSTS[model]['input']}/M input, ${MODEL_COSTS[model]['output']}/M output")
        for agent in agents:
            config = AGENT_REGISTRY[agent]
            print(f"  - {agent}: {config.description}")

    print("\n" + "=" * 70)
    print("COST OPTIMIZATION SUMMARY")
    print("=" * 70)
    print("✓ Data collection uses HAIKU (60x cheaper than Opus)")
    print("✓ Analysis uses SONNET (balanced cost/performance)")
    print("✓ Strategy uses OPUS (critical decisions only)")
    print("✓ Following CLAUDE.md optimization guidelines")
