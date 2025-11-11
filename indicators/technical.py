"""
Technical indicators: Moving Averages, RSI, MACD, Momentum.
Calculations based on professional hedge fund methodologies.
"""

import pandas as pd
from typing import Dict, Any

from utils.config import config


def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """
    Calculate Exponential Moving Average.

    Args:
        data: Price series
        period: EMA period

    Returns:
        EMA series
    """
    return data.ewm(span=period, adjust=False).mean()


def calculate_ma_position(df: pd.DataFrame, beta: float = 1.0) -> Dict[str, Any]:
    """
    Calculate Moving Average position score.

    Args:
        df: DataFrame with price data (must have 'Close' column)
        beta: Stock beta (for adaptive thresholds)

    Returns:
        Dictionary with score and details
    """
    tech_params = config.get_technical_params()
    short_period = tech_params['ma']['short_period']
    long_period = tech_params['ma']['long_period']

    current_price = df['Close'].iloc[-1]
    ema_50 = calculate_ema(df['Close'], short_period).iloc[-1]
    ema_200 = calculate_ema(df['Close'], long_period).iloc[-1]

    # Scoring logic from spec
    if current_price > ema_50 and ema_50 > ema_200:
        score = 2
        signal = "Bullish (Golden Cross setup)"
    elif current_price < ema_50 and ema_50 < ema_200:
        score = -2
        signal = "Bearish (Death Cross)"
    else:
        score = 0
        signal = "Neutral"

    return {
        'score': score,
        'current_price': current_price,
        'ema_50': ema_50,
        'ema_200': ema_200,
        'signal': signal
    }


def calculate_momentum(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate 12-month momentum skipping recent month.

    Professional standard: 252-day lookback, skip 21 recent days.

    Args:
        df: DataFrame with price data

    Returns:
        Dictionary with score and details
    """
    tech_params = config.get_technical_params()
    lookback_days = tech_params['momentum']['lookback_days']
    skip_recent = tech_params['momentum']['skip_recent_days']

    if len(df) < lookback_days + skip_recent:
        return {
            'score': 0,
            'momentum_percent': 0,
            'signal': 'Insufficient data'
        }

    # Skip recent month for mean-reversion effect
    current_price = df['Close'].iloc[-skip_recent - 1]
    past_price = df['Close'].iloc[-(lookback_days + skip_recent)]

    momentum_percent = ((current_price - past_price) / past_price) * 100

    # Scoring logic from spec
    if momentum_percent > 25:
        score = 2
        signal = "Strong Bullish"
    elif momentum_percent > 10:
        score = 1
        signal = "Bullish"
    elif momentum_percent > -10:
        score = 0
        signal = "Neutral"
    elif momentum_percent > -25:
        score = -1
        signal = "Bearish"
    else:
        score = -2
        signal = "Strong Bearish"

    return {
        'score': score,
        'momentum_percent': momentum_percent,
        'signal': signal
    }


def calculate_rsi(df: pd.DataFrame, beta: float = 1.0) -> Dict[str, Any]:
    """
    Calculate Relative Strength Index.

    Uses adaptive thresholds based on beta.

    Args:
        df: DataFrame with price data
        beta: Stock beta (for adaptive thresholds)

    Returns:
        Dictionary with score and details
    """
    tech_params = config.get_technical_params()
    period = tech_params['rsi']['period']

    # Calculate price changes
    delta = df['Close'].diff()

    # Separate gains and losses
    gains = delta.clip(lower=0)
    losses = (-delta).clip(lower=0)

    # Calculate average gains and losses
    avg_gains = gains.rolling(window=period, min_periods=period).mean()
    avg_losses = losses.rolling(window=period, min_periods=period).mean()

    # Calculate RS and RSI
    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]

    # Adaptive thresholds based on beta (from spec)
    if beta > tech_params['rsi']['high_beta_threshold']:
        overbought = tech_params['rsi']['volatile_overbought']
        oversold = tech_params['rsi']['volatile_oversold']
        threshold_type = "High volatility (80/20)"
    else:
        overbought = tech_params['rsi']['standard_overbought']
        oversold = tech_params['rsi']['standard_oversold']
        threshold_type = "Standard (70/30)"

    # Scoring logic from spec
    if current_rsi > overbought:
        score = -1
        signal = "Overbought"
    elif current_rsi < oversold:
        score = 1
        signal = "Oversold"
    else:
        score = 0
        signal = "Neutral"

    return {
        'score': score,
        'rsi': current_rsi,
        'overbought_threshold': overbought,
        'oversold_threshold': oversold,
        'threshold_type': threshold_type,
        'signal': signal
    }


def calculate_macd(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Standard 12/26/9 parameters.

    Args:
        df: DataFrame with price data

    Returns:
        Dictionary with score and details
    """
    tech_params = config.get_technical_params()
    fast_period = tech_params['macd']['fast_period']
    slow_period = tech_params['macd']['slow_period']
    signal_period = tech_params['macd']['signal_period']

    # Calculate MACD line
    ema_fast = calculate_ema(df['Close'], fast_period)
    ema_slow = calculate_ema(df['Close'], slow_period)
    macd_line = ema_fast - ema_slow

    # Calculate signal line
    signal_line = calculate_ema(macd_line, signal_period)

    # Calculate histogram
    histogram = macd_line - signal_line

    # Get recent values
    current_macd = macd_line.iloc[-1]
    current_signal = signal_line.iloc[-1]
    current_histogram = histogram.iloc[-1]
    previous_histogram = histogram.iloc[-2] if len(histogram) > 1 else 0

    # Scoring logic from spec
    # Bullish: crossover above signal OR positive and increasing histogram
    # Bearish: crossover below signal OR negative and decreasing histogram
    if current_macd > current_signal and current_histogram > 0 and current_histogram > previous_histogram:
        score = 1
        signal = "Bullish (positive and increasing)"
    elif current_macd < current_signal and current_histogram < 0 and current_histogram < previous_histogram:
        score = -1
        signal = "Bearish (negative and decreasing)"
    elif current_macd > current_signal:
        score = 1
        signal = "Bullish crossover"
    elif current_macd < current_signal:
        score = -1
        signal = "Bearish crossover"
    else:
        score = 0
        signal = "Neutral"

    return {
        'score': score,
        'macd_line': current_macd,
        'signal_line': current_signal,
        'histogram': current_histogram,
        'signal': signal
    }


def calculate_52week_breakout(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate 52-week high breakout score.

    Professional momentum signal: stocks near/breaking 52-week highs often continue higher.

    Scoring:
    - +2: Breaking above 52-week high on volume (50%+ above average)
    - +1: Within 2% of 52-week high
    - 0: Normal range
    - -1: More than 20% below 52-week high (weak)
    - -2: More than 40% below 52-week high (very weak)

    Args:
        df: DataFrame with price data (needs 252 days for full 52-week period)

    Returns:
        Dictionary with score and details
    """
    # Get Phase 5a config
    phase5_params = config.get('phase5a', {})
    near_high_threshold = phase5_params.get('breakout_52week', {}).get('near_high_threshold', 0.02)
    volume_multiplier = phase5_params.get('breakout_52week', {}).get('volume_confirmation_multiplier', 1.5)

    # Need at least 252 days (1 trading year)
    if len(df) < 252:
        return {
            'score': 0,
            'signal': 'Insufficient data',
            '52week_high': None,
            'current_price': None,
            'distance_from_high': None
        }

    # Calculate 52-week high (last 252 days)
    lookback_df = df.tail(252)
    week_52_high = lookback_df['High'].max()
    current_price = df['Close'].iloc[-1]

    # Calculate distance from high
    distance_from_high = (current_price - week_52_high) / week_52_high

    # Check volume confirmation
    avg_volume = df['Volume'].tail(20).mean()
    current_volume = df['Volume'].iloc[-1]
    volume_confirmed = current_volume > (avg_volume * volume_multiplier)

    # Scoring logic
    if distance_from_high >= 0 and volume_confirmed:
        # Breaking above 52-week high on volume
        score = 2
        signal = f"Breakout on volume ({current_volume/avg_volume:.1f}x avg)"
    elif distance_from_high >= -near_high_threshold:
        # Within 2% of 52-week high
        score = 1
        signal = f"Near 52-week high ({abs(distance_from_high)*100:.1f}% below)"
    elif distance_from_high >= -0.20:
        # Within 20% of high - normal
        score = 0
        signal = f"Normal ({abs(distance_from_high)*100:.1f}% from high)"
    elif distance_from_high >= -0.40:
        # 20-40% below high - weak
        score = -1
        signal = f"Weak ({abs(distance_from_high)*100:.1f}% from high)"
    else:
        # More than 40% below high - very weak
        score = -2
        signal = f"Very weak ({abs(distance_from_high)*100:.1f}% from high)"

    return {
        'score': score,
        'signal': signal,
        '52week_high': week_52_high,
        'current_price': current_price,
        'distance_from_high': distance_from_high,
        'volume_confirmed': volume_confirmed
    }


def calculate_all_technical_indicators(df: pd.DataFrame, beta: float = 1.0) -> Dict[str, Any]:
    """
    Calculate all technical indicators.

    Args:
        df: DataFrame with price data
        beta: Stock beta

    Returns:
        Dictionary with all technical scores and details
    """
    ma_result = calculate_ma_position(df, beta)
    momentum_result = calculate_momentum(df)
    rsi_result = calculate_rsi(df, beta)
    macd_result = calculate_macd(df)
    breakout_52w_result = calculate_52week_breakout(df)  # Phase 5a

    # Calculate total raw score
    raw_score = (
        ma_result['score'] +
        momentum_result['score'] +
        rsi_result['score'] +
        macd_result['score'] +
        breakout_52w_result['score']  # Phase 5a
    )

    # Normalize to percentage (-100 to +100)
    max_score = config.get('score_ranges.trend_max', 10.0)  # Phase 5a: updated from 6.0
    normalized_score = (raw_score / max_score) * 100

    return {
        'raw_score': raw_score,
        'normalized_score': normalized_score,
        'ma_position': ma_result,
        'momentum': momentum_result,
        'rsi': rsi_result,
        'macd': macd_result,
        'breakout_52week': breakout_52w_result  # Phase 5a
    }
