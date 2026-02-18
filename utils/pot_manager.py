"""
Investment Pots Manager

Manages the "pots" allocation system for portfolio diversification.
Each pot represents a different investment strategy with target allocation.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class PotType(Enum):
    """Investment pot categories"""
    INDEX_CORE = "index_core"
    GROWTH = "growth"
    VALUE = "value"
    EXPERIMENTAL = "experimental"


@dataclass
class InvestmentPot:
    """Configuration for a single investment pot"""
    name: str
    pot_type: PotType
    target_allocation_percent: float
    description: str
    strategy: str
    symbols: List[str]
    min_position_size: float = 500.0  # Minimum $ per position


# =============================================================================
# POT DEFINITIONS
# =============================================================================

INDEX_FUND_CORE = InvestmentPot(
    name="Index Fund Core",
    pot_type=PotType.INDEX_CORE,
    target_allocation_percent=40.0,
    description="Set-it-and-forget-it broad market exposure",
    strategy="""
    Core portfolio foundation using low-cost index funds.

    Allocation strategy:
    - 60% Total US Stock Market (VTI)
    - 30% Total International (VXUS)
    - 10% Total Bond Market (BND)

    Rebalance: Quarterly
    Hold period: Indefinite (buy and hold)
    Risk level: Low-Moderate

    Why this works:
    - Captures entire market returns
    - Lowest fees (0.03-0.05%)
    - Proven long-term strategy
    - Minimal maintenance required
    """,
    symbols=["VTI", "VXUS", "BND"]
)

GROWTH_STOCKS = InvestmentPot(
    name="Growth Stocks",
    pot_type=PotType.GROWTH,
    target_allocation_percent=30.0,
    description="Quality companies with strong growth potential",
    strategy="""
    Focus on established companies with:
    - Revenue growth > 15% annually
    - Expanding profit margins
    - Strong competitive moats
    - Leadership in growing markets

    Sectors: Technology, Healthcare, Clean Energy

    Screening criteria:
    ✓ Market cap > $10B (established companies)
    ✓ Positive earnings (profitable)
    ✓ P/E ratio < 40 (not absurdly overvalued)
    ✓ Strong balance sheet (low debt)
    ✓ Technical: Above 200-day moving average

    Hold period: 3-5 years minimum
    Position size: Max 5% per stock
    Stop loss: -20% from entry

    Examples: Microsoft, Apple, Nvidia, UnitedHealth
    """,
    symbols=[],  # Dynamic based on screening
    min_position_size=500.0
)

VALUE_OPPORTUNITIES = InvestmentPot(
    name="Value Opportunities",
    pot_type=PotType.VALUE,
    target_allocation_percent=20.0,
    description="Undervalued stocks with strong fundamentals",
    strategy="""
    Contrarian approach: Buy quality companies when they're cheap.

    Screening criteria:
    ✓ P/E ratio < industry average
    ✓ P/B ratio < 3
    ✓ Dividend yield > 2%
    ✓ Strong cash flow (FCF positive)
    ✓ Debt/Equity < 1
    ✓ ROE > 10%

    Look for:
    - Out-of-favor sectors
    - Temporary setbacks (not structural decline)
    - Dividend aristocrats (25+ years of increases)
    - Spin-offs and special situations

    Hold period: 2-3 years (until value recognized)
    Position size: Max 5% per stock
    Buy zone: When technical indicators oversold

    Examples: Banks during rate hikes, Energy during transitions
    """,
    symbols=[],  # Dynamic based on screening
    min_position_size=500.0
)

LEARNING_EXPERIMENTAL = InvestmentPot(
    name="Learning/Experimental",
    pot_type=PotType.EXPERIMENTAL,
    target_allocation_percent=10.0,
    description="Your investing tuition - learn by doing",
    strategy="""
    This pot is for LEARNING, not maximizing returns.

    Acceptable uses:
    - Test agent recommendations
    - Try sector rotation strategies
    - Experiment with technical analysis
    - Learn from mistakes with real money

    Rules:
    - Max 2% per position (smaller positions = more learning)
    - Document WHY you made each trade
    - Review quarterly: What worked? What didn't?
    - Expected outcome: Some winners, some losers, LOTS of learning

    Think of this as:
    💵 Tuition for investing education
    📚 Better than paying for courses
    🎓 Real-world experience

    As you learn and prove strategies work, graduate them to Growth/Value pots.
    """,
    symbols=[],  # Anything goes (within risk limits)
    min_position_size=200.0  # Smaller minimum for learning
)


# =============================================================================
# POT MANAGER CLASS
# =============================================================================

class PotManager:
    """Manages investment pot allocations and rebalancing"""

    def __init__(self, monthly_investment: float = 5850.0):
        self.monthly_investment = monthly_investment
        self.pots = {
            "index_core": INDEX_FUND_CORE,
            "growth": GROWTH_STOCKS,
            "value": VALUE_OPPORTUNITIES,
            "experimental": LEARNING_EXPERIMENTAL,
        }

    def calculate_monthly_allocations(self) -> Dict[str, float]:
        """Calculate how much goes to each pot this month"""

        allocations = {}
        for pot_id, pot in self.pots.items():
            amount = self.monthly_investment * (pot.target_allocation_percent / 100)
            allocations[pot_id] = round(amount, 2)

        return allocations

    def get_pot_allocation_summary(self) -> str:
        """Get formatted summary of pot allocations"""

        allocations = self.calculate_monthly_allocations()

        summary = "=" * 70 + "\n"
        summary += "MONTHLY INVESTMENT ALLOCATION\n"
        summary += "=" * 70 + "\n"
        summary += f"Total Monthly Investment: ${self.monthly_investment:,.2f}\n\n"

        for pot_id, amount in allocations.items():
            pot = self.pots[pot_id]
            pct = pot.target_allocation_percent
            summary += f"{pot.name}\n"
            summary += f"  Allocation: {pct:.1f}% (${amount:,.2f}/month)\n"
            summary += f"  Strategy: {pot.description}\n\n"

        return summary

    def needs_rebalancing(
        self,
        current_allocations: Dict[str, float],
        tolerance: float = 5.0
    ) -> bool:
        """
        Check if portfolio needs rebalancing

        Args:
            current_allocations: Current % allocation for each pot
            tolerance: Percentage points deviation allowed (default 5%)

        Returns:
            True if any pot is outside tolerance band
        """

        for pot_id, pot in self.pots.items():
            target = pot.target_allocation_percent
            current = current_allocations.get(pot_id, 0)

            deviation = abs(current - target)
            if deviation > tolerance:
                logger.info(
                    f"Pot '{pot.name}' needs rebalancing: "
                    f"Current {current:.1f}% vs Target {target:.1f}% "
                    f"(deviation: {deviation:.1f}%)"
                )
                return True

        return False

    def calculate_rebalancing_trades(
        self,
        current_values: Dict[str, float],
        total_portfolio_value: float
    ) -> Dict[str, float]:
        """
        Calculate trades needed to rebalance portfolio

        Args:
            current_values: Current dollar value in each pot
            total_portfolio_value: Total portfolio value

        Returns:
            Dictionary of pot_id -> dollar amount to buy (+) or sell (-)
        """

        trades = {}

        for pot_id, pot in self.pots.items():
            current_value = current_values.get(pot_id, 0)
            current_pct = (current_value / total_portfolio_value) * 100

            target_pct = pot.target_allocation_percent
            target_value = total_portfolio_value * (target_pct / 100)

            difference = target_value - current_value
            trades[pot_id] = round(difference, 2)

        return trades

    def validate_trade(
        self,
        pot_id: str,
        symbol: str,
        amount: float
    ) -> tuple[bool, str]:
        """
        Validate if a trade follows pot rules

        Returns:
            (is_valid, message)
        """

        pot = self.pots.get(pot_id)
        if not pot:
            return False, f"Unknown pot: {pot_id}"

        # Check minimum position size
        if amount < pot.min_position_size:
            return False, (
                f"Position size ${amount:.2f} below minimum "
                f"${pot.min_position_size:.2f} for {pot.name}"
            )

        # Check if symbol allowed for pot type
        if pot.symbols and symbol not in pot.symbols:
            return False, (
                f"Symbol {symbol} not in allowed list for {pot.name}. "
                f"Allowed: {', '.join(pot.symbols)}"
            )

        return True, "Trade validated"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def print_pot_strategies():
    """Print detailed strategy for each pot"""

    print("=" * 70)
    print("INVESTMENT POTS - DETAILED STRATEGIES")
    print("=" * 70)

    pots = [
        INDEX_FUND_CORE,
        GROWTH_STOCKS,
        VALUE_OPPORTUNITIES,
        LEARNING_EXPERIMENTAL
    ]

    for pot in pots:
        print(f"\n{pot.name}")
        print("-" * 70)
        print(f"Target Allocation: {pot.target_allocation_percent}%")
        print(f"Description: {pot.description}\n")
        print("Strategy:")
        print(pot.strategy)
        print("=" * 70)


if __name__ == "__main__":
    # Example usage
    manager = PotManager(monthly_investment=5850.0)

    # Show monthly allocations
    print(manager.get_pot_allocation_summary())

    # Show pot strategies
    print_pot_strategies()

    # Simulate rebalancing check
    print("\n" + "=" * 70)
    print("REBALANCING EXAMPLE")
    print("=" * 70)

    # Current portfolio is overweight Growth, underweight Index
    current_allocations = {
        "index_core": 30.0,  # Target: 40% (underweight)
        "growth": 45.0,      # Target: 30% (overweight)
        "value": 20.0,       # Target: 20% (on target)
        "experimental": 5.0, # Target: 10% (underweight)
    }

    needs_rebal = manager.needs_rebalancing(current_allocations, tolerance=5.0)
    print(f"Needs rebalancing: {needs_rebal}")

    if needs_rebal:
        total_value = 50000.0
        current_values = {
            pot_id: total_value * (pct / 100)
            for pot_id, pct in current_allocations.items()
        }

        trades = manager.calculate_rebalancing_trades(current_values, total_value)

        print("\nRebalancing trades:")
        for pot_id, amount in trades.items():
            pot = manager.pots[pot_id]
            action = "BUY" if amount > 0 else "SELL"
            print(f"  {action} ${abs(amount):,.2f} in {pot.name}")
