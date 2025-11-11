"""
Fundamental analysis indicators.
Valuation metrics and quality metrics based on financial statements.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

from utils.config import config


def calculate_pe_score(info: Dict[str, Any], sector: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate P/E ratio score with improved edge case handling (Phase 2).

    Args:
        info: Stock info dictionary from yfinance
        sector: Stock sector for sector-specific thresholds

    Returns:
        Dictionary with score and details
    """
    fundamental_params = config.get_fundamental_params()

    # Get P/E ratio - Phase 2: Try forward P/E first if trailing is negative
    trailing_pe = info.get('trailingPE')
    forward_pe = info.get('forwardPE')

    # Use forward P/E if trailing is negative or missing
    if trailing_pe is None or pd.isna(trailing_pe) or trailing_pe < 0:
        pe_ratio = forward_pe
        pe_type = "forward"
    else:
        pe_ratio = trailing_pe
        pe_type = "trailing"

    if pe_ratio is None or pd.isna(pe_ratio):
        return {
            'score': 0,
            'pe_ratio': None,
            'signal': 'No P/E data available'
        }

    # Phase 2: Handle still-negative earnings (even forward)
    if pe_ratio < 0:
        return {
            'score': -1,
            'pe_ratio': pe_ratio,
            'signal': 'Negative earnings (both trailing and forward)'
        }

    # Phase 2: Get sector-specific thresholds if available
    pe_thresholds = fundamental_params['pe'].copy()
    if sector:
        sector_adjustments = config.get('sector_adjustments', {}).get(sector, {})
        threshold_overrides = sector_adjustments.get('threshold_overrides', {})
        if 'pe_fair' in threshold_overrides:
            pe_thresholds['fair'] = threshold_overrides['pe_fair']
        if 'pe_expensive' in threshold_overrides:
            pe_thresholds['speculative'] = threshold_overrides.get('pe_expensive', pe_thresholds['speculative'])

    # Scoring logic from spec with sector-specific thresholds
    if pe_ratio > fundamental_params['pe']['speculative'] and info.get('earningsGrowth', 0) < 0:
        score = -2
        signal = f"Speculative (P/E {pe_ratio:.1f} with declining earnings)"
    elif pe_ratio > pe_thresholds['fair']:
        score = -1
        signal = f"Expensive ({pe_type} P/E {pe_ratio:.1f})"
    elif pe_ratio < pe_thresholds['value']:
        score = 1
        signal = f"Value ({pe_type} P/E {pe_ratio:.1f})"
    else:
        score = 0
        signal = f"Fair ({pe_type} P/E {pe_ratio:.1f})"

    return {
        'score': score,
        'pe_ratio': pe_ratio,
        'pe_type': pe_type,
        'signal': signal
    }


def calculate_peg_score(info: Dict[str, Any], sector: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate PEG ratio score with improved edge case handling (Phase 2).

    Args:
        info: Stock info dictionary from yfinance
        sector: Stock sector for sector-specific thresholds

    Returns:
        Dictionary with score and details
    """
    fundamental_params = config.get_fundamental_params()

    # Get P/E and growth rate - Phase 2: use forward P/E for growth stocks
    trailing_pe = info.get('trailingPE')
    forward_pe = info.get('forwardPE')
    pe_ratio = forward_pe if forward_pe and forward_pe > 0 else trailing_pe

    earnings_growth = info.get('earningsGrowth')

    # Phase 2: Try to calculate our own growth estimate if missing
    if earnings_growth is None or pd.isna(earnings_growth):
        earnings_quarterly_growth = info.get('earningsQuarterlyGrowth')
        if earnings_quarterly_growth and not pd.isna(earnings_quarterly_growth):
            earnings_growth = earnings_quarterly_growth
        else:
            return {
                'score': 0,
                'peg_ratio': None,
                'signal': 'No growth data available'
            }

    if pe_ratio is None or pd.isna(pe_ratio):
        return {
            'score': 0,
            'peg_ratio': None,
            'signal': 'No P/E data available'
        }

    # Handle edge cases - Phase 2: Better handling of negative growth
    if pe_ratio <= 0:
        return {
            'score': -1,
            'peg_ratio': None,
            'signal': 'Negative earnings'
        }

    if earnings_growth <= 0:
        return {
            'score': -1,
            'peg_ratio': None,
            'signal': 'Negative earnings growth'
        }

    # Calculate PEG ratio
    # Convert earnings growth from decimal to percentage
    earnings_growth_pct = earnings_growth * 100
    peg_ratio = pe_ratio / earnings_growth_pct

    # Scoring logic from spec
    if peg_ratio < fundamental_params['peg']['attractive']:
        score = 1
        signal = "Attractive (undervalued for growth)"
    elif peg_ratio < fundamental_params['peg']['fair']:
        score = 0
        signal = "Fair"
    else:
        score = -1
        signal = "Expensive (overvalued even with growth)"

    return {
        'score': score,
        'peg_ratio': peg_ratio,
        'earnings_growth_pct': earnings_growth_pct,
        'signal': signal
    }


def calculate_roe_score(info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate Return on Equity score.

    Args:
        info: Stock info dictionary from yfinance

    Returns:
        Dictionary with score and details
    """
    fundamental_params = config.get_fundamental_params()

    # Get ROE
    roe = info.get('returnOnEquity')

    if roe is None or pd.isna(roe):
        return {
            'score': 0,
            'roe_percent': None,
            'signal': 'No ROE data available'
        }

    # Convert to percentage (yfinance returns as decimal, e.g., 0.15 = 15%)
    # But sometimes it's already a percentage, so check if value is > 1
    if roe > 1:
        # Already a percentage
        roe_percent = roe
    else:
        # Convert decimal to percentage
        roe_percent = roe * 100

    # Scoring logic from spec
    if roe_percent > fundamental_params['roe']['quality_threshold']:
        score = 1
        signal = "Quality (strong returns)"
    else:
        score = 0
        signal = "Adequate"

    return {
        'score': score,
        'roe_percent': roe_percent,
        'signal': signal
    }


def calculate_debt_equity_score(info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate Debt to Equity ratio score.

    Args:
        info: Stock info dictionary from yfinance

    Returns:
        Dictionary with score and details
    """
    fundamental_params = config.get_fundamental_params()

    # Get debt to equity ratio
    debt_to_equity = info.get('debtToEquity')

    if debt_to_equity is None or pd.isna(debt_to_equity):
        return {
            'score': 0,
            'debt_to_equity': None,
            'signal': 'No debt/equity data available'
        }

    # Convert from percentage to ratio if needed
    # yfinance sometimes returns it as percentage (e.g., 50.0 instead of 0.5)
    if debt_to_equity > 10:
        debt_to_equity = debt_to_equity / 100

    # Scoring logic from spec
    if debt_to_equity < fundamental_params['debt_equity']['healthy_threshold']:
        score = 1
        signal = "Healthy (low debt)"
    else:
        score = 0
        signal = "Acceptable"

    # Check for veto condition (handled in vetoes.py)
    if debt_to_equity > fundamental_params['debt_equity']['veto_threshold']:
        signal = "WARNING: High bankruptcy risk"

    return {
        'score': score,
        'debt_to_equity': debt_to_equity,
        'signal': signal
    }


def calculate_cash_flow_quality_score(info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate Cash Flow Quality score.

    Args:
        info: Stock info dictionary from yfinance

    Returns:
        Dictionary with score and details
    """
    fundamental_params = config.get_fundamental_params()

    # Get operating cash flow and net income
    operating_cash_flow = info.get('operatingCashflow')
    net_income = info.get('netIncomeToCommon')

    if operating_cash_flow is None or net_income is None or pd.isna(operating_cash_flow) or pd.isna(net_income):
        return {
            'score': 0,
            'cash_flow_quality': None,
            'signal': 'No cash flow data available'
        }

    # Handle edge case
    if net_income <= 0:
        return {
            'score': 0,
            'cash_flow_quality': None,
            'signal': 'Negative net income'
        }

    # Calculate cash flow quality ratio
    cash_flow_quality = operating_cash_flow / net_income

    # Scoring logic from spec
    if cash_flow_quality >= fundamental_params['cash_flow_quality']['quality_threshold']:
        score = 1
        signal = "Quality (cash-backed earnings)"
    else:
        score = 0
        signal = "Warning (accounting concerns)"

    return {
        'score': score,
        'cash_flow_quality': cash_flow_quality,
        'signal': signal
    }


def calculate_revenue_acceleration(ticker: str) -> Dict[str, Any]:
    """
    Calculate revenue growth acceleration score (Phase 5a).

    Analyzes quarterly revenue trends to detect if growth is accelerating.
    Professional signal: accelerating revenue growth often precedes stock outperformance.

    Scoring:
    - +2: Revenue growth accelerating (Q-2 < Q-1 < Q0)
    - +1: Revenue growing consistently
    - 0: Revenue stable or mixed trends
    - -1: Revenue growth decelerating
    - -2: Revenue declining

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dictionary with score and details
    """
    from data.fetcher import fetcher

    # Get Phase 5a config
    phase5_params = config.get('phase5a', {})
    quarters_lookback = phase5_params.get('revenue_acceleration', {}).get('quarters_lookback', 4)

    # get_quarterly_financials returns tuple: (income, balance, cashflow)
    quarterly_data = fetcher.get_quarterly_financials(ticker)

    if quarterly_data is None or quarterly_data[0] is None:
        return {
            'score': 0,
            'signal': 'No quarterly revenue data available',
            'revenue_growth_rates': None
        }

    # Extract income statement (first element of tuple)
    quarterly_income = quarterly_data[0]

    if quarterly_income.empty:
        return {
            'score': 0,
            'signal': 'No quarterly revenue data available',
            'revenue_growth_rates': None
        }

    # Get Total Revenue row (yfinance uses 'Total Revenue' or sometimes 'Revenue')
    if 'Total Revenue' in quarterly_income.index:
        revenue_row = quarterly_income.loc['Total Revenue']
    elif 'Revenue' in quarterly_income.index:
        revenue_row = quarterly_income.loc['Revenue']
    else:
        return {
            'score': 0,
            'signal': 'Revenue data not found in financials',
            'revenue_growth_rates': None
        }

    # Sort by date (most recent first) and take last N quarters
    revenue_data = revenue_row.sort_index(ascending=False).head(quarters_lookback)

    if len(revenue_data) < 3:
        return {
            'score': 0,
            'signal': 'Insufficient quarterly data (need 3+ quarters)',
            'revenue_growth_rates': None
        }

    # Calculate quarter-over-quarter growth rates
    # Note: revenue_data is sorted newest to oldest, so we need to reverse for calculation
    revenue_values = revenue_data.values[::-1]  # Reverse to oldest -> newest
    growth_rates = []

    for i in range(1, len(revenue_values)):
        if revenue_values[i-1] != 0:
            growth_rate = ((revenue_values[i] - revenue_values[i-1]) / abs(revenue_values[i-1])) * 100
            growth_rates.append(growth_rate)

    if len(growth_rates) < 2:
        return {
            'score': 0,
            'signal': 'Insufficient data for growth comparison',
            'revenue_growth_rates': growth_rates
        }

    # Analyze trend
    # Most recent growth rate
    latest_growth = growth_rates[-1]
    previous_growth = growth_rates[-2]

    # Check if all growth rates are positive
    all_positive = all(g > 0 for g in growth_rates)
    all_negative = all(g < 0 for g in growth_rates)

    # Check acceleration (each quarter growing faster than previous)
    is_accelerating = all(growth_rates[i] > growth_rates[i-1] for i in range(1, len(growth_rates)))
    is_decelerating = all(growth_rates[i] < growth_rates[i-1] for i in range(1, len(growth_rates)))

    # Scoring logic
    if is_accelerating and all_positive:
        score = 2
        signal = f"Accelerating ({', '.join([f'{g:.1f}%' for g in growth_rates[-3:]])})"
    elif all_positive and latest_growth > previous_growth:
        score = 2
        signal = f"Accelerating (latest: {latest_growth:.1f}% vs {previous_growth:.1f}%)"
    elif all_positive:
        score = 1
        signal = f"Growing (avg: {np.mean(growth_rates):.1f}%)"
    elif latest_growth > 0 and previous_growth > 0:
        score = 1
        signal = f"Growing (recent: {latest_growth:.1f}%)"
    elif is_decelerating and all_positive:
        score = -1
        signal = f"Decelerating ({', '.join([f'{g:.1f}%' for g in growth_rates[-3:]])})"
    elif latest_growth < 0 and previous_growth < 0:
        score = -2
        signal = f"Declining ({latest_growth:.1f}%, {previous_growth:.1f}%)"
    elif all_negative:
        score = -2
        signal = f"Declining (avg: {np.mean(growth_rates):.1f}%)"
    else:
        score = 0
        signal = f"Mixed trends (latest: {latest_growth:.1f}%)"

    return {
        'score': score,
        'signal': signal,
        'revenue_growth_rates': growth_rates,
        'latest_growth': latest_growth
    }


def calculate_all_fundamental_indicators(info: Dict[str, Any], sector: Optional[str] = None, ticker: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate all fundamental indicators (Phase 2: with sector-specific thresholds, Phase 5a: revenue acceleration).

    Args:
        info: Stock info dictionary from yfinance
        sector: Stock sector for sector-specific thresholds
        ticker: Stock ticker symbol (Phase 5a: required for revenue acceleration)

    Returns:
        Dictionary with all fundamental scores and details
    """
    pe_result = calculate_pe_score(info, sector)
    peg_result = calculate_peg_score(info, sector)
    roe_result = calculate_roe_score(info)
    debt_result = calculate_debt_equity_score(info)
    cash_flow_result = calculate_cash_flow_quality_score(info)

    # Phase 5a: Revenue acceleration (only if ticker provided)
    if ticker:
        revenue_accel_result = calculate_revenue_acceleration(ticker)
    else:
        revenue_accel_result = {'score': 0, 'signal': 'Ticker not provided'}

    # Calculate total raw score
    raw_score = (
        pe_result['score'] +
        peg_result['score'] +
        roe_result['score'] +
        debt_result['score'] +
        cash_flow_result['score'] +
        revenue_accel_result['score']  # Phase 5a
    )

    # Normalize to percentage (-100 to +100)
    # Phase 5a: Updated max from 5.0 to 8.0 (added revenue acceleration +2/-2)
    max_score = config.get('score_ranges.fundamental_max', 8.0)
    normalized_score = (raw_score / max_score) * 100

    return {
        'raw_score': raw_score,
        'normalized_score': normalized_score,
        'pe': pe_result,
        'peg': peg_result,
        'roe': roe_result,
        'debt_equity': debt_result,
        'cash_flow_quality': cash_flow_result,
        'revenue_acceleration': revenue_accel_result  # Phase 5a
    }
