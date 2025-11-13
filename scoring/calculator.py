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
from indicators.advanced import calculate_all_advanced_indicators
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
        self.advanced: Dict[str, Any] = {}  # Phase 3

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
    vix_value: float,
    ticker: Optional[str] = None,
    score_direction: float = 0,
    advanced_normalized: float = 0
) -> float:
    """
    Calculate confidence adjustment multiplier (Phase 3: Enhanced with advanced indicators).

    Args:
        technical_normalized: Technical score (-100 to +100)
        volume_normalized: Volume score (-100 to +100)
        fundamental_normalized: Fundamental score (-100 to +100)
        market_normalized: Market score (-100 to +100)
        vix_value: Current VIX value
        ticker: Stock ticker (for Phase 2 enhancements)
        score_direction: Overall score direction (for Phase 2 enhancements)
        advanced_normalized: Advanced indicators score (-100 to +100, Phase 3)

    Returns:
        Confidence multiplier
    """
    confidence_params = config.get_confidence_params()
    multiplier = 1.0

    # PHASE 1 FACTORS

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

    # PHASE 2 ENHANCEMENTS

    if ticker:
        from data.fetcher import fetcher

        # Factor 1: Quarterly earnings trend confirms score direction
        try:
            earnings_hist = fetcher.get_earnings_history(ticker)
            if earnings_hist is not None and not earnings_hist.empty and len(earnings_hist) >= 2:
                recent_beats = sum(1 for idx in range(min(2, len(earnings_hist)))
                                 if earnings_hist.iloc[idx].get('surprisePercent', 0) > 0)

                if score_direction > 0 and recent_beats >= 2:
                    multiplier *= 1.1  # Boost confidence for bullish score with earnings beats
                elif score_direction < 0 and recent_beats == 0:
                    multiplier *= 1.1  # Boost confidence for bearish score with earnings misses
        except:
            pass

        # Factor 2: Analyst downgrades warn against bullish signals
        try:
            analyst_data = fetcher.get_analyst_data(ticker)
            if analyst_data and analyst_data.get('upgrades_downgrades'):
                import pandas as pd
                from datetime import datetime

                upgrades_df = pd.DataFrame(analyst_data['upgrades_downgrades'])
                if not upgrades_df.empty and 'GradeDate' in upgrades_df.columns:
                    thirty_days_ago = datetime.now() - pd.Timedelta(days=30)
                    recent = upgrades_df[pd.to_datetime(upgrades_df['GradeDate']) >= thirty_days_ago]

                    if not recent.empty and 'Action' in recent.columns:
                        downgrades = sum(recent['Action'].str.lower().str.contains('down', na=False))
                        upgrades = sum(recent['Action'].str.lower().str.contains('up', na=False))

                        # Reduce confidence if bullish score but analysts downgrading
                        if score_direction > 0 and downgrades > upgrades:
                            multiplier *= 0.9
                        # Boost confidence if bearish score and analysts downgrading
                        elif score_direction < 0 and downgrades > upgrades:
                            multiplier *= 1.1
        except:
            pass

    # Factor 3: Multiple timeframes alignment (momentum at different periods)
    # Check if technical indicators show alignment across timeframes
    if abs(technical_normalized) > 50:  # Strong technical signal
        multiplier *= 1.05  # Slight boost for strong trend confirmation

    # Factor 4: Fundamental quality deterioration warning
    # If fundamentals very weak, reduce confidence even if other signals strong
    if fundamental_normalized < -50 and score_direction > 0:
        multiplier *= 0.85  # Reduce confidence for bullish signal with weak fundamentals

    # Factor 5: Very strong agreement across all 4 categories
    if (categories_positive == 4 and all([abs(s) > 30 for s in
        [technical_normalized, volume_normalized, fundamental_normalized, market_normalized]])):
        multiplier *= 1.15  # Extra boost for unanimous strong signals
    elif (categories_negative == 4 and all([abs(s) > 30 for s in
        [technical_normalized, volume_normalized, fundamental_normalized, market_normalized]])):
        multiplier *= 1.15  # Extra boost for unanimous strong signals

    # PHASE 3 FACTORS

    # Factor 6: Advanced indicators confirmation
    # Strong agreement between advanced indicators and overall score direction
    if abs(advanced_normalized) > 30:  # Strong advanced signal
        if (advanced_normalized > 0 and score_direction > 0) or \
           (advanced_normalized < 0 and score_direction < 0):
            multiplier *= 1.10  # Boost for advanced confirmation
        elif (advanced_normalized > 0 and score_direction < 0) or \
             (advanced_normalized < 0 and score_direction > 0):
            multiplier *= 0.90  # Reduce for advanced contradiction

    # Factor 7: Very strong advanced signal (all 4 indicators aligned)
    # This indicates unanimous agreement on earnings, analyst, short interest, and options
    if abs(advanced_normalized) > 60:  # Very strong advanced signal
        multiplier *= 1.08  # Additional boost for exceptional advanced confirmation

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


def get_sector_adjusted_weights(sector: str, quiet: bool = False) -> Dict[str, float]:
    """
    Get category weights adjusted for regime and sector-specific factors (Phase 4).

    Phase 4 Enhancement:
    - First checks if regime-adaptive weights are enabled
    - Loads bull_market or bear_market weights based on current S&P 500 regime
    - Then applies sector-specific multipliers on top of regime weights

    Args:
        sector: Stock sector name

    Returns:
        Dictionary of adjusted weights
    """
    # Phase 4: Check for regime-adaptive weights
    use_regime_weights = config.get('backtesting', {}).get('use_regime_weights', False)

    if use_regime_weights:
        # Detect current market regime
        from utils.regime_classifier import get_current_regime

        try:
            current_regime = get_current_regime(quiet=True)  # Suppress verbose regime output
            if not quiet:
                print(f"[Phase 4] Current market regime: {current_regime}")

            # Load regime-specific weights from config
            regime_weights = config.get('optimized_weights', {})

            if current_regime == 'Bull' and 'bull_market' in regime_weights:
                weights = regime_weights['bull_market'].copy()
                if not quiet:
                    print(f"[Phase 4] Using bull market weights")
            elif current_regime == 'Bear' and 'bear_market' in regime_weights:
                weights = regime_weights['bear_market'].copy()
                if not quiet:
                    print(f"[Phase 4] Using bear market weights")
            else:
                # Fallback to standard weights
                if not quiet:
                    print(f"[Phase 4] Regime weights not configured, using standard weights")
                weights = config.get_weights().copy()
        except Exception as e:
            if not quiet:
                print(f"[Phase 4] Error detecting regime: {e}, using standard weights")
            weights = config.get_weights().copy()
    else:
        # Phase 3: Use standard weights
        weights = config.get_weights().copy()

    # Apply sector adjustments (works with both regime and standard weights)
    sector_adjustments = config.get('sector_adjustments', {})

    if sector in sector_adjustments:
        adjustments = sector_adjustments[sector]
        weight_multipliers = adjustments.get('weight_multipliers', {})

        # Apply multipliers
        for category, multiplier in weight_multipliers.items():
            if category in weights:
                weights[category] *= multiplier

        # Normalize to sum to 1.0
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

    return weights


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


def calculate_stock_score(ticker: str, sp500_returns_cache: Optional[Dict[str, float]] = None, quiet: bool = False) -> StockScore:
    """
    Calculate complete score for a stock (Phase 5a - OPTIMIZED).

    PERFORMANCE OPTIMIZATION: Accepts pre-fetched S&P 500 returns cache to dramatically
    improve performance during batch operations (optimization, backtesting).

    Args:
        ticker: Stock ticker symbol
        sp500_returns_cache: Optional pre-fetched S&P 500 6-month returns
                            If None, will fetch bulk data (adds ~30s first time)
        quiet: If True, suppress print statements (default: False)

    Returns:
        StockScore object with complete analysis
    """
    result = StockScore()
    result.ticker = ticker.upper()

    # Fetch S&P 500 returns once if not provided (optimization for single stock queries)
    if sp500_returns_cache is None:
        sp500_returns_cache = fetcher.get_sp500_returns_bulk(period='6mo')

    try:
        # Fetch data
        if not quiet:
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
        if not quiet:
            print("Checking veto rules...")
        veto_result = apply_all_veto_rules(result.ticker, info, df)
        if veto_result.is_vetoed:
            result.is_vetoed = True
            result.veto_reasons = veto_result.veto_reasons
            return result

        # Calculate indicators
        if not quiet:
            print("Calculating technical indicators...")
        result.technical = calculate_all_technical_indicators(df, result.beta, result.ticker)  # Phase 5b: added ticker

        if not quiet:
            print("Calculating volume indicators...")
        result.volume = calculate_all_volume_indicators(df)

        if not quiet:
            print("Calculating fundamental indicators...")
        result.fundamental = calculate_all_fundamental_indicators(info, result.sector, result.ticker)  # Phase 5a: added ticker

        if not quiet:
            print("Calculating market context...")
        result.market = calculate_all_market_context_indicators(result.ticker, df)

        # Phase 3 + Phase 5a: Calculate advanced indicators with S&P 500 cache (OPTIMIZED)
        if not quiet:
            print("Calculating advanced indicators...")
        result.advanced = calculate_all_advanced_indicators(result.ticker, config._config or {}, sp500_returns_cache)

        # Get normalized scores
        technical_norm = result.technical['normalized_score']
        volume_norm = result.volume['normalized_score']
        fundamental_norm = result.fundamental['normalized_score']
        market_norm = result.market['normalized_score']
        advanced_norm = result.advanced['normalized_score']

        # Apply category weights (with sector-specific adjustments)
        weights = get_sector_adjusted_weights(result.sector, quiet=quiet)
        weighted_score = (
            technical_norm * weights['trend_momentum'] +
            volume_norm * weights['volume'] +
            fundamental_norm * weights['fundamental'] +
            market_norm * weights['market_context'] +
            advanced_norm * weights.get('advanced', 0.0)  # Phase 3
        )

        # Calculate confidence adjustment (Phase 3: with advanced indicators)
        vix_value = result.market['vix'].get('vix_value', 15.0)
        preliminary_score = weighted_score / 10  # Get preliminary score for direction
        confidence = calculate_confidence_adjustment(
            technical_norm,
            volume_norm,
            fundamental_norm,
            market_norm,
            vix_value,
            result.ticker,
            preliminary_score,
            advanced_norm  # Phase 3
        )
        result.confidence = confidence

        # Apply confidence and convert to -10 to +10 scale
        adjusted_score = preliminary_score * confidence
        result.final_score = max(-10, min(10, adjusted_score))

        # Generate signal
        if not quiet:
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

        if not quiet:
            print("Scoring complete!")
        return result

    except Exception as e:
        if not quiet:
            print(f"Error calculating score: {e}")
        result.is_vetoed = True
        result.veto_reasons.append(f"Error: {str(e)}")
        return result
