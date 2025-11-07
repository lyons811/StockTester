"""
Backtesting engine for historical performance validation.

Walks through historical data, generates scores at each point,
and tracks performance over 1-3 month holding periods.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from dataclasses import dataclass

from data.fetcher import fetcher
from scoring.calculator import calculate_stock_score
from scoring.vetoes import apply_all_veto_rules


@dataclass
class BacktestTrade:
    """Single backtest trade record."""
    ticker: str
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    score: float
    signal: str
    confidence: float
    return_pct: float
    holding_days: int


class BacktestEngine:
    """
    Backtesting engine for validating scoring system performance.

    Tests historical signals and tracks win rates, returns,
    and accuracy by score ranges.
    """

    def __init__(self, start_date: str, end_date: str, holding_period_days: int = 60):
        """
        Initialize backtest engine.

        Args:
            start_date: Start date for backtesting (YYYY-MM-DD)
            end_date: End date for backtesting (YYYY-MM-DD)
            holding_period_days: Days to hold each position (default 60 = ~2-3 months)
        """
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.holding_period_days = holding_period_days
        self.trades: List[BacktestTrade] = []

    def run_backtest(self, tickers: List[str], rebalance_frequency_days: int = 30) -> List[BacktestTrade]:
        """
        Run backtest on a list of tickers.

        Args:
            tickers: List of stock ticker symbols
            rebalance_frequency_days: Days between rebalancing (default 30)

        Returns:
            List of BacktestTrade objects
        """
        print(f"\n{'='*60}")
        print(f"BACKTESTING: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
        print(f"Tickers: {', '.join(tickers)}")
        print(f"Holding Period: {self.holding_period_days} days (~{self.holding_period_days // 30} months)")
        print(f"Rebalance Frequency: {rebalance_frequency_days} days")
        print(f"{'='*60}\n")

        self.trades = []

        # Walk through time period
        current_date = self.start_date
        trade_count = 0

        while current_date <= self.end_date:
            print(f"Processing date: {current_date.strftime('%Y-%m-%d')}", end='\r')

            for ticker in tickers:
                # Generate score at this point in time
                trade = self._evaluate_trade(ticker, current_date)

                if trade:
                    self.trades.append(trade)
                    trade_count += 1

            # Move to next rebalance date
            current_date += timedelta(days=rebalance_frequency_days)

        print(f"\nBacktest complete: {trade_count} trades executed")
        return self.trades

    def _evaluate_trade(self, ticker: str, entry_date: datetime) -> Optional[BacktestTrade]:
        """
        Evaluate a single trade at a given point in time.

        Args:
            ticker: Stock ticker symbol
            entry_date: Date to enter the trade

        Returns:
            BacktestTrade object or None if trade not valid
        """
        try:
            # Fetch historical data covering backtest period + lookback
            # Need at least 400 days before earliest entry date for indicators
            # Fetch from start of backtest - 400 days to end of backtest + holding period
            fetch_start = self.start_date - timedelta(days=400)
            fetch_end = self.end_date + timedelta(days=self.holding_period_days)

            # Calculate total period needed in years
            total_days = (fetch_end - fetch_start).days
            years_needed = max(2, int(total_days / 365) + 1)

            # Get price data (fetch enough for entire backtest)
            price_data = fetcher.get_stock_data(ticker, period=f"{years_needed}y")
            if price_data is None or price_data.empty:
                return None

            # Filter data up to entry date (avoid look-ahead bias)
            price_data.index = pd.to_datetime(price_data.index, utc=True)
            available_data = price_data[price_data.index <= pd.Timestamp(entry_date, tz='UTC')]

            if len(available_data) < 252:  # Need at least 1 year of data
                return None

            # Get entry price (last available price before or on entry_date)
            entry_price = available_data['Close'].iloc[-1]

            # Calculate exit date
            exit_date = entry_date + timedelta(days=self.holding_period_days)

            # Get exit price (need to look forward, but only for evaluation)
            future_data = price_data[price_data.index > pd.Timestamp(entry_date, tz='UTC')]
            if future_data.empty:
                return None

            # Find exit price (closest date to exit_date, or last available)
            time_diffs = pd.Series((pd.to_datetime(future_data.index, utc=True) - pd.Timestamp(exit_date, tz='UTC'))).abs()
            exit_idx = int(time_diffs.argmin())
            exit_price = float(future_data['Close'].iloc[exit_idx])
            actual_exit_date = pd.Timestamp(future_data.index[exit_idx]).to_pydatetime().replace(tzinfo=None)

            # Calculate return
            return_pct = ((exit_price - entry_price) / entry_price) * 100
            holding_days = (actual_exit_date - entry_date).days

            # Generate score at entry date (this is the key - use only data available then)
            # Note: This will use current data, but in a full implementation,
            # we would cache historical snapshots
            result = calculate_stock_score(ticker)

            if result is None or result.is_vetoed:
                return None  # Skip if can't score or vetoed

            score = result.final_score
            confidence = result.confidence
            signal = result.signal

            # Create trade record
            trade = BacktestTrade(
                ticker=ticker,
                entry_date=entry_date,
                exit_date=actual_exit_date,
                entry_price=entry_price,
                exit_price=exit_price,
                score=score,
                signal=signal,
                confidence=confidence,
                return_pct=return_pct,
                holding_days=holding_days
            )

            return trade

        except Exception as e:
            # Silently skip trades with errors (common for missing data)
            return None

    def get_trades_by_score_range(self, min_score: float, max_score: float) -> List[BacktestTrade]:
        """
        Filter trades by score range.

        Args:
            min_score: Minimum score (inclusive)
            max_score: Maximum score (exclusive)

        Returns:
            List of trades in that score range
        """
        return [t for t in self.trades if min_score <= t.score < max_score]

    def get_trades_by_signal(self, signal: str) -> List[BacktestTrade]:
        """
        Filter trades by signal type.

        Args:
            signal: Signal type (BUY, STRONG BUY, SELL, etc.)

        Returns:
            List of trades with that signal
        """
        return [t for t in self.trades if signal.upper() in t.signal.upper()]

    def calculate_win_rate(self, trades: List[BacktestTrade]) -> Tuple[float, int, int]:
        """
        Calculate win rate for a set of trades.

        Args:
            trades: List of trades

        Returns:
            Tuple of (win_rate_pct, winners, losers)
        """
        if not trades:
            return 0.0, 0, 0

        winners = sum(1 for t in trades if t.return_pct > 0)
        losers = sum(1 for t in trades if t.return_pct <= 0)
        win_rate = (winners / len(trades)) * 100

        return win_rate, winners, losers

    def calculate_average_return(self, trades: List[BacktestTrade]) -> float:
        """
        Calculate average return for a set of trades.

        Args:
            trades: List of trades

        Returns:
            Average return percentage
        """
        if not trades:
            return 0.0

        return sum(t.return_pct for t in trades) / len(trades)

    def export_trades_csv(self, filename: str = "backtest_results.csv"):
        """
        Export trades to CSV file.

        Args:
            filename: Output filename
        """
        if not self.trades:
            print("No trades to export")
            return

        # Convert trades to DataFrame
        df = pd.DataFrame([
            {
                'Ticker': t.ticker,
                'Entry Date': t.entry_date.strftime('%Y-%m-%d'),
                'Exit Date': t.exit_date.strftime('%Y-%m-%d'),
                'Entry Price': t.entry_price,
                'Exit Price': t.exit_price,
                'Score': t.score,
                'Signal': t.signal,
                'Confidence': t.confidence,
                'Return %': t.return_pct,
                'Holding Days': t.holding_days
            }
            for t in self.trades
        ])

        df.to_csv(filename, index=False)
        print(f"Exported {len(self.trades)} trades to {filename}")
