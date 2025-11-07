"""
Main scoring calculator.
Integrates all indicators and generates final score and signal.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

from utils.config import config
from data.fetcher import fetcher
from indicators.technical import calculate_all_technical_indicators
from indicators.volume import calculate_all_volume_indicators
from indicators.fundamental import calculate_all_fundamental_indicators
from indicators.market_context import calculate_all_market_context_indicators
from scoring.vetoes import apply_all_veto_rules


class StockScore:
    """Complete stock scoring result."""

    def __init__(self):
        self.ticker: str = ""
        self.is_vetoed: bool = False
        self.veto_reasons: list = []

        # Category results
        self.technical: Dict[str, Any] = {}
        self.volume: Dict[str, Any] = {}
        self.fundamental: Dict[str, Any] = {}
        self.market: Dict[str, Any] = {}

        # Scores
        self.raw_score: float = 0.0
        self.normalized_score: float = 0.0
        self.confidence: float = 1.0
        self.final_score: float = 0.0

        # Signal
        self.signal: str = ""
        self.probability_higher: str = ""
        self.probability_lower: str = ""
        self.probability_sideways: str = ""
        self.position_size_pct: float = 0.0

        # Additional data
        self.company_name: str = ""
        self.sector: str = ""
        self.market_cap: float = 0.0
        self.beta: float = 1.0
        self.current_price: float = 0.0

        # For detailed output
        self.info: Dict[str, Any] = {}
        self.price_df: Optional[pd.DataFrame] = None


def calculate_confidence_adjustment(
    technical_normalized: float,
    volume_normalized: float,
    fundamental_normalized: float,
    market_normalized: float,
    vix_value: float
) -> float:
    """
    Calculate confidence adjustment multiplier.

    Args:
        technical_normalized: Technical score (-100 to +100)
        volume_normalized: Volume score (-100 to +100)
        fundamental_normalized: Fundamental score (-100 to +100)
        market_normalized: Market score (-100 to +100)
        vix_value: Current VIX value

    Returns:
        Confidence multiplier
    """
    confidence_params = config.get_confidence_params()
    multiplier = 1.0

    # Check for strong agreement
    categories_positive = sum([
        technical_normalized > 0,
        volume_normalized > 0,
        fundamental_normalized > 0,
        market_normalized > 0
    ])

    categories_negative = sum([
        technical_normalized < 0,
        volume_normalized < 0,
        fundamental_normalized < 0,
        market_normalized < 0
    ])

    if categories_positive >= confidence_params['strong_agreement_threshold']:
        multiplier *= confidence_params['strong_agreement_multiplier']
    elif categories_negative >= confidence_params['strong_agreement_threshold']:
        multiplier *= confidence_params['strong_agreement_multiplier']
    elif categories_positive == 2 and categories_negative == 2:
        multiplier *= confidence_params['major_conflict_multiplier']

    # Less confidence in extreme volatility
    if vix_value > confidence_params['high_vix_threshold']:
        multiplier *= confidence_params['high_vix_multiplier']

    # Less confidence when trend bullish but fundamentals bearish
    if (technical_normalized > confidence_params['trend_fundamental_conflict_threshold_trend'] and
        fundamental_normalized < confidence_params['trend_fundamental_conflict_threshold_fundamental']):
        multiplier *= confidence_params['trend_fundamental_conflict_multiplier']

    return multiplier


def generate_signal(final_score: float) -> Dict[str, Any]:
    """
    Generate trading signal from final score.

    Args:
        final_score: Final score (-10 to +10)

    Returns:
        Dictionary with signal and probabilities
    """
    signal_thresholds = config.get_signal_thresholds()

    if final_score >= signal_thresholds['strong_buy']:
        return {
            'signal': 'STRONG BUY',
            'probability_higher': '70-80%',
            'probability_lower': '10-15%',
            'probability_sideways': '10-15%'
        }
    elif final_score >= signal_thresholds['buy']:
        return {
            'signal': 'BUY',
            'probability_higher': '60-70%',
            'probability_lower': '15-25%',
            'probability_sideways': '15-20%'
        }
    elif final_score > signal_thresholds['neutral_low']:
        return {
            'signal': 'NEUTRAL / HOLD',
            'probability_higher': '35-40%',
            'probability_lower': '35-40%',
            'probability_sideways': '20-30%'
        }
    elif final_score > signal_thresholds['sell']:
        return {
            'signal': 'SELL / AVOID',
            'probability_higher': '15-25%',
            'probability_lower': '60-70%',
            'probability_sideways': '15-20%'
        }
    else:
        return {
            'signal': 'STRONG SELL',
            'probability_higher': '10-15%',
            'probability_lower': '70-80%',
            'probability_sideways': '10-15%'
        }


def calculate_position_size(final_score: float, beta: float, market_regime: str) -> float:
    """
    Calculate recommended position size.

    Args:
        final_score: Final score (-10 to +10)
        beta: Stock beta
        market_regime: Market regime (Bull/Bear)

    Returns:
        Position size as percentage of portfolio
    """
    position_params = config.get_position_sizing_params()

    # Base size by score strength
    abs_score = abs(final_score)

    if abs_score >= 7:
        base_size = position_params['score_7_plus']
    elif abs_score >= 5:
        base_size = position_params['score_5_plus']
    elif abs_score >= 3:
        base_size = position_params['score_3_plus']
    else:
        base_size = position_params['score_below_3']

    # For sell signals, position size is 0
    if final_score < 0:
        return 0.0

    # Adjust for volatility (beta)
    if beta > position_params['high_beta_threshold']:
        volatility_adj = position_params['high_beta_multiplier']
    elif beta < position_params['low_beta_threshold']:
        volatility_adj = position_params['low_beta_multiplier']
    else:
        volatility_adj = 1.0

    # Adjust for market regime
    if market_regime == "Bear" and final_score > 0:
        regime_adj = position_params['bear_market_multiplier']
    elif market_regime == "Bull" and final_score > 0:
        regime_adj = position_params['bull_market_multiplier']
    else:
        regime_adj = 1.0

    # Calculate final position size
    position_size = base_size * volatility_adj * regime_adj

    # Apply maximum constraint
    return min(position_size, position_params['max_position'])


def calculate_stock_score(ticker: str) -> StockScore:
    """
    Calculate complete score for a stock.

    Args:
        ticker: Stock ticker symbol

    Returns:
        StockScore object with complete analysis
    """
    result = StockScore()
    result.ticker = ticker.upper()

    try:
        # Fetch data
        print(f"Fetching data for {result.ticker}...")
        df = fetcher.get_stock_data(result.ticker, period='2y')
        info = fetcher.get_stock_info(result.ticker)

        if df is None or df.empty or not info:
            result.is_vetoed = True
            result.veto_reasons.append("Unable to fetch stock data")
            return result

        result.price_df = df
        result.info = info

        # Extract basic info
        result.company_name = info.get('longName', result.ticker)
        result.sector = info.get('sector', 'Unknown')
        result.market_cap = info.get('marketCap', 0)
        result.beta = fetcher.get_beta(result.ticker)
        result.current_price = df['Close'].iloc[-1]

        # Check veto rules
        print("Checking veto rules...")
        veto_result = apply_all_veto_rules(result.ticker, info, df)
        if veto_result.is_vetoed:
            result.is_vetoed = True
            result.veto_reasons = veto_result.veto_reasons
            return result

        # Calculate indicators
        print("Calculating technical indicators...")
        result.technical = calculate_all_technical_indicators(df, result.beta)

        print("Calculating volume indicators...")
        result.volume = calculate_all_volume_indicators(df)

        print("Calculating fundamental indicators...")
        result.fundamental = calculate_all_fundamental_indicators(info)

        print("Calculating market context...")
        result.market = calculate_all_market_context_indicators(result.ticker, df)

        # Get normalized scores
        technical_norm = result.technical['normalized_score']
        volume_norm = result.volume['normalized_score']
        fundamental_norm = result.fundamental['normalized_score']
        market_norm = result.market['normalized_score']

        # Apply category weights
        weights = config.get_weights()
        weighted_score = (
            technical_norm * weights['trend_momentum'] +
            volume_norm * weights['volume'] +
            fundamental_norm * weights['fundamental'] +
            market_norm * weights['market_context']
        )

        # Calculate confidence adjustment
        vix_value = result.market['vix'].get('vix_value', 15.0)
        confidence = calculate_confidence_adjustment(
            technical_norm,
            volume_norm,
            fundamental_norm,
            market_norm,
            vix_value
        )
        result.confidence = confidence

        # Apply confidence and convert to -10 to +10 scale
        adjusted_score = (weighted_score / 10) * confidence
        result.final_score = max(-10, min(10, adjusted_score))

        # Generate signal
        print("Generating signal...")
        signal_data = generate_signal(result.final_score)
        result.signal = signal_data['signal']
        result.probability_higher = signal_data['probability_higher']
        result.probability_lower = signal_data['probability_lower']
        result.probability_sideways = signal_data['probability_sideways']

        # Calculate position size
        market_regime = result.market['market_regime'].get('regime', 'Unknown')
        result.position_size_pct = calculate_position_size(
            result.final_score,
            result.beta,
            market_regime
        )

        print("Scoring complete!")
        return result

    except Exception as e:
        print(f"Error calculating score: {e}")
        result.is_vetoed = True
        result.veto_reasons.append(f"Error: {str(e)}")
        return result
