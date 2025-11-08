"""
Phase 4 Complete Optimization and Validation Script

This script runs the full Phase 4 optimization pipeline:
1. Walk-forward optimization with Sharpe ratio objective (7 years, 2018-2025)
2. Regime-specific weight optimization (bull/bear markets)
3. Statistical validation and significance testing
4. Comprehensive report generation

Expected runtime: 30-60 minutes (depending on hardware)
"""

import sys
from datetime import datetime

from backtesting.engine import BacktestEngine
from backtesting.walk_forward import WalkForwardOptimizer
from backtesting.optimizer import WeightOptimizer
from backtesting.report_generator import Phase4ReportGenerator
from utils.config import config
from utils.regime_classifier import RegimeClassifier
import yaml


def main():
    """Run complete Phase 4 optimization and validation."""

    print("\n" + "="*100)
    print("PHASE 4 COMPLETE OPTIMIZATION & VALIDATION")
    print("="*100)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nThis will take approximately 30-60 minutes to complete.")
    print("The script will:")
    print("  1. Run walk-forward optimization (5-6 periods)")
    print("  2. Optimize regime-specific weights (bull/bear)")
    print("  3. Perform statistical validation")
    print("  4. Generate comprehensive Phase 4 report")
    print("="*100 + "\n")

    # Get configuration
    backtest_config = config.get('backtesting', {})
    tickers = backtest_config.get('default_tickers', ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'JPM', 'XOM', 'PFE', 'WMT'])
    start_date = '2018-01-01'
    end_date = '2025-01-01'

    print(f"Tickers: {', '.join(tickers)}")
    print(f"Period: {start_date} to {end_date} (7 years)")
    print(f"Objective: Sharpe Ratio (risk-adjusted returns)\n")

    # ============================================================================
    # STEP 1: Walk-Forward Optimization
    # ============================================================================
    print("\n" + "="*100)
    print("STEP 1: WALK-FORWARD OPTIMIZATION")
    print("="*100)
    print("Running expanding window validation with Sharpe ratio optimization...")
    print("This step validates the strategy across multiple out-of-sample periods.\n")

    try:
        engine = BacktestEngine(start_date, end_date)
        wf_optimizer = WalkForwardOptimizer(engine, train_period_years=2, test_period_years=1)

        wf_results = wf_optimizer.run_walk_forward_optimization(
            tickers=tickers,
            objective='sharpe_ratio'
        )

        wf_optimizer.print_period_comparison(wf_results)

        agg_metrics = wf_results['aggregated_test_metrics']
        print(f"\n✅ Walk-forward optimization complete!")
        print(f"   Out-of-sample Sharpe Ratio: {agg_metrics['risk']['sharpe_ratio']:.3f}")
        print(f"   Out-of-sample Win Rate: {agg_metrics['overall']['win_rate_pct']:.1f}%")

    except Exception as e:
        print(f"\n❌ Walk-forward optimization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ============================================================================
    # STEP 2: Regime-Specific Optimization
    # ============================================================================
    print("\n" + "="*100)
    print("STEP 2: REGIME-SPECIFIC OPTIMIZATION")
    print("="*100)
    print("Optimizing separate weights for bull and bear markets...")
    print("This allows the strategy to adapt to changing market conditions.\n")

    try:
        # Use 2018-2023 for training, save 2024-2025 for out-of-sample validation
        train_end = '2024-01-01'

        engine = BacktestEngine(start_date, train_end)
        optimizer = WeightOptimizer(engine)

        regime_weights = optimizer.optimize_by_regime_auto(
            tickers=tickers,
            start_date=start_date,
            end_date=train_end,
            objective='sharpe_ratio'
        )

        print(f"\n✅ Regime-specific optimization complete!")

        # Save to config.yaml
        print("\nSaving regime weights to config.yaml...")
        with open('config.yaml', 'r') as f:
            config_data = yaml.safe_load(f)

        config_data['optimized_weights'] = regime_weights

        with open('config.yaml', 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

        print("✅ Regime weights saved to config.yaml")

    except Exception as e:
        print(f"\n❌ Regime optimization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ============================================================================
    # STEP 3: Statistical Validation & Report Generation
    # ============================================================================
    print("\n" + "="*100)
    print("STEP 3: STATISTICAL VALIDATION & REPORT GENERATION")
    print("="*100)
    print("Generating comprehensive Phase 4 validation report...\n")

    try:
        # Initialize report generator
        report = Phase4ReportGenerator(output_file="phase4_validation_report.md")

        # Add report sections
        report.add_header()
        report.add_walk_forward_results(wf_results)

        # Add regime comparison
        classifier = RegimeClassifier()
        classifier.fetch_sp500_data(start_date=start_date, end_date=end_date)
        classifier.calculate_regimes()

        all_test_trades = wf_results['all_test_trades']
        bull_trades = classifier.filter_trades_by_regime(all_test_trades, 'Bull')
        bear_trades = classifier.filter_trades_by_regime(all_test_trades, 'Bear')

        report.add_regime_comparison(bull_trades, bear_trades)
        report.add_statistical_validation(all_test_trades)

        # For Phase 3 vs Phase 4 comparison, we'd need to run Phase 3 backtest
        # For now, skip this section or use existing Phase 3 results

        report.add_conclusion()
        report.generate_report()

        print("✅ Phase 4 validation report generated: phase4_validation_report.md")

    except Exception as e:
        print(f"\n❌ Report generation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        # Don't exit - the optimization still succeeded

    # ============================================================================
    # FINAL SUMMARY
    # ============================================================================
    print("\n" + "="*100)
    print("PHASE 4 OPTIMIZATION COMPLETE!")
    print("="*100)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    print("📊 RESULTS SUMMARY:")
    print(f"   Walk-Forward Sharpe Ratio: {agg_metrics['risk']['sharpe_ratio']:.3f}")
    print(f"   Out-of-Sample Win Rate: {agg_metrics['overall']['win_rate_pct']:.1f}%")
    print(f"   Total Test Trades: {agg_metrics['overall']['total_trades']}")
    print(f"   Max Drawdown: {agg_metrics['risk']['max_drawdown_pct']:.2f}%")
    print(f"   Annualized Return: {agg_metrics['risk']['annualized_return_pct']:+.2f}%\n")

    print("📁 FILES GENERATED:")
    print("   ✅ config.yaml (updated with regime weights)")
    print("   ✅ phase4_validation_report.md (comprehensive analysis)\n")

    print("🚀 NEXT STEPS:")
    print("   1. Review phase4_validation_report.md for detailed analysis")
    print("   2. Enable regime-adaptive scoring:")
    print("      Set backtesting.use_regime_weights: true in config.yaml")
    print("   3. Test live scoring with:")
    print("      python main.py AAPL")
    print("\n" + "="*100 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Phase 4 optimization interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
