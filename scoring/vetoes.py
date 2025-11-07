"""
Automatic veto rules.
Disqualifies stocks that meet certain risk criteria regardless of score.
"""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime

from utils.config import config


class VetoResult:
    """Result of veto check."""

    def __init__(self, is_vetoed: bool = False, reason: str = ""):
        self.is_vetoed = is_vetoed
        self.reason = reason
        self.veto_reasons: List[str] = []

        if is_vetoed and reason:
            self.veto_reasons.append(reason)

    def add_veto(self, reason: str):
        """Add a veto reason."""
        self.is_vetoed = True
        self.veto_reasons.append(reason)


def check_liquidity_veto(info: Dict[str, Any]) -> VetoResult:
    """
    Check liquidity filters.

    Vetos if:
    - Average daily volume < 500,000 shares
    - Market cap < $300 million

    Args:
        info: Stock info dictionary

    Returns:
        VetoResult
    """
    veto_params = config.get_veto_rules()
    result = VetoResult()

    # Check average volume
    avg_volume = info.get('averageVolume')
    if avg_volume is not None and avg_volume < veto_params['min_avg_volume']:
        result.add_veto(
            f"Insufficient liquidity: Avg volume {avg_volume:,.0f} < {veto_params['min_avg_volume']:,.0f} shares"
        )

    # Check market cap
    market_cap = info.get('marketCap')
    if market_cap is not None and market_cap < veto_params['min_market_cap']:
        result.add_veto(
            f"Too small: Market cap ${market_cap/1e6:.1f}M < ${veto_params['min_market_cap']/1e6:.0f}M"
        )

    return result


def check_event_risk_veto(info: Dict[str, Any]) -> VetoResult:
    """
    Check for upcoming event risk.

    Vetos if:
    - Earnings announcement within next 7 days

    Args:
        info: Stock info dictionary

    Returns:
        VetoResult
    """
    veto_params = config.get_veto_rules()
    result = VetoResult()

    # Check earnings date
    earnings_date = info.get('earningsDate')
    if earnings_date:
        # earningsDate can be a timestamp or list of timestamps
        next_earnings_raw = earnings_date[0] if isinstance(earnings_date, list) and len(earnings_date) > 0 else earnings_date

        try:
            # Convert to datetime if it's a timestamp
            next_earnings_dt: datetime
            if hasattr(next_earnings_raw, 'to_pydatetime'):
                next_earnings_dt = next_earnings_raw.to_pydatetime()  # type: ignore
            elif isinstance(next_earnings_raw, datetime):
                next_earnings_dt = next_earnings_raw
            else:
                # Skip if we can't convert
                return result

            days_to_earnings = (next_earnings_dt - datetime.now()).days

            if 0 <= days_to_earnings <= veto_params['earnings_days_before']:
                result.add_veto(
                    f"Earnings risk: Earnings in {days_to_earnings} days (avoid within {veto_params['earnings_days_before']} days)"
                )
        except (AttributeError, TypeError):
            # Unable to parse earnings date
            pass

    return result


def check_fundamental_disaster_veto(info: Dict[str, Any]) -> VetoResult:
    """
    Check for fundamental disasters.

    Vetos if:
    - Debt/Equity > 3.0 (bankruptcy risk)

    Note: Negative earnings and cash flow quality are checked separately
    as they require historical data.

    Args:
        info: Stock info dictionary

    Returns:
        VetoResult
    """
    veto_params = config.get_veto_rules()
    result = VetoResult()

    # Check debt to equity
    debt_to_equity = info.get('debtToEquity')
    if debt_to_equity is not None and not pd.isna(debt_to_equity):
        # Convert from percentage if needed
        if debt_to_equity > 10:
            debt_to_equity = debt_to_equity / 100

        if debt_to_equity > veto_params['max_debt_equity']:
            result.add_veto(
                f"Bankruptcy risk: Debt/Equity {debt_to_equity:.2f} > {veto_params['max_debt_equity']:.1f}"
            )

    return result


def check_technical_breakdown_veto(df: pd.DataFrame) -> VetoResult:
    """
    Check for technical breakdown.

    Vetos if:
    - Price down > 50% in last 60 days (falling knife)

    Args:
        df: Price DataFrame

    Returns:
        VetoResult
    """
    veto_params = config.get_veto_rules()
    result = VetoResult()

    if len(df) < 60:
        return result

    # Calculate 60-day decline
    price_60_days_ago = df['Close'].iloc[-60]
    current_price = df['Close'].iloc[-1]
    decline_pct = (current_price - price_60_days_ago) / price_60_days_ago

    if decline_pct < -veto_params['max_decline_60d']:
        result.add_veto(
            f"Falling knife: Price down {abs(decline_pct)*100:.1f}% in 60 days (> {veto_params['max_decline_60d']*100:.0f}%)"
        )

    return result


def check_data_quality_veto(info: Dict[str, Any], df: pd.DataFrame) -> VetoResult:
    """
    Check for data quality issues.

    Vetos if:
    - Missing critical fundamental data
    - Invalid price data

    Args:
        info: Stock info dictionary
        df: Price DataFrame

    Returns:
        VetoResult
    """
    result = VetoResult()

    # Check if we have price data
    if df is None or df.empty:
        result.add_veto("Missing price data")

    # Check if we have basic info
    if not info:
        result.add_veto("Missing stock information")

    # Check for valid current price
    if info and 'currentPrice' not in info and 'regularMarketPrice' not in info and 'previousClose' not in info:
        result.add_veto("Missing current price data")

    return result


def apply_all_veto_rules(
    ticker: str,
    info: Dict[str, Any],
    df: pd.DataFrame
) -> VetoResult:
    """
    Apply all veto rules.

    Args:
        ticker: Stock ticker symbol
        info: Stock info dictionary
        df: Price DataFrame

    Returns:
        VetoResult with all veto checks
    """
    combined_result = VetoResult()

    # Run all veto checks
    checks = [
        check_liquidity_veto(info),
        check_event_risk_veto(info),
        check_fundamental_disaster_veto(info),
        check_technical_breakdown_veto(df),
        check_data_quality_veto(info, df)
    ]

    # Combine all veto reasons
    for check in checks:
        if check.is_vetoed:
            combined_result.is_vetoed = True
            combined_result.veto_reasons.extend(check.veto_reasons)

    return combined_result
