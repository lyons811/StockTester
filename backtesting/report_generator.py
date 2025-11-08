"""
Comprehensive report generator for Phase 4 backtesting results.

Creates detailed validation reports comparing walk-forward results,
regime performance, and statistical significance testing.
"""

from typing import List, Dict, Any
from datetime import datetime
from backtesting.metrics import PerformanceMetrics
from utils.statistics import (
    test_win_rate_significance,
    test_mean_return_significance,
    compare_strategies,
    calculate_confidence_interval
)


class Phase4ReportGenerator:
    """
    Generate comprehensive Phase 4 validation reports.

    Includes:
    - Walk-forward optimization results
    - Regime-specific performance comparison
    - Statistical significance tests
    - Phase 3 vs Phase 4 comparison
    """

    def __init__(self, output_file: str = "phase4_validation_report.md"):
        """
        Initialize report generator.

        Args:
            output_file: Output filename for markdown report
        """
        self.output_file = output_file
        self.sections = []

    def add_header(self):
        """Add report header."""
        self.sections.append("# Phase 4 Validation Report")
        self.sections.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.sections.append("")
        self.sections.append("---")
        self.sections.append("")

    def add_walk_forward_results(self, wf_results: Dict[str, Any]):
        """
        Add walk-forward optimization results.

        Args:
            wf_results: Results from WalkForwardOptimizer.run_walk_forward_optimization()
        """
        self.sections.append("## Walk-Forward Optimization Results")
        self.sections.append("")

        if not wf_results.get('success'):
            self.sections.append("**ERROR:** Walk-forward optimization failed")
            return

        # Summary stats
        agg = wf_results['aggregated_test_metrics']
        overall = agg['overall']
        risk = agg['risk']

        self.sections.append("### Aggregated Out-of-Sample Performance")
        self.sections.append("")
        self.sections.append(f"- **Total Test Trades:** {overall['total_trades']}")
        self.sections.append(f"- **Win Rate:** {overall['win_rate_pct']:.1f}%")
        self.sections.append(f"- **Average Return:** {overall['avg_return_pct']:+.2f}%")
        self.sections.append(f"- **Median Return:** {overall['median_return_pct']:+.2f}%")
        self.sections.append("")
        self.sections.append("**Risk-Adjusted Metrics:**")
        self.sections.append(f"- **Sharpe Ratio:** {risk['sharpe_ratio']:.3f}")
        self.sections.append(f"- **Sortino Ratio:** {risk['sortino_ratio']:.3f}")
        self.sections.append(f"- **Max Drawdown:** {risk['max_drawdown_pct']:.2f}%")
        self.sections.append(f"- **Calmar Ratio:** {risk['calmar_ratio']:.3f}")
        self.sections.append(f"- **Annualized Return:** {risk['annualized_return_pct']:+.2f}%")
        self.sections.append(f"- **Annualized Volatility:** {risk['annualized_volatility_pct']:.2f}%")
        self.sections.append("")

        # Period breakdown
        self.sections.append("### Period-by-Period Breakdown")
        self.sections.append("")
        self.sections.append("| Period | Test Range | Trades | Win Rate | Avg Return | Sharpe | Max DD |")
        self.sections.append("|--------|------------|--------|----------|------------|--------|--------|")

        for i, result in enumerate(wf_results['periods'], 1):
            test_range = f"{result.period.test_start} to {result.period.test_end}"
            test_overall = result.test_metrics['overall']
            test_risk = result.test_metrics['risk']

            self.sections.append(
                f"| {i} | {test_range} | {test_overall['total_trades']} | "
                f"{test_overall['win_rate_pct']:.1f}% | {test_overall['avg_return_pct']:+.2f}% | "
                f"{test_risk['sharpe_ratio']:.3f} | {test_risk['max_drawdown_pct']:.2f}% |"
            )

        self.sections.append("")
        self.sections.append("---")
        self.sections.append("")

    def add_regime_comparison(self, bull_trades: List, bear_trades: List):
        """
        Add regime-specific performance comparison.

        Args:
            bull_trades: Trades during bull market
            bear_trades: Trades during bear market
        """
        self.sections.append("## Regime-Specific Performance")
        self.sections.append("")

        # Bull market metrics
        self.sections.append("### Bull Market Performance")
        if bull_trades:
            bull_metrics = PerformanceMetrics(bull_trades)
            bull_overall = bull_metrics.calculate_overall_metrics()
            bull_risk = bull_metrics.calculate_risk_adjusted_metrics()

            self.sections.append(f"- **Trades:** {bull_overall['total_trades']}")
            self.sections.append(f"- **Win Rate:** {bull_overall['win_rate_pct']:.1f}%")
            self.sections.append(f"- **Avg Return:** {bull_overall['avg_return_pct']:+.2f}%")
            self.sections.append(f"- **Sharpe Ratio:** {bull_risk['sharpe_ratio']:.3f}")
            self.sections.append(f"- **Max Drawdown:** {bull_risk['max_drawdown_pct']:.2f}%")
        else:
            self.sections.append("No bull market trades")

        self.sections.append("")

        # Bear market metrics
        self.sections.append("### Bear Market Performance")
        if bear_trades:
            bear_metrics = PerformanceMetrics(bear_trades)
            bear_overall = bear_metrics.calculate_overall_metrics()
            bear_risk = bear_metrics.calculate_risk_adjusted_metrics()

            self.sections.append(f"- **Trades:** {bear_overall['total_trades']}")
            self.sections.append(f"- **Win Rate:** {bear_overall['win_rate_pct']:.1f}%")
            self.sections.append(f"- **Avg Return:** {bear_overall['avg_return_pct']:+.2f}%")
            self.sections.append(f"- **Sharpe Ratio:** {bear_risk['sharpe_ratio']:.3f}")
            self.sections.append(f"- **Max Drawdown:** {bear_risk['max_drawdown_pct']:.2f}%")
        else:
            self.sections.append("No bear market trades")

        self.sections.append("")

        # Statistical comparison
        if bull_trades and bear_trades:
            bull_returns = [t.return_pct for t in bull_trades]
            bear_returns = [t.return_pct for t in bear_trades]

            comparison = compare_strategies(bull_returns, bear_returns, "Bull Market", "Bear Market")

            self.sections.append("### Statistical Comparison")
            self.sections.append(f"- **{comparison['conclusion']}**")
            self.sections.append(f"- p-value: {comparison['p_value']:.4f}")

        self.sections.append("")
        self.sections.append("---")
        self.sections.append("")

    def add_statistical_validation(self, trades: List):
        """
        Add statistical significance tests.

        Args:
            trades: List of all trades to validate
        """
        self.sections.append("## Statistical Validation")
        self.sections.append("")

        if not trades:
            self.sections.append("No trades to validate")
            return

        returns = [t.return_pct for t in trades]
        winners = sum(1 for t in trades if t.return_pct > 0)

        # Win rate significance
        win_rate_test = test_win_rate_significance(winners, len(trades), baseline_win_rate=0.50)

        self.sections.append("### Win Rate Significance Test")
        self.sections.append(f"- **Observed Win Rate:** {win_rate_test['win_rate']:.1%}")
        self.sections.append(f"- **Baseline (Random):** {win_rate_test['baseline']:.1%}")
        self.sections.append(f"- **p-value:** {win_rate_test['p_value']:.4f}")
        self.sections.append(f"- **Significant:** {'✅ Yes' if win_rate_test['is_significant'] else '❌ No'}")
        self.sections.append(f"- **Conclusion:** {win_rate_test['conclusion']}")
        self.sections.append("")

        # Mean return significance
        return_test = test_mean_return_significance(returns, baseline_return=0.0)

        self.sections.append("### Mean Return Significance Test")
        self.sections.append(f"- **Observed Mean Return:** {return_test['mean_return']:+.2f}%")
        self.sections.append(f"- **Baseline (Break-even):** {return_test['baseline']:+.2f}%")
        self.sections.append(f"- **p-value:** {return_test['p_value']:.4f}")
        self.sections.append(f"- **Significant:** {'✅ Yes' if return_test['is_significant'] else '❌ No'}")
        self.sections.append(f"- **Conclusion:** {return_test['conclusion']}")
        self.sections.append("")

        # Confidence interval
        mean, lower, upper = calculate_confidence_interval(returns, confidence=0.95)

        self.sections.append("### 95% Confidence Interval for Mean Return")
        self.sections.append(f"- **Mean:** {mean:+.2f}%")
        self.sections.append(f"- **95% CI:** [{lower:+.2f}%, {upper:+.2f}%]")
        self.sections.append("")
        self.sections.append("---")
        self.sections.append("")

    def add_phase_comparison(self, phase3_trades: List, phase4_trades: List):
        """
        Compare Phase 3 vs Phase 4 performance.

        Args:
            phase3_trades: Trades from Phase 3 (static weights)
            phase4_trades: Trades from Phase 4 (adaptive weights)
        """
        self.sections.append("## Phase 3 vs Phase 4 Comparison")
        self.sections.append("")

        if not phase3_trades or not phase4_trades:
            self.sections.append("Insufficient data for comparison")
            return

        # Phase 3 metrics
        p3_metrics = PerformanceMetrics(phase3_trades)
        p3_overall = p3_metrics.calculate_overall_metrics()
        p3_risk = p3_metrics.calculate_risk_adjusted_metrics()

        # Phase 4 metrics
        p4_metrics = PerformanceMetrics(phase4_trades)
        p4_overall = p4_metrics.calculate_overall_metrics()
        p4_risk = p4_metrics.calculate_risk_adjusted_metrics()

        # Comparison table
        self.sections.append("| Metric | Phase 3 (Static) | Phase 4 (Adaptive) | Improvement |")
        self.sections.append("|--------|------------------|--------------------| ------------|")

        metrics_to_compare = [
            ("Total Trades", p3_overall['total_trades'], p4_overall['total_trades'], ""),
            ("Win Rate", f"{p3_overall['win_rate_pct']:.1f}%", f"{p4_overall['win_rate_pct']:.1f}%",
             f"{p4_overall['win_rate_pct'] - p3_overall['win_rate_pct']:+.1f}%"),
            ("Avg Return", f"{p3_overall['avg_return_pct']:+.2f}%", f"{p4_overall['avg_return_pct']:+.2f}%",
             f"{p4_overall['avg_return_pct'] - p3_overall['avg_return_pct']:+.2f}%"),
            ("Sharpe Ratio", f"{p3_risk['sharpe_ratio']:.3f}", f"{p4_risk['sharpe_ratio']:.3f}",
             f"{p4_risk['sharpe_ratio'] - p3_risk['sharpe_ratio']:+.3f}"),
            ("Max Drawdown", f"{p3_risk['max_drawdown_pct']:.2f}%", f"{p4_risk['max_drawdown_pct']:.2f}%",
             f"{p3_risk['max_drawdown_pct'] - p4_risk['max_drawdown_pct']:+.2f}%"),  # Lower is better
        ]

        for metric_name, p3_val, p4_val, improvement in metrics_to_compare:
            self.sections.append(f"| {metric_name} | {p3_val} | {p4_val} | {improvement} |")

        self.sections.append("")

        # Statistical test
        p3_returns = [t.return_pct for t in phase3_trades]
        p4_returns = [t.return_pct for t in phase4_trades]

        comparison = compare_strategies(p3_returns, p4_returns, "Phase 3", "Phase 4")

        self.sections.append("### Statistical Significance")
        self.sections.append(f"- **{comparison['conclusion']}**")
        self.sections.append(f"- p-value: {comparison['p_value']:.4f}")
        self.sections.append("")
        self.sections.append("---")
        self.sections.append("")

    def add_conclusion(self):
        """Add report conclusion."""
        self.sections.append("## Conclusion")
        self.sections.append("")
        self.sections.append("Phase 4 implementation includes:")
        self.sections.append("- ✅ Walk-forward optimization with expanding window")
        self.sections.append("- ✅ Sharpe ratio as optimization objective")
        self.sections.append("- ✅ Regime-based weight adaptation (bull/bear markets)")
        self.sections.append("- ✅ Advanced risk-adjusted metrics (Sharpe, Sortino, Max DD, Calmar)")
        self.sections.append("- ✅ Statistical validation with significance tests")
        self.sections.append("- ✅ Out-of-sample validation across multiple periods")
        self.sections.append("")
        self.sections.append("**Phase 4 Status:** Complete ✅")
        self.sections.append("")

    def generate_report(self):
        """Generate and save the full report."""
        report_content = "\n".join(self.sections)

        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        print(f"\n✅ Phase 4 validation report saved to: {self.output_file}")
        return report_content
