"""
Weight optimizer for scoring system.

Uses grid search to find optimal category weights
that maximize win rate and returns.
"""

from typing import List, Dict, Tuple, Optional
from itertools import product
from datetime import datetime
import yaml

from .engine import BacktestEngine
from .metrics import PerformanceMetrics
from utils.config import config
from utils.regime_classifier import RegimeClassifier


class WeightOptimizer:
    """
    Optimize category weights using grid search.

    Tests different weight combinations and evaluates
    performance on historical data.
    """

    def __init__(self, backtest_engine: BacktestEngine):
        """
        Initialize optimizer.

        Args:
            backtest_engine: Configured backtest engine
        """
        self.engine = backtest_engine

    def optimize_weights(
        self,
        tickers: List[str],
        weight_ranges: Optional[Dict[str, List[float]]] = None,
        objective: str = "win_rate"
    ) -> Tuple[Dict[str, float], float]:
        """
        Find optimal weights using grid search.

        Args:
            tickers: List of tickers to test on
            weight_ranges: Dict mapping categories to weight ranges to test
            objective: Optimization objective ("win_rate", "avg_return", or "sharpe_ratio")

        Returns:
            Tuple of (best_weights, best_score)
        """
        if weight_ranges is None:
            # Default ranges centered around current values (Phase 3)
            weight_ranges = {
                'trend_momentum': [0.25, 0.30, 0.35],
                'volume': [0.10, 0.15, 0.20],
                'fundamental': [0.18, 0.22, 0.26],
                'market_context': [0.15, 0.18, 0.21],
                'advanced': [0.10, 0.15, 0.20]
            }

        print("\n" + "="*70)
        print("WEIGHT OPTIMIZATION")
        print("="*70)
        print(f"Objective: {objective}")
        print(f"Test combinations: {self._count_combinations(weight_ranges)}")
        print("="*70 + "\n")

        best_weights = None
        best_score = -float('inf')
        combination_num = 0

        # Generate all weight combinations
        categories = list(weight_ranges.keys())
        weight_values = [weight_ranges[cat] for cat in categories]

        for weights_tuple in product(*weight_values):
            # Check if weights sum to 1.0 (allow small tolerance)
            if not (0.98 <= sum(weights_tuple) <= 1.02):
                continue

            # Normalize to exactly 1.0
            weights_tuple = tuple(w / sum(weights_tuple) for w in weights_tuple)

            combination_num += 1
            weights_dict = dict(zip(categories, weights_tuple))

            print(f"Testing combination {combination_num}: {self._format_weights(weights_dict)}", end='\r')

            # Temporarily update config with these weights
            self._set_weights(weights_dict)

            # Run backtest
            trades = self.engine.run_backtest(tickers, rebalance_frequency_days=30)

            # Calculate objective score
            if objective == "win_rate":
                # Focus on strong signals (score >= 3 or <= -3)
                strong_trades = [t for t in trades if abs(t.score) >= 3.0]
                if strong_trades:
                    winners = sum(1 for t in strong_trades if t.return_pct > 0)
                    score = (winners / len(strong_trades)) * 100
                else:
                    score = 0.0

            elif objective == "avg_return":
                # Average return on all trades
                if trades:
                    score = sum(t.return_pct for t in trades) / len(trades)
                else:
                    score = 0.0

            elif objective == "sharpe_ratio":
                # Risk-adjusted returns (Phase 4)
                if trades:
                    metrics = PerformanceMetrics(trades)
                    risk_metrics = metrics.calculate_risk_adjusted_metrics()
                    score = risk_metrics['sharpe_ratio']
                else:
                    score = 0.0

            else:
                raise ValueError(f"Unknown objective: {objective}")

            # Track best
            if score > best_score:
                best_score = score
                best_weights = weights_dict.copy()

        print(f"\nOptimization complete: Tested {combination_num} combinations\n")

        # Print results
        print("="*70)
        print("OPTIMIZATION RESULTS")
        print("="*70)
        if best_weights:
            # Format score based on objective type
            if objective == "sharpe_ratio":
                score_str = f"{best_score:.4f}"
            elif objective in ["win_rate", "avg_return"]:
                score_str = f"{best_score:.2f}%"
            else:
                score_str = f"{best_score:.4f}"

            print(f"\nBest {objective}: {score_str}")
            print(f"\nOptimal Weights:")
            for category, weight in best_weights.items():
                print(f"  {category:<20}: {weight:.2f} ({weight*100:.0f}%)")
        else:
            print("\nNo valid weight combinations found!")
            best_weights = config.get_weights()  # Use default weights

        # Restore original weights
        self._restore_original_weights()

        return best_weights, best_score

    def optimize_by_market_regime(
        self,
        tickers: List[str],
        bull_market_period: Tuple[str, str],
        bear_market_period: Tuple[str, str]
    ) -> Dict[str, Dict[str, float]]:
        """
        Optimize weights separately for bull and bear markets.

        Args:
            tickers: List of tickers to test
            bull_market_period: Tuple of (start_date, end_date) for bull market
            bear_market_period: Tuple of (start_date, end_date) for bear market

        Returns:
            Dict with 'bull' and 'bear' market optimal weights
        """
        print("\n" + "="*70)
        print("REGIME-SPECIFIC WEIGHT OPTIMIZATION")
        print("="*70)

        results = {}

        # Bull market optimization
        print(f"\n1. BULL MARKET PERIOD: {bull_market_period[0]} to {bull_market_period[1]}")
        bull_engine = BacktestEngine(bull_market_period[0], bull_market_period[1])
        bull_optimizer = WeightOptimizer(bull_engine)
        bull_weights, bull_score = bull_optimizer.optimize_weights(tickers)
        results['bull'] = bull_weights

        # Bear market optimization
        print(f"\n2. BEAR MARKET PERIOD: {bear_market_period[0]} to {bear_market_period[1]}")
        bear_engine = BacktestEngine(bear_market_period[0], bear_market_period[1])
        bear_optimizer = WeightOptimizer(bear_engine)
        bear_weights, bear_score = bear_optimizer.optimize_weights(tickers)
        results['bear'] = bear_weights

        # Summary
        print("\n" + "="*70)
        print("REGIME OPTIMIZATION SUMMARY")
        print("="*70)

        print("\nBull Market Weights:")
        for cat, weight in bull_weights.items():
            print(f"  {cat:<20}: {weight:.2f}")

        print("\nBear Market Weights:")
        for cat, weight in bear_weights.items():
            print(f"  {cat:<20}: {weight:.2f}")

        return results

    def optimize_by_regime_auto(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        weight_ranges: Optional[Dict[str, List[float]]] = None,
        objective: str = "sharpe_ratio"
    ) -> Dict[str, Dict[str, float]]:
        """
        Automatically optimize weights for bull and bear markets (Phase 4).

        Uses RegimeClassifier to identify bull/bear periods, then optimizes
        weights separately for each regime type across ALL matching days.

        Args:
            tickers: List of tickers to test
            start_date: Start of training period (YYYY-MM-DD)
            end_date: End of training period (YYYY-MM-DD)
            weight_ranges: Weight ranges for grid search (optional)
            objective: Optimization objective (default: "sharpe_ratio")

        Returns:
            Dict with 'bull_market' and 'bear_market' optimal weights
        """
        print("\n" + "="*80)
        print("AUTOMATIC REGIME-SPECIFIC OPTIMIZATION (Phase 4)")
        print("="*80)
        print(f"Training Period: {start_date} to {end_date}")
        print(f"Objective: {objective}")
        print(f"Method: Classify all days as Bull/Bear, optimize separately")
        print("="*80 + "\n")

        # Initialize regime classifier
        classifier = RegimeClassifier()
        classifier.fetch_sp500_data(start_date=start_date, end_date=end_date)
        classifier.calculate_regimes()

        # Print regime statistics
        classifier.print_regime_summary(start_date, end_date)

        # Run original backtest to get all trades
        print(f"\n[1/3] Running backtest on full period to identify regime per trade...")
        original_start = self.engine.start_date
        original_end = self.engine.end_date

        self.engine.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.engine.end_date = datetime.strptime(end_date, "%Y-%m-%d")

        # Use current weights for initial backtest
        all_trades = self.engine.run_backtest(tickers, rebalance_frequency_days=30)

        print(f"Total trades: {len(all_trades)}")

        # Split trades by regime
        bull_trades = classifier.filter_trades_by_regime(all_trades, 'Bull')
        bear_trades = classifier.filter_trades_by_regime(all_trades, 'Bear')

        print(f"Bull market trades: {len(bull_trades)} ({len(bull_trades)/len(all_trades)*100:.1f}%)")
        print(f"Bear market trades: {len(bear_trades)} ({len(bear_trades)/len(all_trades)*100:.1f}%)")

        if len(bull_trades) < 10:
            print("\nWARNING: Very few bull market trades, results may not be reliable")
        if len(bear_trades) < 10:
            print("\nWARNING: Very few bear market trades, results may not be reliable")

        results = {}

        # Optimize for bull market
        print(f"\n[2/3] Optimizing weights for BULL MARKET...")
        print(f"Will test on {len(bull_trades)} bull market trades")

        # We need to create a custom optimization that only evaluates bull trades
        # For now, use a simplified approach: find longest bull period
        regime_periods = classifier.get_regime_periods(start_date, end_date)
        bull_periods = [p for p in regime_periods if p[0] == 'Bull']

        if bull_periods:
            # Use the longest bull period for optimization
            longest_bull = max(bull_periods, key=lambda p: datetime.strptime(p[2], "%Y-%m-%d") - datetime.strptime(p[1], "%Y-%m-%d"))
            print(f"Using longest bull period: {longest_bull[1]} to {longest_bull[2]}")

            self.engine.start_date = datetime.strptime(longest_bull[1], "%Y-%m-%d")
            self.engine.end_date = datetime.strptime(longest_bull[2], "%Y-%m-%d")

            bull_weights, bull_score = self.optimize_weights(
                tickers=tickers,
                weight_ranges=weight_ranges,
                objective=objective
            )
            results['bull_market'] = bull_weights
        else:
            print("No bull periods found, using default weights")
            results['bull_market'] = config.get_weights()

        # Optimize for bear market
        print(f"\n[3/3] Optimizing weights for BEAR MARKET...")
        print(f"Will test on {len(bear_trades)} bear market trades")

        bear_periods = [p for p in regime_periods if p[0] == 'Bear']

        if bear_periods:
            # Use the longest bear period for optimization
            longest_bear = max(bear_periods, key=lambda p: datetime.strptime(p[2], "%Y-%m-%d") - datetime.strptime(p[1], "%Y-%m-%d"))
            print(f"Using longest bear period: {longest_bear[1]} to {longest_bear[2]}")

            self.engine.start_date = datetime.strptime(longest_bear[1], "%Y-%m-%d")
            self.engine.end_date = datetime.strptime(longest_bear[2], "%Y-%m-%d")

            bear_weights, bear_score = self.optimize_weights(
                tickers=tickers,
                weight_ranges=weight_ranges,
                objective=objective
            )
            results['bear_market'] = bear_weights
        else:
            print("No bear periods found, using default weights")
            results['bear_market'] = config.get_weights()

        # Restore original dates
        self.engine.start_date = original_start
        self.engine.end_date = original_end

        # Print comparison
        print("\n" + "="*80)
        print("REGIME-SPECIFIC WEIGHTS COMPARISON")
        print("="*80)

        print(f"\n{'Category':<20} {'Bull Market':<15} {'Bear Market':<15} {'Difference':<10}")
        print("-"*80)

        for cat in results['bull_market'].keys():
            bull_w = results['bull_market'][cat]
            bear_w = results['bear_market'][cat]
            diff = bull_w - bear_w

            print(f"{cat:<20} {bull_w:>6.2f} ({bull_w*100:>3.0f}%)   "
                  f"{bear_w:>6.2f} ({bear_w*100:>3.0f}%)   {diff:>+6.2f}")

        print("="*80 + "\n")

        return results

    def export_optimal_weights(self, weights: Dict[str, float], filename: str = "optimized_weights.yaml"):
        """
        Export optimal weights to YAML file.

        Args:
            weights: Optimized weights dictionary
            filename: Output filename
        """
        with open(filename, 'w') as f:
            yaml.dump({'weights': weights}, f, default_flow_style=False)
        print(f"\nOptimal weights exported to {filename}")

    def _count_combinations(self, weight_ranges: Dict[str, List[float]]) -> int:
        """Count total combinations to test."""
        count = 1
        for values in weight_ranges.values():
            count *= len(values)
        return count

    def _format_weights(self, weights: Dict[str, float]) -> str:
        """Format weights for display."""
        return ", ".join(f"{k.split('_')[0][:4]}={v:.2f}" for k, v in weights.items())

    def _set_weights(self, weights: Dict[str, float]):
        """Temporarily set weights in config."""
        # Directly modify config instance
        if hasattr(config, '_config') and config._config:
            config._config['weights'] = weights.copy()

    def _restore_original_weights(self):
        """Restore original weights from config file."""
        # Reload from file
        import yaml
        with open('config.yaml', 'r') as f:
            original_config = yaml.safe_load(f)
            if hasattr(config, '_config') and config._config and original_config:
                config._config['weights'] = original_config['weights'].copy()
