"""
Sector Optimizer - Phase 5c
Automatically optimizes sector-specific indicator multipliers to achieve 75%+ win rate.

Uses grid search to test different multiplier combinations and finds optimal values
based on historical backtest performance.
"""

import itertools
import copy
import random
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass

from backtesting.engine import BacktestEngine
from utils.config import config


@dataclass
class OptimizationResult:
    """Result from sector optimization."""
    sector: str
    win_rate: float
    avg_return: float
    total_trades: int
    best_config: Dict[str, Any]
    improvement: float  # Win rate improvement vs baseline


class SectorOptimizer:
    """
    Optimizes sector-specific weight multipliers and indicator overrides.
    Phase 5c implementation.
    """

    def __init__(self, engine: BacktestEngine):
        """
        Initialize sector optimizer.

        Args:
            engine: Configured BacktestEngine instance
        """
        self.engine = engine
        self.baseline_results = {}

    def run_baseline(self, tickers: List[str]) -> Dict[str, Dict[str, float]]:
        """
        Run baseline backtest to establish starting performance.

        Args:
            tickers: List of tickers to test

        Returns:
            Dict mapping sector to performance metrics
        """
        print("\n" + "="*80)
        print("RUNNING BASELINE BACKTEST (No optimizations)")
        print("="*80)
        print(f"Testing {len(tickers)} tickers from {self.engine.start_date.strftime('%Y-%m-%d')} to {self.engine.end_date.strftime('%Y-%m-%d')}")
        print("This will take 5-10 minutes...")
        print("-" * 80)

        trades = self.engine.run_backtest(tickers, quiet=False, sector_analysis=False)  # Show progress bar

        # Group by sector
        sector_performance = {}
        for trade in trades:
            sector = trade.sector if trade.sector else 'Unknown'
            if sector not in sector_performance:
                sector_performance[sector] = {'wins': 0, 'losses': 0, 'returns': []}

            if trade.return_pct > 0:
                sector_performance[sector]['wins'] += 1
            else:
                sector_performance[sector]['losses'] += 1
            sector_performance[sector]['returns'].append(trade.return_pct)

        # Calculate metrics
        for sector, data in sector_performance.items():
            total = data['wins'] + data['losses']
            win_rate = (data['wins'] / total * 100) if total > 0 else 0
            avg_return = sum(data['returns']) / len(data['returns']) if data['returns'] else 0

            sector_performance[sector]['win_rate'] = win_rate
            sector_performance[sector]['avg_return'] = avg_return
            sector_performance[sector]['total_trades'] = total

            print(f"\n{sector}: {win_rate:.1f}% win rate ({data['wins']}/{total}), {avg_return:+.2f}% avg return")

        self.baseline_results = sector_performance
        return sector_performance

    def optimize_sector(self, sector: str, tickers: List[str],
                       target_win_rate: float = 75.0,
                       test_ranges: Optional[Dict[str, List[float]]] = None,
                       max_samples: int = 40,
                       use_subset: bool = True) -> OptimizationResult:
        """
        Find optimal indicator multipliers for a specific sector using random search.

        Args:
            sector: Sector name to optimize
            tickers: Tickers in this sector
            target_win_rate: Target win rate percentage (default: 75.0)
            test_ranges: Dict of multiplier names to ranges to test
            max_samples: Maximum number of random configurations to test (default: 40)
            use_subset: Use only 3 tickers for faster optimization (default: True)

        Returns:
            OptimizationResult with best configuration
        """
        print("\n" + "="*80)
        print(f"OPTIMIZING SECTOR: {sector}")
        print(f"Target Win Rate: {target_win_rate}%")
        print("="*80)

        # Use subset of tickers for faster optimization
        if use_subset and len(tickers) > 3:
            opt_tickers = tickers[:3]  # Use first 3 tickers for robust optimization
            print(f"Using subset of tickers for optimization: {', '.join(opt_tickers)}")
        else:
            opt_tickers = tickers
            print(f"Using all {len(opt_tickers)} tickers")

        # Create shorter-range engine for faster optimization (last 3 years)
        from datetime import datetime, timedelta
        opt_end_date = self.engine.end_date
        opt_start_date = opt_end_date - timedelta(days=1095)  # 3 years back
        opt_engine = BacktestEngine(
            start_date=opt_start_date.strftime('%Y-%m-%d'),
            end_date=opt_end_date.strftime('%Y-%m-%d'),
            holding_period_days=self.engine.holding_period_days
        )
        print(f"Optimization period: {opt_start_date.strftime('%Y-%m-%d')} to {opt_end_date.strftime('%Y-%m-%d')} (3 years)")

        # Default test ranges if not provided
        if test_ranges is None:
            test_ranges = {
                # Weight multipliers (affect category importance)
                'trend_momentum': [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5],
                'fundamental': [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6],
                'market_context': [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5],
                # Indicator overrides (affect individual indicators)
                'rsi_score_multiplier': [0.3, 0.4, 0.5, 0.7, 1.0, 1.3, 1.5],
                'macd_score_multiplier': [0.3, 0.4, 0.5, 0.7, 1.0, 1.3, 1.5],
                'roe_score_multiplier': [0.8, 1.0, 1.2, 1.4, 1.5, 1.8],
                'revenue_growth_multiplier': [0.3, 0.5, 0.8, 1.0, 1.2, 1.5, 1.8],
            }

        # Get baseline for this sector
        baseline_win_rate = self.baseline_results.get(sector, {}).get('win_rate', 0)
        print(f"Baseline Win Rate: {baseline_win_rate:.1f}%")
        print(f"Improvement Needed: {target_win_rate - baseline_win_rate:+.1f} points\n")

        # Grid search over parameter combinations
        best_config: Dict[str, float] = {}
        best_win_rate = baseline_win_rate
        best_avg_return = 0
        configs_tested = 0
        trades = []  # Initialize to avoid unbound variable warning

        # RANDOM SEARCH: Test random parameter combinations (much faster than exhaustive grid search)
        # Test major parameters that typically have biggest impact
        major_params = ['trend_momentum', 'fundamental', 'rsi_score_multiplier',
                       'roe_score_multiplier', 'revenue_growth_multiplier']

        # Generate random configurations
        print(f"Using RANDOM SEARCH: Testing {max_samples} random configurations...")
        estimated_minutes = max_samples * 35 / 60  # ~35 seconds per config (3yr, 3 tickers)
        print(f"(Estimated time: {estimated_minutes:.0f} minutes)")
        print("=" * 80)

        for i in range(max_samples):
            configs_tested += 1

            # Progress indicator EVERY config for visibility
            progress = (configs_tested / max_samples) * 100
            print(f"[Progress: {progress:5.1f}%] Config {configs_tested}/{max_samples} | Best: {best_win_rate:.1f}%", end='\r')

            # Build random test config by randomly sampling from test_ranges
            test_config = {}
            for param in major_params:
                if param in test_ranges:
                    test_config[param] = random.choice(test_ranges[param])
                else:
                    test_config[param] = 1.0  # Default to 1.0 if not in test_ranges

            # Apply config temporarily
            original_config = self._apply_test_config(sector, test_config)

            # Run backtest with this config (quiet mode, shorter period, subset of tickers)
            trades = opt_engine.run_backtest(opt_tickers, quiet=True, sector_analysis=False)

            # Calculate win rate for this sector
            sector_trades = [t for t in trades if t.sector == sector]
            if sector_trades:
                wins = sum(1 for t in sector_trades if t.return_pct > 0)
                win_rate = (wins / len(sector_trades)) * 100
                avg_return = sum(t.return_pct for t in sector_trades) / len(sector_trades)

                # Check if this is better
                if win_rate > best_win_rate:
                    best_win_rate = win_rate
                    best_avg_return = avg_return
                    best_config = test_config.copy()

                    print(f"\n{'':80}")  # Clear progress line
                    print(f">>> [{configs_tested}/{max_samples}] NEW BEST: {win_rate:.1f}% win rate "
                          f"(+{win_rate - baseline_win_rate:.1f} pts)")
                    print(f"    Config: {test_config}")

            # Restore original config
            self._restore_config(sector, original_config)

        # Results
        print(f"\n{'':80}")  # Clear progress line
        print("\n" + "="*80)
        print(f"OPTIMIZATION COMPLETE: {sector}")
        print("="*80)
        print(f"Optimized on: {len(opt_tickers)} tickers, {opt_start_date.strftime('%Y-%m-%d')} to {opt_end_date.strftime('%Y-%m-%d')} (3 years)")
        print(f"Baseline Win Rate: {baseline_win_rate:.1f}%")
        print(f"Optimized Win Rate: {best_win_rate:.1f}%")
        print(f"Improvement: {best_win_rate - baseline_win_rate:+.1f} points")
        print(f"Avg Return: {best_avg_return:+.2f}%")
        print(f"\nBest Configuration:")
        for param, value in best_config.items():
            print(f"  {param}: {value}")

        if best_win_rate >= target_win_rate:
            print(f"\n✓ TARGET ACHIEVED: {best_win_rate:.1f}% >= {target_win_rate}%")
        else:
            print(f"\n✗ TARGET MISSED: {best_win_rate:.1f}% < {target_win_rate}% "
                  f"(gap: {target_win_rate - best_win_rate:.1f} points)")

        return OptimizationResult(
            sector=sector,
            win_rate=best_win_rate,
            avg_return=best_avg_return,
            total_trades=len([t for t in trades if t.sector == sector]),
            best_config=best_config,
            improvement=best_win_rate - baseline_win_rate
        )

    def optimize_all_sectors(self, tickers_by_sector: Dict[str, List[str]],
                            target_win_rate: float = 75.0) -> Dict[str, OptimizationResult]:
        """
        Optimize all sectors to achieve target win rate.

        Args:
            tickers_by_sector: Dict mapping sector names to lists of tickers
            target_win_rate: Target win rate for all sectors

        Returns:
            Dict mapping sector names to OptimizationResults
        """
        print("\n" + "="*80)
        print("PHASE 5C: AUTOMATED SECTOR OPTIMIZATION")
        print(f"Target: {target_win_rate}% win rate across ALL sectors")
        print(f"Methodology: 40 random configs per sector, 3 tickers, 3-year period (robust mode)")
        print("="*80)

        # Run baseline first
        all_tickers = [ticker for tickers in tickers_by_sector.values() for ticker in tickers]
        self.run_baseline(all_tickers)

        # Optimize each sector
        results = {}
        for sector, tickers in tickers_by_sector.items():
            result = self.optimize_sector(sector, tickers, target_win_rate)
            results[sector] = result

            # Apply best config for this sector
            self._apply_test_config(sector, result.best_config, permanent=True)

        # Final summary
        print("\n" + "="*80)
        print("OPTIMIZATION SUMMARY")
        print("="*80)

        sectors_meeting_target = 0
        for sector, result in results.items():
            status = "✓" if result.win_rate >= target_win_rate else "✗"
            print(f"{status} {sector}: {result.win_rate:.1f}% ({result.improvement:+.1f} pts)")
            if result.win_rate >= target_win_rate:
                sectors_meeting_target += 1

        print(f"\nSectors Meeting Target: {sectors_meeting_target} / {len(results)}")

        if sectors_meeting_target == len(results):
            print("\n🎉 SUCCESS: All sectors achieved 75%+ win rate!")
        else:
            print(f"\n⚠️  {len(results) - sectors_meeting_target} sector(s) still below target")

        return results

    def _apply_test_config(self, sector: str, test_config: Dict[str, float],
                          permanent: bool = False) -> Optional[Dict[str, Any]]:
        """
        Temporarily apply a test configuration to the config.

        Args:
            sector: Sector name
            test_config: Configuration to test
            permanent: If True, don't return original config (optimization complete)

        Returns:
            Original configuration (for restoration), or None if permanent
        """
        sector_adjustments = config.get('sector_adjustments', {})
        if sector_adjustments is None:
            sector_adjustments = {}

        # Save original
        original_config = copy.deepcopy(sector_adjustments.get(sector, {}))

        # Apply test config
        if sector not in sector_adjustments:
            sector_adjustments[sector] = {}

        # Weight multipliers
        if 'weight_multipliers' not in sector_adjustments[sector]:
            sector_adjustments[sector]['weight_multipliers'] = {}

        for key in ['trend_momentum', 'fundamental', 'market_context', 'volume', 'advanced']:
            if key in test_config:
                sector_adjustments[sector]['weight_multipliers'][key] = test_config[key]

        # Indicator overrides
        if 'indicator_overrides' not in sector_adjustments[sector]:
            sector_adjustments[sector]['indicator_overrides'] = {}

        for key, value in test_config.items():
            if '_multiplier' in key or '_weight' in key:
                sector_adjustments[sector]['indicator_overrides'][key] = value

        # Update config object
        config._config['sector_adjustments'] = sector_adjustments

        return original_config if not permanent else None

    def _restore_config(self, sector: str, original_config: Optional[Dict[str, Any]]):
        """Restore original configuration."""
        if original_config is None:
            return  # Nothing to restore
        sector_adjustments = config.get('sector_adjustments', {})
        if sector_adjustments is None:
            sector_adjustments = {}
        sector_adjustments[sector] = original_config
        config._config['sector_adjustments'] = sector_adjustments

    def export_optimized_config(self, results: Dict[str, OptimizationResult], filename: str = "optimized_sector_config.yaml"):
        """
        Export optimized configuration to YAML file.

        Args:
            results: Optimization results
            filename: Output filename
        """
        import yaml

        output = {
            'sector_adjustments': {}
        }

        for sector, result in results.items():
            output['sector_adjustments'][sector] = {
                'weight_multipliers': {},
                'indicator_overrides': {},
                'performance': {
                    'win_rate': result.win_rate,
                    'avg_return': result.avg_return,
                    'improvement': result.improvement
                }
            }

            # Populate with best config
            for key, value in result.best_config.items():
                if key in ['trend_momentum', 'fundamental', 'market_context', 'volume', 'advanced']:
                    output['sector_adjustments'][sector]['weight_multipliers'][key] = value
                else:
                    output['sector_adjustments'][sector]['indicator_overrides'][key] = value

        # Write to file
        with open(filename, 'w') as f:
            yaml.dump(output, f, default_flow_style=False, sort_keys=False)

        print(f"\n✓ Optimized configuration exported to {filename}")


if __name__ == "__main__":
    """
    Run sector optimization from command line.

    Usage:
        python -m backtesting.sector_optimizer
    """
    from utils.config import config

    # Setup
    backtest_config = config.get('backtesting', {})
    start_date = backtest_config.get('start_date', '2018-01-01')
    end_date = backtest_config.get('end_date', '2025-01-01')

    # Create engine
    engine = BacktestEngine(start_date, end_date, holding_period_days=60)

    # Define tickers by sector (3 representative stocks per sector for robust optimization)
    tickers_by_sector = {
        'Technology': ['AAPL', 'MSFT', 'NVDA'],           # Tech giants, semiconductors
        'Healthcare': ['PFE', 'JNJ', 'UNH'],              # Pharma, diversified healthcare, insurance
        'Energy': ['XOM', 'CVX', 'COP'],                  # Integrated oils, exploration
        'Financial Services': ['JPM', 'BAC', 'GS'],       # Banking, investment banking
        'Consumer Defensive': ['WMT', 'PG', 'KO']         # Retail, consumer goods, beverages
    }

    # Run optimization
    optimizer = SectorOptimizer(engine)
    results = optimizer.optimize_all_sectors(tickers_by_sector, target_win_rate=75.0)

    # Export results
    optimizer.export_optimized_config(results)

    print("\n" + "="*80)
    print("Optimization complete! Review optimized_sector_config.yaml")
    print("Copy the configurations to config.yaml to apply them.")
    print("="*80)
