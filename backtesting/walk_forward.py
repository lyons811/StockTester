"""
Walk-forward optimization framework for Phase 4.

Implements expanding window walk-forward validation to prevent
overfitting and provide realistic out-of-sample performance estimates.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from .engine import BacktestEngine
from .optimizer import WeightOptimizer
from .metrics import PerformanceMetrics
from utils.config import config


@dataclass
class WalkForwardPeriod:
    """Represents a single walk-forward train/test split."""
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_years: float
    test_years: float


@dataclass
class WalkForwardResult:
    """Results from a single walk-forward period."""
    period: WalkForwardPeriod
    optimized_weights: Dict[str, float]
    train_metrics: Dict[str, Any]
    test_metrics: Dict[str, Any]
    test_trades: List[Any]


class WalkForwardOptimizer:
    """
    Expanding window walk-forward optimizer.

    Splits data into multiple train/test periods using expanding window:
    - Train on all past data, test on next year
    - Re-optimize for each period to adapt to changing market conditions
    - Aggregate out-of-sample test results for unbiased performance estimate

    Example for 2018-2025 (7 years):
    - Train 2018-2019 (2y) → Test 2020 (1y)
    - Train 2018-2020 (3y) → Test 2021 (1y)
    - Train 2018-2021 (4y) → Test 2022 (1y)
    - Train 2018-2022 (5y) → Test 2023 (1y)
    - Train 2018-2023 (6y) → Test 2024 (1y)
    """

    def __init__(
        self,
        backtest_engine: BacktestEngine,
        train_period_years: int = 2,
        test_period_years: int = 1,
        quiet: bool = False
    ):
        """
        Initialize walk-forward optimizer.

        Args:
            backtest_engine: Configured backtest engine
            train_period_years: Minimum training period (default: 2 years)
            test_period_years: Test period length (default: 1 year)
            quiet: If True, suppress intermediate messages (default: False)
        """
        self.engine = backtest_engine
        self.train_period_years = train_period_years
        self.test_period_years = test_period_years
        self.quiet = quiet

    def generate_walk_forward_periods(
        self,
        start_date: str,
        end_date: str
    ) -> List[WalkForwardPeriod]:
        """
        Generate expanding window train/test splits.

        Args:
            start_date: Overall backtest start date (e.g., "2018-01-01")
            end_date: Overall backtest end date (e.g., "2025-01-01")

        Returns:
            List of WalkForwardPeriod objects
        """
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        periods = []

        # First training period ends after train_period_years
        current_train_end = start_dt + timedelta(days=365.25 * self.train_period_years)

        while current_train_end < end_dt:
            # Test period starts after training ends
            test_start = current_train_end
            test_end = test_start + timedelta(days=365.25 * self.test_period_years)

            # Don't exceed overall end date
            if test_end > end_dt:
                test_end = end_dt

            # Calculate period lengths
            train_days = (current_train_end - start_dt).days
            test_days = (test_end - test_start).days

            if test_days < 30:  # Skip if test period too short
                break

            period = WalkForwardPeriod(
                train_start=start_dt.strftime("%Y-%m-%d"),
                train_end=current_train_end.strftime("%Y-%m-%d"),
                test_start=test_start.strftime("%Y-%m-%d"),
                test_end=test_end.strftime("%Y-%m-%d"),
                train_years=train_days / 365.25,
                test_years=test_days / 365.25
            )
            periods.append(period)

            # Expand window: next training includes this test period
            current_train_end = test_end

        return periods

    def run_walk_forward_optimization(
        self,
        tickers: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        weight_ranges: Optional[Dict[str, List[float]]] = None,
        objective: str = "sharpe_ratio",
        quiet: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Run full walk-forward optimization and validation.

        Args:
            tickers: List of tickers to backtest
            start_date: Start date (default: from config)
            end_date: End date (default: from config)
            weight_ranges: Weight ranges for grid search (default: standard ranges)
            objective: Optimization objective ("sharpe_ratio", "win_rate", or "avg_return")
            quiet: If True, suppress intermediate messages (default: use instance setting)

        Returns:
            Dictionary with aggregated results and per-period breakdown
        """
        # Use instance setting if not overridden
        if quiet is None:
            quiet = self.quiet

        # Use config defaults if not specified
        if start_date is None:
            backtest_config = config.get('backtesting', {})
            start_date = backtest_config.get('start_date', '2018-01-01')
        if end_date is None:
            backtest_config = config.get('backtesting', {})
            end_date = backtest_config.get('end_date', '2025-01-01')

        if not quiet:
            print("\n" + "="*80)
            print("WALK-FORWARD OPTIMIZATION (Phase 4)")
            print("="*80)
            print(f"Period: {start_date} to {end_date}")
            print(f"Objective: {objective}")
            print(f"Strategy: Expanding window (train on ALL past data)")
            print("="*80 + "\n")

        # Generate periods
        periods = self.generate_walk_forward_periods(start_date, end_date)

        if not periods:
            print("ERROR: No valid walk-forward periods generated")
            print("Check date range and period settings")
            return {
                'periods': [],
                'aggregated_test_metrics': {},
                'success': False
            }

        if not quiet:
            print(f"Generated {len(periods)} walk-forward periods:\n")
            for i, period in enumerate(periods, 1):
                print(f"  Period {i}:")
                print(f"    Train: {period.train_start} to {period.train_end} ({period.train_years:.1f} years)")
                print(f"    Test:  {period.test_start} to {period.test_end} ({period.test_years:.1f} years)")

            print("\n" + "-"*80 + "\n")

        # Run optimization for each period
        results = []
        all_test_trades = []

        for i, period in enumerate(periods, 1):
            if not quiet:
                print(f"\n{'='*80}")
                print(f"PERIOD {i}/{len(periods)}")
                print(f"{'='*80}")

                # Optimize on training period
                print(f"\n[1/2] Optimizing weights on training data ({period.train_start} to {period.train_end})...")

            # Temporarily update engine date range for training
            original_start = self.engine.start_date
            original_end = self.engine.end_date

            self.engine.start_date = datetime.strptime(period.train_start, "%Y-%m-%d")
            self.engine.end_date = datetime.strptime(period.train_end, "%Y-%m-%d")

            # Run optimization
            optimizer = WeightOptimizer(self.engine, quiet=quiet)
            best_weights, train_score = optimizer.optimize_weights(
                tickers=tickers,
                weight_ranges=weight_ranges,
                objective=objective,
                quiet=quiet
            )

            if not quiet:
                print(f"\nOptimized weights (training): {best_weights}")
                print(f"Training {objective}: {train_score:.4f}")

            # Get training metrics
            trades = self.engine.run_backtest(tickers, rebalance_frequency_days=30, quiet=quiet)
            train_metrics_obj = PerformanceMetrics(trades)
            train_overall = train_metrics_obj.calculate_overall_metrics()
            train_risk = train_metrics_obj.calculate_risk_adjusted_metrics()

            if not quiet:
                # Test on out-of-sample period
                print(f"\n[2/2] Testing on out-of-sample data ({period.test_start} to {period.test_end})...")

            self.engine.start_date = datetime.strptime(period.test_start, "%Y-%m-%d")
            self.engine.end_date = datetime.strptime(period.test_end, "%Y-%m-%d")

            # Apply optimized weights to config and run backtest
            self._set_weights(best_weights)
            test_trades = self.engine.run_backtest(tickers, rebalance_frequency_days=30, quiet=quiet)

            test_metrics_obj = PerformanceMetrics(test_trades)
            test_overall = test_metrics_obj.calculate_overall_metrics()
            test_risk = test_metrics_obj.calculate_risk_adjusted_metrics()

            if not quiet:
                print(f"\nOUT-OF-SAMPLE TEST RESULTS:")
                print(f"  Total Trades: {test_overall['total_trades']}")
                print(f"  Win Rate: {test_overall['win_rate_pct']:.1f}%")
                print(f"  Avg Return: {test_overall['avg_return_pct']:+.2f}%")
                print(f"  Sharpe Ratio: {test_risk['sharpe_ratio']:.3f}")
                print(f"  Max Drawdown: {test_risk['max_drawdown_pct']:.2f}%")

            # Store results
            result = WalkForwardResult(
                period=period,
                optimized_weights=best_weights,
                train_metrics={'overall': train_overall, 'risk': train_risk},
                test_metrics={'overall': test_overall, 'risk': test_risk},
                test_trades=test_trades
            )
            results.append(result)
            all_test_trades.extend(test_trades)

            # Restore original dates
            self.engine.start_date = original_start
            self.engine.end_date = original_end

        # Aggregate all test results
        aggregated_metrics = PerformanceMetrics(all_test_trades)
        agg_overall = aggregated_metrics.calculate_overall_metrics()
        agg_risk = aggregated_metrics.calculate_risk_adjusted_metrics()

        # Always print aggregated results (even in quiet mode) - this is the key output
        print("\n" + "="*80)
        print("AGGREGATED OUT-OF-SAMPLE RESULTS (All Test Periods)")
        print("="*80)

        print(f"\nTotal Test Trades: {agg_overall['total_trades']}")
        print(f"Win Rate: {agg_overall['win_rate_pct']:.1f}%")
        print(f"Avg Return: {agg_overall['avg_return_pct']:+.2f}%")
        print(f"Median Return: {agg_overall['median_return_pct']:+.2f}%")
        print(f"\nRisk-Adjusted Metrics:")
        print(f"  Sharpe Ratio: {agg_risk['sharpe_ratio']:.3f}")
        print(f"  Sortino Ratio: {agg_risk['sortino_ratio']:.3f}")
        print(f"  Max Drawdown: {agg_risk['max_drawdown_pct']:.2f}%")
        print(f"  Calmar Ratio: {agg_risk['calmar_ratio']:.3f}")
        print(f"  Annualized Return: {agg_risk['annualized_return_pct']:+.2f}%")
        print(f"  Annualized Volatility: {agg_risk['annualized_volatility_pct']:.2f}%")

        print("\n" + "="*80 + "\n")

        return {
            'periods': results,
            'aggregated_test_metrics': {
                'overall': agg_overall,
                'risk': agg_risk
            },
            'all_test_trades': all_test_trades,
            'n_periods': len(periods),
            'success': True
        }

    def _set_weights(self, weights: Dict[str, float]):
        """
        Temporarily set weights in config for testing.

        Args:
            weights: Dictionary mapping category names to weights
        """
        if hasattr(config, '_config') and config._config:
            config._config['weights'] = weights.copy()

    def print_period_comparison(self, results: Dict[str, Any], quiet: bool = False):
        """
        Print comparison table across all walk-forward periods.

        Args:
            results: Results from run_walk_forward_optimization()
            quiet: If True, suppress output (default: False)
        """
        if quiet:
            return

        if not results.get('success') or not results['periods']:
            print("No results to display")
            return

        print("\n" + "="*100)
        print("WALK-FORWARD PERIOD COMPARISON")
        print("="*100)
        print(f"{'Period':<8} {'Test Range':<25} {'Trades':<8} {'Win Rate':<10} {'Avg Ret':<10} {'Sharpe':<10} {'Max DD':<10}")
        print("-"*100)

        for i, result in enumerate(results['periods'], 1):
            test_range = f"{result.period.test_start} to {result.period.test_end}"
            overall = result.test_metrics['overall']
            risk = result.test_metrics['risk']

            print(f"{i:<8} {test_range:<25} {overall['total_trades']:<8} "
                  f"{overall['win_rate_pct']:>6.1f}%    {overall['avg_return_pct']:>+6.2f}%    "
                  f"{risk['sharpe_ratio']:>6.3f}    {risk['max_drawdown_pct']:>6.2f}%")

        # Aggregated row
        agg_overall = results['aggregated_test_metrics']['overall']
        agg_risk = results['aggregated_test_metrics']['risk']

        print("-"*100)
        print(f"{'ALL':<8} {'Aggregated (out-of-sample)':<25} {agg_overall['total_trades']:<8} "
              f"{agg_overall['win_rate_pct']:>6.1f}%    {agg_overall['avg_return_pct']:>+6.2f}%    "
              f"{agg_risk['sharpe_ratio']:>6.3f}    {agg_risk['max_drawdown_pct']:>6.2f}%")

        print("="*100 + "\n")
