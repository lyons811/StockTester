"""
Statistical validation utilities for Phase 4 backtesting.

Provides significance testing, confidence intervals, and Monte Carlo
simulations to validate trading strategy performance.
"""

from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from scipy import stats


def calculate_confidence_interval(
    returns: List[float],
    confidence: float = 0.95,
    n_bootstrap: int = 10000
) -> Tuple[float, float, float]:
    """
    Calculate bootstrap confidence interval for mean return.

    Args:
        returns: List of trade returns (in percentage)
        confidence: Confidence level (default: 0.95 for 95% CI)
        n_bootstrap: Number of bootstrap samples

    Returns:
        Tuple of (mean, lower_bound, upper_bound)
    """
    if not returns:
        return (0.0, 0.0, 0.0)

    returns_array = np.array(returns)
    mean_return = np.mean(returns_array)

    # Bootstrap resampling
    bootstrap_means = []
    for _ in range(n_bootstrap):
        sample = np.random.choice(returns_array, size=len(returns_array), replace=True)
        bootstrap_means.append(np.mean(sample))

    # Calculate percentiles for confidence interval
    alpha = 1 - confidence
    lower_percentile = (alpha / 2) * 100
    upper_percentile = (1 - alpha / 2) * 100

    lower_bound = np.percentile(bootstrap_means, lower_percentile)
    upper_bound = np.percentile(bootstrap_means, upper_percentile)

    return (mean_return, lower_bound, upper_bound)


def test_win_rate_significance(
    n_winners: int,
    n_total: int,
    baseline_win_rate: float = 0.50
) -> Dict[str, Any]:
    """
    Test if win rate is statistically significantly different from baseline.

    Uses binomial test to determine if observed win rate differs from
    random chance (50%) or another baseline.

    Args:
        n_winners: Number of winning trades
        n_total: Total number of trades
        baseline_win_rate: Baseline to test against (default: 0.50 = random)

    Returns:
        Dictionary with test results including p-value and significance
    """
    if n_total == 0:
        return {
            'win_rate': 0.0,
            'baseline': baseline_win_rate,
            'p_value': 1.0,
            'is_significant': False,
            'conclusion': 'No trades to test'
        }

    observed_win_rate = n_winners / n_total

    # Two-tailed binomial test
    # Tests if observed is significantly different from baseline
    p_value = stats.binomtest(n_winners, n_total, baseline_win_rate, alternative='two-sided').pvalue

    is_significant = p_value < 0.05

    if is_significant:
        if observed_win_rate > baseline_win_rate:
            conclusion = f"Win rate ({observed_win_rate:.1%}) is significantly BETTER than {baseline_win_rate:.1%}"
        else:
            conclusion = f"Win rate ({observed_win_rate:.1%}) is significantly WORSE than {baseline_win_rate:.1%}"
    else:
        conclusion = f"Win rate ({observed_win_rate:.1%}) is NOT significantly different from {baseline_win_rate:.1%}"

    return {
        'win_rate': observed_win_rate,
        'baseline': baseline_win_rate,
        'p_value': p_value,
        'is_significant': is_significant,
        'conclusion': conclusion,
        'n_winners': n_winners,
        'n_total': n_total
    }


def test_mean_return_significance(
    returns: List[float],
    baseline_return: float = 0.0
) -> Dict[str, Any]:
    """
    Test if mean return is statistically significantly different from baseline.

    Uses one-sample t-test to determine if average return differs from
    zero (or another baseline).

    Args:
        returns: List of trade returns (in percentage)
        baseline_return: Baseline to test against (default: 0.0 = break-even)

    Returns:
        Dictionary with test results including p-value and significance
    """
    if not returns or len(returns) < 2:
        return {
            'mean_return': 0.0,
            'baseline': baseline_return,
            'p_value': 1.0,
            't_statistic': 0.0,
            'is_significant': False,
            'conclusion': 'Insufficient data for t-test'
        }

    returns_array = np.array(returns)
    mean_return = np.mean(returns_array)

    # One-sample t-test (two-tailed)
    t_statistic, p_value = stats.ttest_1samp(returns_array, baseline_return)

    is_significant = p_value < 0.05

    if is_significant:
        if mean_return > baseline_return:
            conclusion = f"Mean return ({mean_return:+.2f}%) is significantly BETTER than {baseline_return:+.2f}%"
        else:
            conclusion = f"Mean return ({mean_return:+.2f}%) is significantly WORSE than {baseline_return:+.2f}%"
    else:
        conclusion = f"Mean return ({mean_return:+.2f}%) is NOT significantly different from {baseline_return:+.2f}%"

    return {
        'mean_return': mean_return,
        'baseline': baseline_return,
        'p_value': p_value,
        't_statistic': t_statistic,
        'is_significant': is_significant,
        'conclusion': conclusion,
        'n_trades': len(returns)
    }


def monte_carlo_simulation(
    returns: List[float],
    n_simulations: int = 1000,
    n_trades_per_sim: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run Monte Carlo simulation to test strategy robustness.

    Randomly samples from observed returns to generate alternative
    trading sequences and assess variability.

    Args:
        returns: List of observed trade returns (in percentage)
        n_simulations: Number of simulation runs
        n_trades_per_sim: Trades per simulation (default: same as observed)

    Returns:
        Dictionary with simulation statistics
    """
    if not returns:
        return {
            'mean_simulated_return': 0.0,
            'median_simulated_return': 0.0,
            'std_simulated_return': 0.0,
            'pct_positive_outcomes': 0.0,
            'worst_case': 0.0,
            'best_case': 0.0
        }

    returns_array = np.array(returns)
    if n_trades_per_sim is None:
        n_trades_per_sim = len(returns)

    # Run simulations
    simulated_totals = []
    for _ in range(n_simulations):
        # Sample with replacement
        sim_returns = np.random.choice(returns_array, size=n_trades_per_sim, replace=True)
        total_return = np.sum(sim_returns)
        simulated_totals.append(total_return)

    simulated_totals = np.array(simulated_totals)

    # Calculate statistics
    mean_total = np.mean(simulated_totals)
    median_total = np.median(simulated_totals)
    std_total = np.std(simulated_totals)
    pct_positive = np.sum(simulated_totals > 0) / n_simulations * 100
    worst_case = np.min(simulated_totals)
    best_case = np.max(simulated_totals)

    # Percentiles for risk assessment
    percentile_5 = np.percentile(simulated_totals, 5)
    percentile_95 = np.percentile(simulated_totals, 95)

    return {
        'mean_simulated_return': mean_total,
        'median_simulated_return': median_total,
        'std_simulated_return': std_total,
        'pct_positive_outcomes': pct_positive,
        'worst_case': worst_case,
        'best_case': best_case,
        'percentile_5': percentile_5,
        'percentile_95': percentile_95,
        'n_simulations': n_simulations
    }


def compare_strategies(
    strategy_a_returns: List[float],
    strategy_b_returns: List[float],
    strategy_a_name: str = "Strategy A",
    strategy_b_name: str = "Strategy B"
) -> Dict[str, Any]:
    """
    Compare two trading strategies statistically.

    Uses independent samples t-test to determine if two strategies
    have significantly different mean returns.

    Args:
        strategy_a_returns: Returns from first strategy
        strategy_b_returns: Returns from second strategy
        strategy_a_name: Name of first strategy (for reporting)
        strategy_b_name: Name of second strategy (for reporting)

    Returns:
        Dictionary with comparison results
    """
    if not strategy_a_returns or not strategy_b_returns:
        return {
            'mean_a': 0.0,
            'mean_b': 0.0,
            'p_value': 1.0,
            'is_significant': False,
            'conclusion': 'Insufficient data for comparison'
        }

    a_array = np.array(strategy_a_returns)
    b_array = np.array(strategy_b_returns)

    mean_a = np.mean(a_array)
    mean_b = np.mean(b_array)

    # Independent samples t-test (two-tailed)
    t_statistic, p_value = stats.ttest_ind(a_array, b_array)

    is_significant = p_value < 0.05

    if is_significant:
        if mean_a > mean_b:
            conclusion = f"{strategy_a_name} ({mean_a:+.2f}%) significantly OUTPERFORMS {strategy_b_name} ({mean_b:+.2f}%)"
        else:
            conclusion = f"{strategy_b_name} ({mean_b:+.2f}%) significantly OUTPERFORMS {strategy_a_name} ({mean_a:+.2f}%)"
    else:
        conclusion = f"No significant difference between {strategy_a_name} ({mean_a:+.2f}%) and {strategy_b_name} ({mean_b:+.2f}%)"

    return {
        'strategy_a_name': strategy_a_name,
        'strategy_b_name': strategy_b_name,
        'mean_a': mean_a,
        'mean_b': mean_b,
        'std_a': np.std(a_array, ddof=1),
        'std_b': np.std(b_array, ddof=1),
        'n_a': len(a_array),
        'n_b': len(b_array),
        't_statistic': t_statistic,
        'p_value': p_value,
        'is_significant': is_significant,
        'conclusion': conclusion
    }


def compare_regime_performance(
    bull_returns: List[float],
    bear_returns: List[float]
) -> Dict[str, Any]:
    """
    Compare performance in bull vs bear market regimes.

    Args:
        bull_returns: Returns during bull market periods
        bear_returns: Returns during bear market periods

    Returns:
        Dictionary with regime comparison statistics
    """
    return compare_strategies(
        bull_returns,
        bear_returns,
        strategy_a_name="Bull Market",
        strategy_b_name="Bear Market"
    )


def paired_comparison(
    before_returns: List[float],
    after_returns: List[float],
    before_name: str = "Before",
    after_name: str = "After"
) -> Dict[str, Any]:
    """
    Compare paired observations (e.g., same periods with different strategies).

    Uses paired t-test for matched samples (e.g., Phase 3 vs Phase 4 on same dates).

    Args:
        before_returns: Returns from first condition
        after_returns: Returns from second condition
        before_name: Name of first condition
        after_name: Name of second condition

    Returns:
        Dictionary with paired comparison results
    """
    if not before_returns or not after_returns or len(before_returns) != len(after_returns):
        return {
            'mean_before': 0.0,
            'mean_after': 0.0,
            'mean_difference': 0.0,
            'p_value': 1.0,
            'is_significant': False,
            'conclusion': 'Invalid data for paired comparison (must be same length)'
        }

    before_array = np.array(before_returns)
    after_array = np.array(after_returns)

    mean_before = np.mean(before_array)
    mean_after = np.mean(after_array)
    mean_diff = mean_after - mean_before

    # Paired t-test
    t_statistic, p_value = stats.ttest_rel(after_array, before_array)

    is_significant = p_value < 0.05

    if is_significant:
        if mean_diff > 0:
            conclusion = f"{after_name} ({mean_after:+.2f}%) significantly BETTER than {before_name} ({mean_before:+.2f}%)"
        else:
            conclusion = f"{after_name} ({mean_after:+.2f}%) significantly WORSE than {before_name} ({mean_before:+.2f}%)"
    else:
        conclusion = f"No significant difference between {after_name} and {before_name}"

    return {
        'before_name': before_name,
        'after_name': after_name,
        'mean_before': mean_before,
        'mean_after': mean_after,
        'mean_difference': mean_diff,
        't_statistic': t_statistic,
        'p_value': p_value,
        'is_significant': is_significant,
        'conclusion': conclusion,
        'n_pairs': len(before_returns)
    }
