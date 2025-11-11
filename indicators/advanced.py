"""
Phase 3 Advanced Indicators Module
Implements earnings quality, analyst revisions, short interest, and options flow analysis.

Scoring Ranges:
- Earnings Quality: -3 to +3
- Analyst Revisions: -3 to +3
- Short Interest: -2 to +2
- Options Flow: -2 to +2
- Total Advanced Range: -10 to +10
"""

from typing import Dict, Any
import pandas as pd
from datetime import datetime, timedelta
from data.fetcher import fetcher


def calculate_earnings_quality_score(ticker: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate earnings quality score based on beat/miss history and YoY growth.

    Methodology:
    - Consecutive beats: +1 per quarter (max +3)
    - Consecutive misses: -1 per quarter (max -3)
    - Strong YoY growth (>15%): +1 bonus
    - Weak/negative YoY growth: -1 penalty

    Args:
        ticker: Stock ticker symbol
        config: Configuration dictionary with thresholds

    Returns:
        Dictionary with score, details, and explanation
    """
    result = {
        'score': 0,
        'beats': 0,
        'misses': 0,
        'yoy_growth': None,
        'explanation': ''
    }

    try:
        # Get earnings history (last 4 quarters)
        earnings_hist = fetcher.get_earnings_history(ticker)

        if earnings_hist is None or earnings_hist.empty:
            result['explanation'] = 'No earnings history available'
            return result

        # Count consecutive beats/misses from most recent quarter
        consecutive_beats = 0
        consecutive_misses = 0
        total_beats = 0
        total_misses = 0

        # Iterate through earnings history (most recent first)
        for _, row in earnings_hist.iterrows():
            if 'surprisePercent' in row and pd.notna(row['surprisePercent']):
                surprise = row['surprisePercent']

                # Beat if surprise > 0
                if surprise > 0:
                    total_beats += 1
                    if consecutive_misses == 0:  # Still counting consecutive beats
                        consecutive_beats += 1
                    else:
                        break  # Streak broken
                # Miss if surprise < 0
                elif surprise < 0:
                    total_misses += 1
                    if consecutive_beats == 0:  # Still counting consecutive misses
                        consecutive_misses += 1
                    else:
                        break  # Streak broken

        result['beats'] = total_beats
        result['misses'] = total_misses

        # Calculate YoY earnings growth if available
        if len(earnings_hist) >= 4 and 'epsActual' in earnings_hist.columns:
            try:
                # Compare most recent quarter to same quarter last year (4 quarters ago)
                recent_eps = earnings_hist.iloc[0]['epsActual']
                yoy_eps = earnings_hist.iloc[3]['epsActual']

                if pd.notna(recent_eps) and pd.notna(yoy_eps) and yoy_eps != 0:
                    yoy_growth = ((recent_eps - yoy_eps) / abs(yoy_eps)) * 100
                    result['yoy_growth'] = round(yoy_growth, 2)
            except:
                pass

        # Calculate score
        score = 0

        # Consecutive beats/misses scoring
        beat_threshold = config.get('advanced_features', {}).get('earnings_quality', {}).get('consecutive_beat_threshold', 3)
        miss_threshold = config.get('advanced_features', {}).get('earnings_quality', {}).get('consecutive_miss_threshold', 3)

        if consecutive_beats >= beat_threshold:
            score += 3
            result['explanation'] = f'{consecutive_beats} consecutive earnings beats'
        elif consecutive_beats == 2:
            score += 2
            result['explanation'] = f'{consecutive_beats} consecutive earnings beats'
        elif consecutive_beats == 1:
            score += 1
            result['explanation'] = f'{consecutive_beats} earnings beat'
        elif consecutive_misses >= miss_threshold:
            score -= 3
            result['explanation'] = f'{consecutive_misses} consecutive earnings misses'
        elif consecutive_misses == 2:
            score -= 2
            result['explanation'] = f'{consecutive_misses} consecutive earnings misses'
        elif consecutive_misses == 1:
            score -= 1
            result['explanation'] = f'{consecutive_misses} earnings miss'
        else:
            result['explanation'] = 'Mixed earnings results'

        # YoY growth bonus/penalty
        if result['yoy_growth'] is not None:
            if result['yoy_growth'] > 15:
                score += 1
                result['explanation'] += f' | Strong YoY growth ({result["yoy_growth"]}%)'
            elif result['yoy_growth'] < -10:
                score -= 1
                result['explanation'] += f' | Weak YoY growth ({result["yoy_growth"]}%)'

        # Cap score at -3 to +3
        result['score'] = max(-3, min(3, score))

    except Exception as e:
        result['explanation'] = f'Error calculating earnings quality: {str(e)}'

    return result


def calculate_analyst_revision_score(ticker: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate analyst revision score based on recent upgrades/downgrades and consensus.

    Methodology:
    - Recent upgrades (last 30 days): +1 per upgrade (max +3)
    - Recent downgrades (last 30 days): -1 per downgrade (max -3)
    - Consensus rating: Bonus/penalty based on overall rating

    Args:
        ticker: Stock ticker symbol
        config: Configuration dictionary with thresholds

    Returns:
        Dictionary with score, details, and explanation
    """
    result = {
        'score': 0,
        'upgrades': 0,
        'downgrades': 0,
        'consensus': None,
        'explanation': ''
    }

    try:
        # Get analyst data
        analyst_data = fetcher.get_analyst_data(ticker)

        if analyst_data is None:
            result['explanation'] = 'No analyst data available'
            return result

        # Count recent upgrades/downgrades (last 30 days)
        lookback_days = config.get('advanced_features', {}).get('analyst_revisions', {}).get('lookback_days', 30)
        cutoff_date = pd.Timestamp(datetime.now() - timedelta(days=lookback_days))

        upgrades = 0
        downgrades = 0

        # Parse upgrades/downgrades
        if analyst_data.get('upgrades_downgrades'):
            try:
                # Convert to DataFrame if it's a dict
                upgrades_df = pd.DataFrame(analyst_data['upgrades_downgrades'])

                # Filter by date (last 30 days)
                if not upgrades_df.empty and 'GradeDate' in upgrades_df.columns:
                    # Convert index to datetime if it's stored as index
                    if isinstance(upgrades_df.index, pd.DatetimeIndex):
                        recent = upgrades_df[upgrades_df.index >= cutoff_date]
                    else:
                        upgrades_df['GradeDate'] = pd.to_datetime(upgrades_df['GradeDate'])
                        recent = upgrades_df[upgrades_df['GradeDate'] >= cutoff_date]

                    # Count upgrades vs downgrades
                    if 'Action' in recent.columns:
                        upgrades = len(recent[recent['Action'].str.contains('up', case=False, na=False)])
                        downgrades = len(recent[recent['Action'].str.contains('down', case=False, na=False)])
            except Exception as e:
                pass  # Silently handle parsing errors

        result['upgrades'] = upgrades
        result['downgrades'] = downgrades

        # Get consensus recommendation if available
        if analyst_data.get('recommendations'):
            try:
                rec_df = pd.DataFrame(analyst_data['recommendations'])
                if not rec_df.empty:
                    # Get most recent recommendation
                    latest = rec_df.iloc[0] if hasattr(rec_df, 'iloc') else None
                    if latest is not None and 'To Grade' in latest:
                        result['consensus'] = latest['To Grade']
            except:
                pass

        # Calculate score
        score = 0
        upgrade_threshold = config.get('advanced_features', {}).get('analyst_revisions', {}).get('significant_upgrade_threshold', 3)
        downgrade_threshold = config.get('advanced_features', {}).get('analyst_revisions', {}).get('significant_downgrade_threshold', 3)

        # Net upgrades/downgrades
        net_revisions = upgrades - downgrades

        if net_revisions >= upgrade_threshold:
            score = 3
            result['explanation'] = f'{upgrades} upgrades, {downgrades} downgrades (last {lookback_days}d)'
        elif net_revisions == 2:
            score = 2
            result['explanation'] = f'{upgrades} upgrades, {downgrades} downgrades (last {lookback_days}d)'
        elif net_revisions == 1:
            score = 1
            result['explanation'] = f'{upgrades} upgrades, {downgrades} downgrades (last {lookback_days}d)'
        elif net_revisions <= -downgrade_threshold:
            score = -3
            result['explanation'] = f'{upgrades} upgrades, {downgrades} downgrades (last {lookback_days}d)'
        elif net_revisions == -2:
            score = -2
            result['explanation'] = f'{upgrades} upgrades, {downgrades} downgrades (last {lookback_days}d)'
        elif net_revisions == -1:
            score = -1
            result['explanation'] = f'{upgrades} upgrades, {downgrades} downgrades (last {lookback_days}d)'
        else:
            result['explanation'] = f'No significant analyst revisions (last {lookback_days}d)'

        # Add consensus info if available
        if result['consensus']:
            result['explanation'] += f' | Consensus: {result["consensus"]}'

        result['score'] = score

    except Exception as e:
        result['explanation'] = f'Error calculating analyst revisions: {str(e)}'

    return result


def calculate_short_interest_score(ticker: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate short interest score and detect potential squeeze setups.

    Methodology:
    - High short interest (>20%): +2 (squeeze potential)
    - Moderate short interest (10-20%): +1
    - Low short interest (<5%): 0
    - Very low (<2%): -1 (lacking catalyst)

    Args:
        ticker: Stock ticker symbol
        config: Configuration dictionary with thresholds

    Returns:
        Dictionary with score, details, and explanation
    """
    result = {
        'score': 0,
        'short_percent': None,
        'days_to_cover': None,
        'explanation': ''
    }

    try:
        # Get short interest data
        short_data = fetcher.get_short_interest(ticker)

        if short_data is None:
            result['explanation'] = 'Short interest data unavailable'
            return result

        short_percent = short_data.get('short_percent_float')
        result['short_percent'] = short_percent
        result['days_to_cover'] = short_data.get('days_to_cover')

        if short_percent is None:
            result['explanation'] = 'Short interest data unavailable'
            return result

        # Calculate score based on short interest levels
        high_threshold = config.get('advanced_features', {}).get('short_interest', {}).get('high_threshold', 20.0)

        if short_percent > high_threshold:
            result['score'] = 2
            result['explanation'] = f'High short interest ({short_percent:.1f}%) - squeeze potential'
        elif short_percent > 10:
            result['score'] = 1
            result['explanation'] = f'Moderate short interest ({short_percent:.1f}%)'
        elif short_percent > 5:
            result['score'] = 0
            result['explanation'] = f'Normal short interest ({short_percent:.1f}%)'
        elif short_percent > 2:
            result['score'] = 0
            result['explanation'] = f'Low short interest ({short_percent:.1f}%)'
        else:
            result['score'] = -1
            result['explanation'] = f'Very low short interest ({short_percent:.1f}%) - limited catalyst'

        # Add days to cover if available
        if result['days_to_cover']:
            result['explanation'] += f' | {result["days_to_cover"]:.1f} days to cover'

    except Exception as e:
        result['explanation'] = f'Error calculating short interest: {str(e)}'

    return result


def calculate_options_flow_score(ticker: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate options flow score based on put/call ratios and unusual activity.

    Methodology:
    - Bullish options flow (low P/C, high call volume): +2
    - Moderate bullish flow: +1
    - Neutral: 0
    - Moderate bearish flow: -1
    - Bearish options flow (high P/C, high put volume): -2

    Args:
        ticker: Stock ticker symbol
        config: Configuration dictionary with thresholds

    Returns:
        Dictionary with score, details, and explanation
    """
    result = {
        'score': 0,
        'put_call_ratio': None,
        'unusual_activity': False,
        'explanation': ''
    }

    try:
        # Get options data
        options_data = fetcher.get_options_data(ticker)

        if options_data is None:
            result['explanation'] = 'Options data unavailable'
            return result

        put_call_ratio = options_data.get('put_call_ratio')
        unusual_activity = options_data.get('unusual_activity', False)

        result['put_call_ratio'] = put_call_ratio
        result['unusual_activity'] = unusual_activity

        if put_call_ratio is None:
            result['explanation'] = 'Options data unavailable'
            return result

        # Calculate score based on put/call ratio
        # Low P/C ratio (< 0.7) = bullish (more calls than puts)
        # High P/C ratio (> 1.3) = bearish (more puts than calls)

        score = 0
        if put_call_ratio < 0.7:
            score = 2 if unusual_activity else 1
            result['explanation'] = f'Bullish options flow (P/C: {put_call_ratio:.2f})'
        elif put_call_ratio < 1.0:
            score = 1
            result['explanation'] = f'Moderately bullish options flow (P/C: {put_call_ratio:.2f})'
        elif put_call_ratio <= 1.3:
            score = 0
            result['explanation'] = f'Neutral options flow (P/C: {put_call_ratio:.2f})'
        elif put_call_ratio <= 1.8:
            score = -1
            result['explanation'] = f'Moderately bearish options flow (P/C: {put_call_ratio:.2f})'
        else:
            score = -2 if unusual_activity else -1
            result['explanation'] = f'Bearish options flow (P/C: {put_call_ratio:.2f})'

        if unusual_activity:
            result['explanation'] += ' | Unusual activity detected'

        result['score'] = score

    except Exception as e:
        result['explanation'] = f'Error calculating options flow: {str(e)}'

    return result


def calculate_relative_strength_rank(ticker: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate relative strength rank vs S&P 500 (Phase 5a).

    Compares 6-month return percentile of stock against all S&P 500 constituents.
    Professional signal: stocks with strong relative strength tend to continue outperforming.

    Scoring:
    - +2: Top 20% (top quintile, institutional favorites)
    - +1: Top 50% (above-median performance)
    - 0: Bottom 50% (below-median performance)
    - -1: Bottom 20% (underperforming significantly)

    Args:
        ticker: Stock ticker symbol
        config: Configuration dictionary

    Returns:
        Dictionary with score, percentile rank, and details
    """
    from utils.config import config as cfg

    # Get Phase 5a config
    phase5_params = cfg.get('phase5a', {})
    lookback_days = phase5_params.get('relative_strength', {}).get('lookback_days', 126)
    top_tier_threshold = phase5_params.get('relative_strength', {}).get('top_tier_threshold', 80)
    bottom_tier_threshold = phase5_params.get('relative_strength', {}).get('bottom_tier_threshold', 20)

    result = {
        'score': 0,
        'percentile_rank': None,
        'stock_return': None,
        'sp500_median_return': None,
        'explanation': ''
    }

    try:
        # Fetch target stock's 6-month return
        stock_df = fetcher.get_stock_data(ticker, period='6mo')

        if stock_df is None or stock_df.empty or len(stock_df) < lookback_days:
            result['explanation'] = f'Insufficient data for {ticker}'
            return result

        # Calculate target stock's 6-month return
        stock_price_start = stock_df['Close'].iloc[0]
        stock_price_end = stock_df['Close'].iloc[-1]
        stock_return = ((stock_price_end - stock_price_start) / stock_price_start) * 100
        result['stock_return'] = round(stock_return, 2)

        # Get S&P 500 constituents
        sp500_constituents = fetcher.get_sp500_constituents()

        if sp500_constituents is None or sp500_constituents.empty:
            result['explanation'] = 'Unable to fetch S&P 500 constituents'
            return result

        # Calculate 6-month returns for all S&P 500 stocks
        # Use caching to avoid redundant API calls
        sp500_returns = []

        for _, row in sp500_constituents.iterrows():
            sp_ticker = row['ticker']

            try:
                # Fetch 6-month data for each S&P 500 stock
                sp_df = fetcher.get_stock_data(sp_ticker, period='6mo')

                if sp_df is not None and not sp_df.empty and len(sp_df) >= lookback_days:
                    sp_start = sp_df['Close'].iloc[0]
                    sp_end = sp_df['Close'].iloc[-1]
                    sp_return = ((sp_end - sp_start) / sp_start) * 100
                    sp500_returns.append(sp_return)
            except:
                # Skip stocks with errors
                continue

        if len(sp500_returns) < 100:
            # Not enough data to calculate percentile
            result['explanation'] = 'Insufficient S&P 500 return data'
            return result

        # Calculate percentile rank
        # percentileofscore returns 0-100 where higher = better
        from scipy import stats
        percentile_rank = stats.percentileofscore(sp500_returns, stock_return, kind='rank')
        result['percentile_rank'] = round(percentile_rank, 1)
        result['sp500_median_return'] = round(pd.Series(sp500_returns).median(), 2)

        # Scoring logic
        if percentile_rank >= top_tier_threshold:
            # Top 20%
            score = 2
            explanation = f"Top {100 - percentile_rank:.0f}% ({percentile_rank:.0f}th percentile)"
        elif percentile_rank >= 50:
            # Top 50%
            score = 1
            explanation = f"Above median ({percentile_rank:.0f}th percentile)"
        elif percentile_rank >= bottom_tier_threshold:
            # 20-50%
            score = 0
            explanation = f"Below median ({percentile_rank:.0f}th percentile)"
        else:
            # Bottom 20%
            score = -1
            explanation = f"Bottom {percentile_rank:.0f}% (weak relative strength)"

        result['score'] = score
        result['explanation'] = explanation

    except Exception as e:
        result['explanation'] = f'Error calculating relative strength: {str(e)[:50]}'

    return result


def calculate_all_advanced_indicators(ticker: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate all advanced indicators (Phase 3 + Phase 5a) and return combined score.

    Args:
        ticker: Stock ticker symbol
        config: Configuration dictionary

    Returns:
        Dictionary with individual scores, combined score, and normalized score (-100 to +100)
    """
    # Calculate individual indicator scores
    earnings = calculate_earnings_quality_score(ticker, config)
    analyst = calculate_analyst_revision_score(ticker, config)
    short_interest = calculate_short_interest_score(ticker, config)
    options_flow = calculate_options_flow_score(ticker, config)
    relative_strength = calculate_relative_strength_rank(ticker, config)  # Phase 5a

    # Combine scores
    raw_score = (
        earnings['score'] +
        analyst['score'] +
        short_interest['score'] +
        options_flow['score'] +
        relative_strength['score']  # Phase 5a
    )

    # Normalize to -100 to +100 scale
    # Phase 5a: Updated max from 10.0 to 13.0 (added relative strength -1 to +2)
    # Max possible: +3 +3 +2 +2 +2 = +12 (but we use 13 for safety margin)
    # Min possible: -3 -3 -2 -2 -1 = -11
    from utils.config import config as cfg
    max_score = cfg.get('score_ranges.advanced_max', 13.0)
    normalized_score = (raw_score / max_score) * 100

    return {
        'earnings_quality': earnings,
        'analyst_revisions': analyst,
        'short_interest': short_interest,
        'options_flow': options_flow,
        'relative_strength': relative_strength,  # Phase 5a
        'raw_score': raw_score,
        'normalized_score': normalized_score,
        'max_score': max_score
    }
