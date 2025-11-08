"""
Weight optimizer for scoring system.

Uses grid search to find optimal category weights
that maximize win rate and returns.
"""

from typing import List, Dict, Tuple, Optional
from itertools import product
import yaml

from .engine import BacktestEngine
from .metrics import PerformanceMetrics
from utils.config import config


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
            objective: Optimization objective ("win_rate" or "avg_return")

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
            print(f"\nBest {objective}: {best_score:.2f}{'%' if objective == 'win_rate' else '%'}")
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
