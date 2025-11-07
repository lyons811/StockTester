"""
Performance metrics calculator for backtesting results.

Analyzes win rates, returns, and accuracy by score ranges,
signals, and categories.
"""

from typing import List, Dict, Any
from dataclasses import dataclass

from .engine import BacktestTrade


@dataclass
class ScoreRangeMetrics:
    """Metrics for a specific score range."""
    score_range: str
    min_score: float
    max_score: float
    total_trades: int
    winners: int
    losers: int
    win_rate_pct: float
    avg_return_pct: float
    avg_winner_return_pct: float
    avg_loser_return_pct: float
    median_return_pct: float


class PerformanceMetrics:
    """
    Calculate and analyze backtest performance metrics.

    Provides detailed analysis of win rates, returns, and
    accuracy across different score ranges and signals.
    """

    def __init__(self, trades: List[BacktestTrade]):
        """
        Initialize metrics calculator.

        Args:
            trades: List of backtest trades
        """
        self.trades = trades

    def calculate_overall_metrics(self) -> Dict[str, Any]:
        """
        Calculate overall performance metrics.

        Returns:
            Dictionary with overall metrics
        """
        if not self.trades:
            return {
                'total_trades': 0,
                'winners': 0,
                'losers': 0,
                'win_rate_pct': 0.0,
                'avg_return_pct': 0.0,
                'median_return_pct': 0.0,
                'avg_winner_return_pct': 0.0,
                'avg_loser_return_pct': 0.0,
                'best_trade_pct': 0.0,
                'worst_trade_pct': 0.0,
                'avg_holding_days': 0
            }

        winners = [t for t in self.trades if t.return_pct > 0]
        losers = [t for t in self.trades if t.return_pct <= 0]
        returns = [t.return_pct for t in self.trades]

        return {
            'total_trades': len(self.trades),
            'winners': len(winners),
            'losers': len(losers),
            'win_rate_pct': (len(winners) / len(self.trades)) * 100,
            'avg_return_pct': sum(returns) / len(returns),
            'median_return_pct': sorted(returns)[len(returns) // 2],
            'avg_winner_return_pct': sum(t.return_pct for t in winners) / len(winners) if winners else 0.0,
            'avg_loser_return_pct': sum(t.return_pct for t in losers) / len(losers) if losers else 0.0,
            'best_trade_pct': max(returns),
            'worst_trade_pct': min(returns),
            'avg_holding_days': sum(t.holding_days for t in self.trades) / len(self.trades)
        }

    def calculate_score_range_metrics(self) -> List[ScoreRangeMetrics]:
        """
        Calculate metrics for each score range.

        Returns:
            List of ScoreRangeMetrics objects
        """
        score_ranges = [
            ("Strong Sell", -10.0, -6.0),
            ("Sell/Avoid", -6.0, -3.0),
            ("Neutral", -3.0, 3.0),
            ("Buy", 3.0, 6.0),
            ("Strong Buy", 6.0, 10.1)
        ]

        metrics_list = []

        for range_name, min_score, max_score in score_ranges:
            # Filter trades in this range
            range_trades = [t for t in self.trades if min_score <= t.score < max_score]

            if not range_trades:
                metrics_list.append(ScoreRangeMetrics(
                    score_range=range_name,
                    min_score=min_score,
                    max_score=max_score,
                    total_trades=0,
                    winners=0,
                    losers=0,
                    win_rate_pct=0.0,
                    avg_return_pct=0.0,
                    avg_winner_return_pct=0.0,
                    avg_loser_return_pct=0.0,
                    median_return_pct=0.0
                ))
                continue

            winners = [t for t in range_trades if t.return_pct > 0]
            losers = [t for t in range_trades if t.return_pct <= 0]
            returns = [t.return_pct for t in range_trades]

            metrics_list.append(ScoreRangeMetrics(
                score_range=range_name,
                min_score=min_score,
                max_score=max_score,
                total_trades=len(range_trades),
                winners=len(winners),
                losers=len(losers),
                win_rate_pct=(len(winners) / len(range_trades)) * 100,
                avg_return_pct=sum(returns) / len(returns),
                avg_winner_return_pct=sum(t.return_pct for t in winners) / len(winners) if winners else 0.0,
                avg_loser_return_pct=sum(t.return_pct for t in losers) / len(losers) if losers else 0.0,
                median_return_pct=sorted(returns)[len(returns) // 2]
            ))

        return metrics_list

    def calculate_signal_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate metrics by signal type.

        Returns:
            Dictionary mapping signal types to their metrics
        """
        signals = ["STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL"]
        signal_metrics = {}

        for signal in signals:
            signal_trades = [t for t in self.trades if signal in t.signal.upper()]

            if not signal_trades:
                signal_metrics[signal] = {
                    'total_trades': 0,
                    'win_rate_pct': 0.0,
                    'avg_return_pct': 0.0
                }
                continue

            winners = [t for t in signal_trades if t.return_pct > 0]
            returns = [t.return_pct for t in signal_trades]

            signal_metrics[signal] = {
                'total_trades': len(signal_trades),
                'winners': len(winners),
                'losers': len(signal_trades) - len(winners),
                'win_rate_pct': (len(winners) / len(signal_trades)) * 100,
                'avg_return_pct': sum(returns) / len(returns),
                'median_return_pct': sorted(returns)[len(returns) // 2]
            }

        return signal_metrics

    def calculate_ticker_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate metrics by ticker.

        Returns:
            Dictionary mapping tickers to their metrics
        """
        tickers = set(t.ticker for t in self.trades)
        ticker_metrics = {}

        for ticker in tickers:
            ticker_trades = [t for t in self.trades if t.ticker == ticker]

            if not ticker_trades:
                continue

            winners = [t for t in ticker_trades if t.return_pct > 0]
            returns = [t.return_pct for t in ticker_trades]

            ticker_metrics[ticker] = {
                'total_trades': len(ticker_trades),
                'winners': len(winners),
                'losers': len(ticker_trades) - len(winners),
                'win_rate_pct': (len(winners) / len(ticker_trades)) * 100,
                'avg_return_pct': sum(returns) / len(returns),
                'avg_score': sum(t.score for t in ticker_trades) / len(ticker_trades)
            }

        return ticker_metrics

    def print_summary_report(self):
        """Print comprehensive summary report."""
        print("\n" + "="*70)
        print("BACKTESTING PERFORMANCE REPORT")
        print("="*70)

        # Overall metrics
        overall = self.calculate_overall_metrics()

        if overall['total_trades'] == 0:
            print("\nNo trades were executed during the backtest period.")
            print("This may indicate:")
            print("  - All stocks were vetoed")
            print("  - Insufficient historical data")
            print("  - Date range issues")
            return

        print("\nOVERALL PERFORMANCE:")
        print(f"  Total Trades:        {overall['total_trades']}")
        print(f"  Winners:             {overall['winners']} ({overall['win_rate_pct']:.1f}%)")
        print(f"  Losers:              {overall['losers']}")
        print(f"  Avg Return:          {overall['avg_return_pct']:+.2f}%")
        print(f"  Median Return:       {overall['median_return_pct']:+.2f}%")
        print(f"  Avg Winner Return:   {overall['avg_winner_return_pct']:+.2f}%")
        print(f"  Avg Loser Return:    {overall['avg_loser_return_pct']:+.2f}%")
        print(f"  Best Trade:          {overall['best_trade_pct']:+.2f}%")
        print(f"  Worst Trade:         {overall['worst_trade_pct']:+.2f}%")
        print(f"  Avg Holding Period:  {overall['avg_holding_days']:.0f} days")

        # Score range metrics
        print("\n" + "-"*70)
        print("PERFORMANCE BY SCORE RANGE:")
        print("-"*70)
        print(f"{'Score Range':<15} {'Trades':<8} {'Win Rate':<10} {'Avg Return':<12} {'Median Return'}")
        print("-"*70)

        score_metrics = self.calculate_score_range_metrics()
        for m in score_metrics:
            if m.total_trades == 0:
                print(f"{m.score_range:<15} {m.total_trades:<8} {'N/A':<10} {'N/A':<12} {'N/A'}")
            else:
                print(f"{m.score_range:<15} {m.total_trades:<8} {m.win_rate_pct:>6.1f}%    "
                      f"{m.avg_return_pct:>+6.2f}%      {m.median_return_pct:>+6.2f}%")

        # Signal metrics
        print("\n" + "-"*70)
        print("PERFORMANCE BY SIGNAL:")
        print("-"*70)
        print(f"{'Signal':<15} {'Trades':<8} {'Win Rate':<10} {'Avg Return':<12} {'Median Return'}")
        print("-"*70)

        signal_metrics = self.calculate_signal_metrics()
        for signal, metrics in signal_metrics.items():
            if metrics['total_trades'] == 0:
                print(f"{signal:<15} {metrics['total_trades']:<8} {'N/A':<10} {'N/A':<12} {'N/A'}")
            else:
                print(f"{signal:<15} {metrics['total_trades']:<8} {metrics['win_rate_pct']:>6.1f}%    "
                      f"{metrics['avg_return_pct']:>+6.2f}%      {metrics['median_return_pct']:>+6.2f}%")

        # Ticker metrics
        print("\n" + "-"*70)
        print("PERFORMANCE BY TICKER:")
        print("-"*70)
        print(f"{'Ticker':<10} {'Trades':<8} {'Win Rate':<10} {'Avg Return':<12} {'Avg Score'}")
        print("-"*70)

        ticker_metrics = self.calculate_ticker_metrics()
        for ticker in sorted(ticker_metrics.keys()):
            metrics = ticker_metrics[ticker]
            print(f"{ticker:<10} {metrics['total_trades']:<8} {metrics['win_rate_pct']:>6.1f}%    "
                  f"{metrics['avg_return_pct']:>+6.2f}%      {metrics['avg_score']:>+5.2f}")

        print("\n" + "="*70 + "\n")
