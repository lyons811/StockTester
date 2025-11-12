"""
Technical indicators: Moving Averages, RSI, MACD, Momentum.
Calculations based on professional hedge fund methodologies.
"""

import pandas as pd
from typing import Dict, Any, Optional

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


def calculate_bollinger_bands(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate Bollinger Bands and detect squeeze/breakout patterns (Phase 5b).

    Bollinger Bands show volatility and potential reversals.
    Squeeze (low volatility) often precedes explosive moves.

    Scoring:
    - +2: BB squeeze + breakout above upper band (explosive momentum)
    - +1: Price at lower BB in uptrend (oversold bounce setup)
    - 0: Neutral
    - -1: Price at upper BB with RSI > 70 (overbought)

    Args:
        df: Price DataFrame with Close column

    Returns:
        Dict with score, signal, bandwidth, squeeze status
    """
    # Get Phase 5b config
    phase5b_params = config.get('phase5b', {})
    bb_params = phase5b_params.get('bollinger_bands', {})
    period = bb_params.get('period', 20)
    std_dev = bb_params.get('std_dev', 2.0)
    squeeze_percentile = bb_params.get('squeeze_percentile', 20)

    result = {
        'score': 0,
        'signal': 'Neutral',
        'bandwidth': None,
        'squeeze_detected': False
    }

    try:
        if len(df) < period:
            result['signal'] = 'Insufficient data'
            return result

        # Calculate Bollinger Bands
        close = df['Close']
        middle_band = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper_band = middle_band + (std_dev * std)
        lower_band = middle_band - (std_dev * std)

        # Calculate bandwidth (volatility measure)
        bandwidth = (upper_band - lower_band) / middle_band
        current_bandwidth = bandwidth.iloc[-1]

        # Detect squeeze (bandwidth < 20th percentile = low volatility)
        lookback_periods = min(100, len(bandwidth) - 1)
        if lookback_periods >= 20:
            percentile_threshold = bandwidth.iloc[-lookback_periods:].quantile(squeeze_percentile / 100.0)
            squeeze_detected = current_bandwidth < percentile_threshold
        else:
            squeeze_detected = False

        current_price = close.iloc[-1]
        current_upper = upper_band.iloc[-1]
        current_lower = lower_band.iloc[-1]

        # Calculate RSI for overbought check
        delta = close.diff()
        gains = delta.clip(lower=0)
        losses = (-delta).clip(lower=0)
        avg_gains = gains.rolling(window=14, min_periods=14).mean()
        avg_losses = losses.rolling(window=14, min_periods=14).mean()
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1] if len(rsi) > 14 else 50

        # Check if in uptrend (50 EMA > 200 EMA)
        if len(close) >= 200:
            ema_50 = calculate_ema(close, 50).iloc[-1]
            ema_200 = calculate_ema(close, 200).iloc[-1]
            uptrend = ema_50 > ema_200
        else:
            uptrend = True

        # Scoring logic
        if squeeze_detected and current_price > current_upper:
            # Squeeze + breakout above upper band = explosive momentum
            result['score'] = 2
            result['signal'] = 'Squeeze breakout (strong momentum)'
            result['squeeze_detected'] = True
        elif uptrend and current_price <= current_lower:
            # Oversold in uptrend = bounce opportunity
            result['score'] = 1
            result['signal'] = 'Oversold bounce setup'
        elif current_price >= current_upper and current_rsi > 70:
            # Overbought at upper band = caution
            result['score'] = -1
            result['signal'] = 'Overbought (upper BB + RSI > 70)'
        else:
            pct_of_band = (current_price - current_lower) / (current_upper - current_lower)
            result['signal'] = f'Price in middle range ({pct_of_band:.1%} of band)'

        result['bandwidth'] = round(current_bandwidth * 100, 2)

    except Exception as e:
        result['signal'] = f'Error: {str(e)[:50]}'

    return result


def calculate_consolidation_pattern(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate ATR-based consolidation pattern detection (Phase 5b).

    Identifies "coiling spring" patterns: declining ATR while price near highs.
    These patterns often precede explosive moves.

    Scoring:
    - +2: Tight 5-10 day consolidation after 20%+ rally (continuation setup)
    - +1: ATR declining 10+ days while price near highs (accumulation)
    - 0: Neutral
    - -1: Wide ATR spikes (volatility, uncertainty)

    Args:
        df: Price DataFrame with OHLC data

    Returns:
        Dict with score, signal, ATR info
    """
    # Get Phase 5b config
    phase5b_params = config.get('phase5b', {})
    cons_params = phase5b_params.get('consolidation', {})
    atr_period = cons_params.get('atr_period', 14)
    atr_decline_days = cons_params.get('atr_decline_days', 10)
    tight_days = cons_params.get('tight_consolidation_days', 7)
    tight_range_pct = cons_params.get('tight_range_pct', 0.02)
    rally_threshold = cons_params.get('rally_threshold', 0.20)

    result = {
        'score': 0,
        'signal': 'Neutral',
        'atr': None,
        'atr_trend': 'Neutral'
    }

    try:
        if len(df) < atr_period + atr_decline_days:
            result['signal'] = 'Insufficient data'
            return result

        # Calculate ATR (Average True Range)
        high = df['High']
        low = df['Low']
        close = df['Close']

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=atr_period).mean()

        current_atr = atr.iloc[-1]
        current_price = close.iloc[-1]

        # Calculate 52-week high
        lookback_252 = min(252, len(df))
        week_52_high = high.tail(lookback_252).max()
        distance_from_high = (current_price - week_52_high) / week_52_high

        # Check if ATR declining
        atr_declining_count = 0
        for i in range(1, min(atr_decline_days + 1, len(atr))):
            if atr.iloc[-i] < atr.iloc[-i-1]:
                atr_declining_count += 1

        atr_declining = atr_declining_count >= atr_decline_days

        # Check for tight consolidation after rally
        if len(df) >= tight_days + 20:
            # Check recent rally (20 days before consolidation)
            price_20d_ago = close.iloc[-(tight_days + 20)]
            price_at_consolidation_start = close.iloc[-tight_days]
            rally_gain = (price_at_consolidation_start - price_20d_ago) / price_20d_ago

            # Check if recent days have tight range
            recent_ranges = (high.tail(tight_days) - low.tail(tight_days)) / close.tail(tight_days)
            tight_consolidation = (recent_ranges < tight_range_pct).sum() >= (tight_days * 0.7)

            if rally_gain > rally_threshold and tight_consolidation:
                result['score'] = 2
                result['signal'] = f'Tight consolidation after {rally_gain*100:.1f}% rally'
                result['atr_trend'] = 'Tightening'
                result['atr'] = round(current_atr, 2)
                return result

        # Check ATR declining while near highs (accumulation)
        if atr_declining and distance_from_high >= -0.05:  # Within 5% of 52-week high
            result['score'] = 1
            result['signal'] = f'ATR declining ({atr_declining_count}d), price near highs'
            result['atr_trend'] = 'Declining'
        else:
            # Check for wide ATR spikes (volatility)
            atr_avg = atr.tail(20).mean()
            if current_atr > atr_avg * 1.5:
                result['score'] = -1
                result['signal'] = 'High volatility (ATR spike)'
                result['atr_trend'] = 'Expanding'
            else:
                result['signal'] = f'Normal consolidation pattern'

        result['atr'] = round(current_atr, 2)

    except Exception as e:
        result['signal'] = f'Error: {str(e)[:50]}'

    return result


def calculate_multi_timeframe_alignment(df: pd.DataFrame, ticker: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate multi-timeframe trend alignment (Phase 5b).

    Checks daily AND weekly trend alignment to reduce whipsaws.
    Only trade when all timeframes agree.

    Scoring:
    - +1: Daily and weekly both uptrend (aligned bullish, high confidence)
    - 0: Mixed signals (choppy market)
    - -1: Daily uptrend but weekly downtrend (counter-trend, risky)

    Args:
        df: Daily price DataFrame
        ticker: Stock ticker (for additional data if needed)

    Returns:
        Dict with score, signal, timeframe info
    """
    # Get Phase 5b config
    phase5b_params = config.get('phase5b', {})
    mtf_params = phase5b_params.get('multi_timeframe', {})
    daily_ema_period = mtf_params.get('daily_ema_period', 50)
    weekly_ema_period = mtf_params.get('weekly_ema_period', 50)

    result = {
        'score': 0,
        'signal': 'Neutral',
        'daily_trend': 'Neutral',
        'weekly_trend': 'Neutral'
    }

    try:
        if len(df) < daily_ema_period:
            result['signal'] = 'Insufficient data'
            return result

        # Daily trend (50 EMA slope)
        daily_ema = calculate_ema(df['Close'], daily_ema_period)
        daily_slope = (daily_ema.iloc[-1] - daily_ema.iloc[-10]) / daily_ema.iloc[-10] if len(daily_ema) >= 10 else 0
        daily_uptrend = daily_slope > 0

        # Weekly trend (resample daily to weekly)
        # Estimate weekly by grouping every 5 trading days
        df_weekly = df.copy()
        weekly_close = df_weekly['Close'].iloc[::5]  # Every 5th trading day ≈ weekly

        if len(weekly_close) >= weekly_ema_period:
            weekly_ema = calculate_ema(weekly_close, weekly_ema_period)
            if len(weekly_ema) >= 3:
                weekly_slope = (weekly_ema.iloc[-1] - weekly_ema.iloc[-3]) / weekly_ema.iloc[-3]
                weekly_uptrend = weekly_slope > 0
            else:
                weekly_uptrend = None
        else:
            weekly_uptrend = None

        # Scoring logic
        if daily_uptrend and weekly_uptrend:
            result['score'] = 1
            result['signal'] = 'Daily and weekly aligned bullish'
            result['daily_trend'] = 'Uptrend'
            result['weekly_trend'] = 'Uptrend'
        elif daily_uptrend and weekly_uptrend == False:
            result['score'] = -1
            result['signal'] = 'Counter-trend (daily up, weekly down)'
            result['daily_trend'] = 'Uptrend'
            result['weekly_trend'] = 'Downtrend'
        elif not daily_uptrend and not weekly_uptrend:
            result['score'] = 0
            result['signal'] = 'Both timeframes bearish'
            result['daily_trend'] = 'Downtrend'
            result['weekly_trend'] = 'Downtrend'
        elif weekly_uptrend is None:
            result['signal'] = 'Insufficient weekly data'
            result['daily_trend'] = 'Uptrend' if daily_uptrend else 'Downtrend'
        else:
            result['signal'] = 'Mixed signals'
            result['daily_trend'] = 'Uptrend' if daily_uptrend else 'Downtrend'
            result['weekly_trend'] = 'Uptrend' if weekly_uptrend else 'Downtrend'

    except Exception as e:
        result['signal'] = f'Error: {str(e)[:50]}'

    return result


def calculate_short_term_sr(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate short-term support/resistance breakout detection (Phase 5b).

    Identifies key 60-day support/resistance levels and detects bounces/breakouts.
    Complements the 52-week breakout indicator (Phase 5a) by focusing on short-term levels.

    Scoring:
    - +1: Bouncing off major support (within 2% of recent swing low)
    - 0: Neutral (between levels)
    - -1: Stuck at resistance (multiple failed attempts at recent swing high)

    Args:
        df: Price DataFrame with OHLC and Volume data

    Returns:
        Dict with score, signal, support/resistance levels
    """
    # Get Phase 5b config
    phase5b_params = config.get('phase5b', {})
    sr_params = phase5b_params.get('support_resistance', {})
    lookback_window = sr_params.get('lookback_window', 60)
    level_proximity = sr_params.get('level_proximity', 0.02)

    result = {
        'score': 0,
        'signal': 'Neutral',
        'support_level': None,
        'resistance_level': None
    }

    try:
        if len(df) < lookback_window:
            result['signal'] = 'Insufficient data'
            return result

        # Get recent price action
        recent_df = df.tail(lookback_window)
        current_price = df['Close'].iloc[-1]
        high = recent_df['High']
        low = recent_df['Low']

        # Find swing lows (support levels) - local minima
        swing_lows = []
        for i in range(5, len(recent_df) - 5):
            window = low.iloc[i-5:i+6]
            if low.iloc[i] == window.min():
                swing_lows.append(low.iloc[i])

        # Find swing highs (resistance levels) - local maxima
        swing_highs = []
        for i in range(5, len(recent_df) - 5):
            window = high.iloc[i-5:i+6]
            if high.iloc[i] == window.max():
                swing_highs.append(high.iloc[i])

        # Find nearest support and resistance
        support_level = max(swing_lows) if swing_lows else low.min()
        resistance_level = min([h for h in swing_highs if h > current_price]) if any(h > current_price for h in swing_highs) else high.max()

        # Calculate distance from levels
        distance_from_support = abs(current_price - support_level) / support_level
        distance_from_resistance = abs(current_price - resistance_level) / resistance_level

        # Scoring logic
        if distance_from_support <= level_proximity:
            # Bouncing off support
            result['score'] = 1
            result['signal'] = f'Bouncing off support at ${support_level:.2f}'
        elif distance_from_resistance <= level_proximity:
            # Check for multiple failed attempts (stuck at resistance)
            recent_highs = high.tail(10)
            touches = sum(abs(recent_highs - resistance_level) / resistance_level <= level_proximity)
            if touches >= 2:
                result['score'] = -1
                result['signal'] = f'Stuck at resistance ${resistance_level:.2f} ({touches} touches)'
            else:
                result['signal'] = f'Testing resistance at ${resistance_level:.2f}'
        else:
            result['signal'] = f'Between levels (S: ${support_level:.2f}, R: ${resistance_level:.2f})'

        result['support_level'] = round(support_level, 2)
        result['resistance_level'] = round(resistance_level, 2)

    except Exception as e:
        result['signal'] = f'Error: {str(e)[:50]}'

    return result


def calculate_all_technical_indicators(df: pd.DataFrame, beta: float = 1.0, ticker: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate all technical indicators (Phase 5b - with advanced momentum).

    Args:
        df: DataFrame with price data
        beta: Stock beta
        ticker: Stock ticker (for multi-timeframe)

    Returns:
        Dictionary with all technical scores and details
    """
    # Phase 5a indicators
    ma_result = calculate_ma_position(df, beta)
    momentum_result = calculate_momentum(df)
    rsi_result = calculate_rsi(df, beta)
    macd_result = calculate_macd(df)
    breakout_52w_result = calculate_52week_breakout(df)  # Phase 5a

    # Phase 5b: Advanced Momentum indicators
    bollinger_result = calculate_bollinger_bands(df)
    consolidation_result = calculate_consolidation_pattern(df)
    multitimeframe_result = calculate_multi_timeframe_alignment(df, ticker)
    short_term_sr_result = calculate_short_term_sr(df)

    # Calculate total raw score (Phase 5b: max now 16 points)
    raw_score = (
        ma_result['score'] +
        momentum_result['score'] +
        rsi_result['score'] +
        macd_result['score'] +
        breakout_52w_result['score'] +  # Phase 5a
        bollinger_result['score'] +  # Phase 5b
        consolidation_result['score'] +  # Phase 5b
        multitimeframe_result['score'] +  # Phase 5b
        short_term_sr_result['score']  # Phase 5b
    )

    # Normalize to percentage (-100 to +100)
    max_score = config.get('score_ranges.trend_max', 16.0)  # Phase 5b: updated from 10.0
    normalized_score = (raw_score / max_score) * 100

    return {
        'raw_score': raw_score,
        'normalized_score': normalized_score,
        'ma_position': ma_result,
        'momentum': momentum_result,
        'rsi': rsi_result,
        'macd': macd_result,
        'breakout_52week': breakout_52w_result,  # Phase 5a
        'bollinger_bands': bollinger_result,  # Phase 5b
        'consolidation': consolidation_result,  # Phase 5b
        'multi_timeframe': multitimeframe_result,  # Phase 5b
        'short_term_sr': short_term_sr_result  # Phase 5b
    }
