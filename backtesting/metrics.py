"""
Performance metrics calculator for backtesting results.

Analyzes win rates, returns, and accuracy by score ranges,
signals, and categories. Includes advanced risk-adjusted metrics
for Phase 4 (Sharpe ratio, Sortino ratio, max drawdown, etc.).
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import numpy as np
from datetime import datetime

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

    def calculate_risk_adjusted_metrics(self, risk_free_rate: float = 0.025) -> Dict[str, Any]:
        """
        Calculate advanced risk-adjusted performance metrics (Phase 4).

        Includes Sharpe ratio, Sortino ratio, maximum drawdown, Calmar ratio,
        annualized returns, and volatility.

        Args:
            risk_free_rate: Annual risk-free rate (default: 2.5% = T-bill average 2018-2025)

        Returns:
            Dictionary with risk-adjusted metrics
        """
        if not self.trades:
            return {
                'sharpe_ratio': 0.0,
                'sortino_ratio': 0.0,
                'max_drawdown_pct': 0.0,
                'calmar_ratio': 0.0,
                'annualized_return_pct': 0.0,
                'annualized_volatility_pct': 0.0,
                'total_return_pct': 0.0,
                'years': 0.0
            }

        # Get returns and calculate basic stats
        returns = np.array([t.return_pct for t in self.trades])

        # Calculate time period
        sorted_trades = sorted(self.trades, key=lambda t: t.entry_date)
        start_date = sorted_trades[0].entry_date
        end_date = sorted_trades[-1].exit_date
        years = (end_date - start_date).days / 365.25

        # Average return per trade
        avg_return_per_trade = np.mean(returns)

        # Estimate annualized return (simple approximation)
        # Assumes avg holding period and rebalancing frequency
        avg_holding_days = np.mean([t.holding_days for t in self.trades])
        trades_per_year = 365.25 / avg_holding_days if avg_holding_days > 0 else 1
        annualized_return = avg_return_per_trade * trades_per_year

        # Volatility (standard deviation of returns)
        volatility_per_trade = np.std(returns, ddof=1)
        annualized_volatility = volatility_per_trade * np.sqrt(trades_per_year)

        # Sharpe Ratio = (Return - RiskFree) / Volatility
        excess_return = annualized_return - (risk_free_rate * 100)
        sharpe_ratio = excess_return / annualized_volatility if annualized_volatility > 0 else 0.0

        # Sortino Ratio (only penalize downside volatility)
        negative_returns = returns[returns < 0]
        downside_volatility_per_trade = np.std(negative_returns, ddof=1) if len(negative_returns) > 1 else 0.0
        downside_volatility_annual = downside_volatility_per_trade * np.sqrt(trades_per_year)
        sortino_ratio = excess_return / downside_volatility_annual if downside_volatility_annual > 0 else 0.0

        # Maximum Drawdown (peak-to-trough decline)
        cumulative_returns = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = running_max - cumulative_returns
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0.0

        # Calmar Ratio = Annualized Return / Max Drawdown
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0.0

        # Total cumulative return
        total_return = np.sum(returns)

        return {
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'max_drawdown_pct': max_drawdown,
            'calmar_ratio': calmar_ratio,
            'annualized_return_pct': annualized_return,
            'annualized_volatility_pct': annualized_volatility,
            'total_return_pct': total_return,
            'years': years,
            'avg_holding_days': avg_holding_days,
            'estimated_trades_per_year': trades_per_year
        }

    def calculate_win_loss_streaks(self) -> Dict[str, Any]:
        """
        Calculate longest winning and losing streaks.

        Returns:
            Dictionary with streak statistics
        """
        if not self.trades:
            return {
                'longest_win_streak': 0,
                'longest_loss_streak': 0,
                'current_streak': 0,
                'current_streak_type': 'None'
            }

        # Sort trades by date
        sorted_trades = sorted(self.trades, key=lambda t: t.entry_date)

        max_win_streak = 0
        max_loss_streak = 0
        current_streak = 0
        current_type = None

        for trade in sorted_trades:
            is_winner = trade.return_pct > 0

            if current_type is None:
                current_type = 'win' if is_winner else 'loss'
                current_streak = 1
            elif (current_type == 'win' and is_winner) or (current_type == 'loss' and not is_winner):
                current_streak += 1
            else:
                # Streak broken
                if current_type == 'win':
                    max_win_streak = max(max_win_streak, current_streak)
                else:
                    max_loss_streak = max(max_loss_streak, current_streak)

                current_type = 'win' if is_winner else 'loss'
                current_streak = 1

        # Check final streak
        if current_type == 'win':
            max_win_streak = max(max_win_streak, current_streak)
        elif current_type == 'loss':
            max_loss_streak = max(max_loss_streak, current_streak)

        return {
            'longest_win_streak': max_win_streak,
            'longest_loss_streak': max_loss_streak,
            'current_streak': current_streak,
            'current_streak_type': current_type if current_type else 'None'
        }

    def calculate_annual_breakdown(self) -> Dict[int, Dict[str, Any]]:
        """
        Calculate metrics broken down by year for consistency analysis.

        Returns:
            Dictionary mapping year to metrics
        """
        if not self.trades:
            return {}

        # Group trades by year
        trades_by_year = {}
        for trade in self.trades:
            year = trade.entry_date.year
            if year not in trades_by_year:
                trades_by_year[year] = []
            trades_by_year[year].append(trade)

        # Calculate metrics for each year
        annual_metrics = {}
        for year, year_trades in sorted(trades_by_year.items()):
            returns = [t.return_pct for t in year_trades]
            winners = [t for t in year_trades if t.return_pct > 0]

            annual_metrics[year] = {
                'total_trades': len(year_trades),
                'winners': len(winners),
                'win_rate_pct': (len(winners) / len(year_trades)) * 100 if year_trades else 0,
                'avg_return_pct': np.mean(returns) if returns else 0,
                'median_return_pct': np.median(returns) if returns else 0,
                'total_return_pct': np.sum(returns) if returns else 0,
                'volatility_pct': np.std(returns, ddof=1) if len(returns) > 1 else 0
            }

        return annual_metrics

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

        # Risk-adjusted metrics (Phase 4)
        risk_metrics = self.calculate_risk_adjusted_metrics()
        print("\n" + "-"*70)
        print("RISK-ADJUSTED METRICS (Phase 4):")
        print("-"*70)
        print(f"  Sharpe Ratio:        {risk_metrics['sharpe_ratio']:.3f}")
        print(f"  Sortino Ratio:       {risk_metrics['sortino_ratio']:.3f}")
        print(f"  Max Drawdown:        {risk_metrics['max_drawdown_pct']:.2f}%")
        print(f"  Calmar Ratio:        {risk_metrics['calmar_ratio']:.3f}")
        print(f"  Annualized Return:   {risk_metrics['annualized_return_pct']:+.2f}%")
        print(f"  Annualized Volatility: {risk_metrics['annualized_volatility_pct']:.2f}%")
        print(f"  Total Return:        {risk_metrics['total_return_pct']:+.2f}%")
        print(f"  Period (Years):      {risk_metrics['years']:.2f}")

        # Win/loss streaks
        streaks = self.calculate_win_loss_streaks()
        print("\n" + "-"*70)
        print("STREAK ANALYSIS:")
        print("-"*70)
        print(f"  Longest Win Streak:  {streaks['longest_win_streak']} trades")
        print(f"  Longest Loss Streak: {streaks['longest_loss_streak']} trades")
        print(f"  Current Streak:      {streaks['current_streak']} {streaks['current_streak_type']}")

        # Annual breakdown
        annual_metrics = self.calculate_annual_breakdown()
        if annual_metrics:
            print("\n" + "-"*70)
            print("ANNUAL PERFORMANCE BREAKDOWN:")
            print("-"*70)
            print(f"{'Year':<8} {'Trades':<8} {'Win Rate':<10} {'Avg Return':<12} {'Total Return':<13} {'Volatility'}")
            print("-"*70)
            for year in sorted(annual_metrics.keys()):
                m = annual_metrics[year]
                print(f"{year:<8} {m['total_trades']:<8} {m['win_rate_pct']:>6.1f}%    "
                      f"{m['avg_return_pct']:>+6.2f}%      {m['total_return_pct']:>+7.2f}%      {m['volatility_pct']:>6.2f}%")

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
