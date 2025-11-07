"""
Volume analysis indicators.
Detects institutional accumulation/distribution and volume-price relationships.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

from utils.config import config


def calculate_volume_trend(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate volume trend analysis.

    Detects gradual institutional accumulation vs sudden spikes.

    Args:
        df: DataFrame with volume data

    Returns:
        Dictionary with score and details
    """
    volume_params = config.get_volume_params()
    recent_period = volume_params['recent_period']
    previous_period = volume_params['previous_period']

    if len(df) < recent_period + previous_period:
        return {
            'score': 0,
            'volume_change_percent': 0,
            'signal': 'Insufficient data'
        }

    # Calculate recent and previous average volumes
    recent_avg_volume = df['Volume'].iloc[-recent_period:].mean()
    previous_avg_volume = df['Volume'].iloc[-(recent_period + previous_period):-recent_period].mean()

    # Calculate volume change percentage
    if previous_avg_volume > 0:
        volume_change_percent = ((recent_avg_volume - previous_avg_volume) / previous_avg_volume) * 100
    else:
        volume_change_percent = 0

    # Get recent price change to determine accumulation vs distribution
    recent_price_change = df['Close'].iloc[-1] - df['Close'].iloc[-recent_period]

    # Scoring logic from spec
    accum_min = volume_params['accumulation_threshold_min'] * 100
    accum_max = volume_params['accumulation_threshold_max'] * 100
    dist_threshold = volume_params['distribution_threshold'] * 100

    if accum_min <= volume_change_percent <= accum_max and recent_price_change >= 0:
        score = 2
        signal = "Accumulation (gradual institutional buying)"
    elif volume_change_percent > dist_threshold and recent_price_change < 0:
        score = -2
        signal = "Distribution (institutional selling)"
    else:
        score = 0
        signal = "Neutral"

    return {
        'score': score,
        'volume_change_percent': volume_change_percent,
        'recent_avg_volume': recent_avg_volume,
        'previous_avg_volume': previous_avg_volume,
        'signal': signal
    }


def calculate_volume_price_relationship(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate volume-price relationship.

    Strong moves on high volume = confirmation.
    Strong moves on low volume = warning sign.

    Args:
        df: DataFrame with price and volume data

    Returns:
        Dictionary with score and details
    """
    volume_params = config.get_volume_params()
    period = volume_params['price_volume_period']

    if len(df) < period + 1:
        return {
            'score': 0,
            'signal': 'Insufficient data'
        }

    # Calculate average volume
    avg_volume = df['Volume'].iloc[-period:].mean()
    current_volume = df['Volume'].iloc[-1]

    # Calculate recent price change
    price_change = df['Close'].iloc[-1] - df['Close'].iloc[-2]
    price_change_percent = (price_change / df['Close'].iloc[-2]) * 100

    # Scoring logic from spec
    if price_change > 0 and current_volume > avg_volume * 1.2:
        score = 1
        signal = "Bullish (up on strong volume)"
    elif price_change > 0 and current_volume < avg_volume * 0.8:
        score = -1
        signal = "Bearish (up on weak volume - unsustainable)"
    elif price_change < 0 and current_volume < avg_volume * 0.8:
        score = 1
        signal = "Bullish (down on low volume - no sellers)"
    else:
        score = 0
        signal = "Neutral"

    return {
        'score': score,
        'current_volume': current_volume,
        'avg_volume': avg_volume,
        'volume_ratio': current_volume / avg_volume if avg_volume > 0 else 0,
        'price_change_percent': price_change_percent,
        'signal': signal
    }


def calculate_all_volume_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate all volume indicators.

    Args:
        df: DataFrame with price and volume data

    Returns:
        Dictionary with all volume scores and details
    """
    volume_trend_result = calculate_volume_trend(df)
    volume_price_result = calculate_volume_price_relationship(df)

    # Calculate total raw score
    raw_score = (
        volume_trend_result['score'] +
        volume_price_result['score']
    )

    # Normalize to percentage (-100 to +100)
    max_score = config.get('score_ranges.volume_max', 3.0)
    normalized_score = (raw_score / max_score) * 100

    return {
        'raw_score': raw_score,
        'normalized_score': normalized_score,
        'volume_trend': volume_trend_result,
        'volume_price': volume_price_result
    }
