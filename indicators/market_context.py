"""
Market context indicators.
VIX levels, sector relative strength, and market regime detection.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

from utils.config import config
from data.fetcher import fetcher


def calculate_vix_score(vix_value: float) -> Dict[str, Any]:
    """
    Calculate VIX score (fear gauge).

    High VIX = high fear = contrarian buying opportunity.

    Args:
        vix_value: Current VIX value

    Returns:
        Dictionary with score and details
    """
    market_params = config.get_market_params()

    # Scoring logic from spec
    if vix_value > market_params['vix']['extreme_fear']:
        score = 2
        signal = "Extreme fear (contrarian buying opportunity)"
    elif vix_value > market_params['vix']['moderate_fear']:
        score = 1
        signal = "Moderate fear (selective opportunities)"
    elif vix_value > market_params['vix']['normal_low']:
        score = 0
        signal = "Normal conditions"
    else:
        score = -1
        signal = "Complacency (potential correction ahead)"

    return {
        'score': score,
        'vix_value': vix_value,
        'signal': signal
    }


def calculate_sector_relative_strength(
    stock_df: pd.DataFrame,
    sector_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Calculate sector relative strength.

    Compares stock performance to its sector.

    Args:
        stock_df: Stock price DataFrame
        sector_df: Sector ETF price DataFrame

    Returns:
        Dictionary with score and details
    """
    market_params = config.get_market_params()
    lookback_days = market_params['sector_relative']['lookback_days']

    # Ensure we have enough data
    if len(stock_df) < lookback_days or len(sector_df) < lookback_days:
        return {
            'score': 0,
            'relative_strength': 0,
            'signal': 'Insufficient data'
        }

    # Calculate returns over lookback period
    stock_return = ((stock_df['Close'].iloc[-1] - stock_df['Close'].iloc[-lookback_days]) /
                    stock_df['Close'].iloc[-lookback_days]) * 100

    sector_return = ((sector_df['Close'].iloc[-1] - sector_df['Close'].iloc[-lookback_days]) /
                     sector_df['Close'].iloc[-lookback_days]) * 100

    # Calculate relative strength
    relative_strength = stock_return - sector_return

    # Scoring logic from spec
    outperform_threshold = market_params['sector_relative']['outperform_threshold']
    underperform_threshold = market_params['sector_relative']['underperform_threshold']

    if relative_strength > outperform_threshold:
        score = 1
        signal = "Outperforming (stock-specific strength)"
    elif relative_strength < underperform_threshold:
        score = -1
        signal = "Underperforming (stock-specific weakness)"
    else:
        score = 0
        signal = "Neutral (moving with sector)"

    return {
        'score': score,
        'relative_strength': relative_strength,
        'stock_return': stock_return,
        'sector_return': sector_return,
        'signal': signal
    }


def calculate_market_regime(sp500_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate market regime (bull vs bear).

    Based on S&P 500 vs 200-day moving average.

    Args:
        sp500_df: S&P 500 price DataFrame

    Returns:
        Dictionary with score and details
    """
    market_params = config.get_market_params()
    ma_period = market_params['regime']['ma_period']

    if len(sp500_df) < ma_period:
        return {
            'score': 0,
            'regime': 'Unknown',
            'signal': 'Insufficient data'
        }

    # Calculate 200-day moving average
    ma_200 = sp500_df['Close'].rolling(window=ma_period).mean()
    current_price = sp500_df['Close'].iloc[-1]
    current_ma = ma_200.iloc[-1]

    # Scoring logic from spec
    if current_price > current_ma:
        score = 1
        regime = "Bull"
        signal = "Bull market (rising tide lifts boats)"
    else:
        score = -1
        regime = "Bear"
        signal = "Bear market (headwinds for most stocks)"

    return {
        'score': score,
        'regime': regime,
        'sp500_price': current_price,
        'sp500_ma_200': current_ma,
        'signal': signal
    }


def calculate_all_market_context_indicators(
    ticker: str,
    stock_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Calculate all market context indicators.

    Args:
        ticker: Stock ticker symbol
        stock_df: Stock price DataFrame

    Returns:
        Dictionary with all market context scores and details
    """
    indices = config.get_indices()

    # Get VIX data
    vix_df = fetcher.get_market_data(indices['vix'], period='1mo')
    if vix_df is not None and not vix_df.empty:
        vix_value = vix_df['Close'].iloc[-1]
        vix_result = calculate_vix_score(vix_value)
    else:
        vix_result = {
            'score': 0,
            'vix_value': None,
            'signal': 'VIX data unavailable'
        }

    # Get sector ETF and calculate relative strength
    sector_etf = fetcher.get_sector_etf(ticker)
    sector_df = fetcher.get_market_data(sector_etf, period='6mo')
    if sector_df is not None and not sector_df.empty:
        sector_result = calculate_sector_relative_strength(stock_df, sector_df)
    else:
        sector_result = {
            'score': 0,
            'relative_strength': 0,
            'signal': 'Sector data unavailable'
        }

    # Get S&P 500 data and calculate market regime
    sp500_df = fetcher.get_market_data(indices['sp500'], period='1y')
    if sp500_df is not None and not sp500_df.empty:
        regime_result = calculate_market_regime(sp500_df)
    else:
        regime_result = {
            'score': 0,
            'regime': 'Unknown',
            'signal': 'S&P 500 data unavailable'
        }

    # Calculate total raw score
    raw_score = (
        vix_result['score'] +
        sector_result['score'] +
        regime_result['score']
    )

    # Normalize to percentage (-100 to +100)
    max_score = config.get('score_ranges.market_max', 4.0)
    normalized_score = (raw_score / max_score) * 100

    return {
        'raw_score': raw_score,
        'normalized_score': normalized_score,
        'vix': vix_result,
        'sector_relative': sector_result,
        'market_regime': regime_result,
        'sector_etf': sector_etf
    }
