"""
Fundamental analysis indicators.
Valuation metrics and quality metrics based on financial statements.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

from utils.config import config


def calculate_pe_score(info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate P/E ratio score.

    Args:
        info: Stock info dictionary from yfinance

    Returns:
        Dictionary with score and details
    """
    fundamental_params = config.get_fundamental_params()

    # Get P/E ratio
    pe_ratio = info.get('trailingPE') or info.get('forwardPE')

    if pe_ratio is None or pd.isna(pe_ratio):
        return {
            'score': 0,
            'pe_ratio': None,
            'signal': 'No P/E data available'
        }

    # Handle negative earnings
    if pe_ratio < 0:
        return {
            'score': -1,
            'pe_ratio': pe_ratio,
            'signal': 'Negative earnings'
        }

    # Scoring logic from spec
    if pe_ratio > fundamental_params['pe']['speculative'] and info.get('earningsGrowth', 0) < 0:
        score = -2
        signal = "Speculative (high P/E with declining earnings)"
    elif pe_ratio > fundamental_params['pe']['fair']:
        score = -1
        signal = "Expensive"
    elif pe_ratio < fundamental_params['pe']['value']:
        score = 1
        signal = "Value"
    else:
        score = 0
        signal = "Fair"

    return {
        'score': score,
        'pe_ratio': pe_ratio,
        'signal': signal
    }


def calculate_peg_score(info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate PEG ratio score.

    Args:
        info: Stock info dictionary from yfinance

    Returns:
        Dictionary with score and details
    """
    fundamental_params = config.get_fundamental_params()

    # Get P/E and growth rate
    pe_ratio = info.get('trailingPE') or info.get('forwardPE')
    earnings_growth = info.get('earningsGrowth')

    if pe_ratio is None or earnings_growth is None or pd.isna(pe_ratio) or pd.isna(earnings_growth):
        return {
            'score': 0,
            'peg_ratio': None,
            'signal': 'No PEG data available'
        }

    # Handle edge cases
    if pe_ratio <= 0 or earnings_growth <= 0:
        return {
            'score': 0,
            'peg_ratio': None,
            'signal': 'Invalid PEG (negative P/E or growth)'
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


def calculate_all_fundamental_indicators(info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate all fundamental indicators.

    Args:
        info: Stock info dictionary from yfinance

    Returns:
        Dictionary with all fundamental scores and details
    """
    pe_result = calculate_pe_score(info)
    peg_result = calculate_peg_score(info)
    roe_result = calculate_roe_score(info)
    debt_result = calculate_debt_equity_score(info)
    cash_flow_result = calculate_cash_flow_quality_score(info)

    # Calculate total raw score
    raw_score = (
        pe_result['score'] +
        peg_result['score'] +
        roe_result['score'] +
        debt_result['score'] +
        cash_flow_result['score']
    )

    # Normalize to percentage (-100 to +100)
    # Note: Fundamental max is 5.0 (asymmetric, rewards quality)
    max_score = config.get('score_ranges.fundamental_max', 5.0)
    normalized_score = (raw_score / max_score) * 100

    return {
        'raw_score': raw_score,
        'normalized_score': normalized_score,
        'pe': pe_result,
        'peg': peg_result,
        'roe': roe_result,
        'debt_equity': debt_result,
        'cash_flow_quality': cash_flow_result
    }
