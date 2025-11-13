"""
Market regime classifier for Phase 4.

Classifies historical periods as Bull or Bear market based on
S&P 500's position relative to its 200-day moving average.
"""

from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
import pandas as pd
import yfinance as yf


class RegimeClassifier:
    """
    Classify market regimes using S&P 500 vs 200-day MA.

    Bull Market: S&P 500 price > 200-day MA
    Bear Market: S&P 500 price < 200-day MA

    This is a professional standard used by institutional investors
    to adapt portfolio strategies to market conditions.
    """

    def __init__(self, lookback_period: str = "10y", quiet: bool = False):
        """
        Initialize regime classifier.

        Args:
            lookback_period: How far back to fetch S&P 500 data (default: 10y)
            quiet: If True, suppress informational messages (default: False)
        """
        self.lookback_period = lookback_period
        self.sp500_data = None
        self.regime_df = None
        self._cache_valid = False
        self.quiet = quiet

    def fetch_sp500_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None):
        """
        Fetch S&P 500 historical data.

        Args:
            start_date: Start date (optional, overrides lookback_period)
            end_date: End date (optional, defaults to today)
        """
        if not self.quiet:
            print(f"Fetching S&P 500 data for regime classification...")

        if start_date and end_date:
            # Use specific date range
            self.sp500_data = yf.download("^GSPC", start=start_date, end=end_date, progress=False, auto_adjust=True)
        else:
            # Use lookback period
            self.sp500_data = yf.download("^GSPC", period=self.lookback_period, progress=False, auto_adjust=True)

        if self.sp500_data.empty:
            raise ValueError("Failed to fetch S&P 500 data")

        # Flatten MultiIndex columns if present (happens with single ticker downloads)
        if isinstance(self.sp500_data.columns, pd.MultiIndex):
            self.sp500_data.columns = self.sp500_data.columns.get_level_values(0)

        if not self.quiet:
            print(f"Fetched {len(self.sp500_data)} days of S&P 500 data")
        self._cache_valid = False

    def calculate_regimes(self, ma_period: int = 200) -> pd.DataFrame:
        """
        Calculate bull/bear regimes for all historical dates.

        Args:
            ma_period: Moving average period in days (default: 200)

        Returns:
            DataFrame with columns: Date, Close, MA_200, Regime (Bull/Bear)
        """
        if self.sp500_data is None or self.sp500_data.empty:
            self.fetch_sp500_data()

        assert self.sp500_data is not None, "S&P 500 data should be loaded"

        # Calculate 200-day MA
        df = self.sp500_data[['Close']].copy()
        df['MA_200'] = df['Close'].rolling(window=ma_period).mean()

        # Classify regime using vectorized comparison (more efficient than apply)
        df['Regime'] = 'Bear'  # Default
        df.loc[df['Close'] > df['MA_200'], 'Regime'] = 'Bull'

        # Add numeric regime code for calculations
        df['Regime_Code'] = df['Regime'].map({'Bull': 1, 'Bear': -1})

        # Drop rows without MA (first 200 days)
        df = df.dropna()

        self.regime_df = df
        self._cache_valid = True

        # Print summary statistics
        if not self.quiet:
            bull_days = (df['Regime'] == 'Bull').sum()
            bear_days = (df['Regime'] == 'Bear').sum()
            total_days = len(df)

            print(f"\nRegime Classification Summary:")
            print(f"  Total Days: {total_days}")
            print(f"  Bull Market Days: {bull_days} ({bull_days/total_days*100:.1f}%)")
            print(f"  Bear Market Days: {bear_days} ({bear_days/total_days*100:.1f}%)")

        return df

    def get_regime_for_date(self, date: datetime) -> str:
        """
        Get market regime for a specific date.

        Args:
            date: Date to check

        Returns:
            "Bull" or "Bear"
        """
        if not self._cache_valid or self.regime_df is None:
            self.calculate_regimes()

        assert self.regime_df is not None, "Regime data should be calculated"

        # Ensure date is in datetime format
        if isinstance(date, str):
            date = pd.to_datetime(date)

        # Find closest date in regime data
        try:
            regime = self.regime_df.loc[date, 'Regime']
        except KeyError:
            # Date not in index, find nearest
            idx = self.regime_df.index.get_indexer([date], method='nearest')[0]
            regime = self.regime_df.iloc[idx]['Regime']

        return regime

    def get_regime_periods(self, start_date: str, end_date: str) -> List[Tuple[str, str, str]]:
        """
        Get contiguous regime periods within date range.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of (regime, period_start, period_end) tuples
        """
        if not self._cache_valid or self.regime_df is None:
            self.calculate_regimes()

        assert self.regime_df is not None, "Regime data should be calculated"

        # Filter to date range
        mask = (self.regime_df.index >= start_date) & (self.regime_df.index <= end_date)
        df = self.regime_df[mask].copy()

        # Find regime changes
        df['Regime_Change'] = df['Regime'] != df['Regime'].shift(1)

        periods = []
        current_regime = None
        period_start = None

        for date, row in df.iterrows():
            if row['Regime_Change'] or current_regime is None:
                # Regime changed, close previous period
                if current_regime is not None:
                    periods.append((current_regime, period_start.strftime('%Y-%m-%d'), date.strftime('%Y-%m-%d')))
                # Start new period
                current_regime = row['Regime']
                period_start = date

        # Close final period
        if current_regime is not None:
            periods.append((current_regime, period_start.strftime('%Y-%m-%d'), df.index[-1].strftime('%Y-%m-%d')))

        return periods

    def filter_trades_by_regime(self, trades: List, regime: str) -> List:
        """
        Filter trades that occurred during a specific regime.

        Args:
            trades: List of BacktestTrade objects
            regime: "Bull" or "Bear"

        Returns:
            Filtered list of trades
        """
        if not self._cache_valid or self.regime_df is None:
            self.calculate_regimes()

        filtered_trades = []

        for trade in trades:
            trade_regime = self.get_regime_for_date(trade.entry_date)
            if trade_regime == regime:
                filtered_trades.append(trade)

        return filtered_trades

    def get_regime_statistics(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Get statistical breakdown of regimes in a period.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Dictionary with regime statistics
        """
        if not self._cache_valid or self.regime_df is None:
            self.calculate_regimes()

        assert self.regime_df is not None, "Regime data should be calculated"

        # Filter to date range
        mask = (self.regime_df.index >= start_date) & (self.regime_df.index <= end_date)
        df = self.regime_df[mask].copy()

        if df.empty:
            return {
                'total_days': 0,
                'bull_days': 0,
                'bear_days': 0,
                'bull_pct': 0.0,
                'bear_pct': 0.0,
                'regime_changes': 0
            }

        total_days = len(df)
        bull_days = (df['Regime'] == 'Bull').sum()
        bear_days = (df['Regime'] == 'Bear').sum()

        # Count regime changes
        regime_changes = (df['Regime'] != df['Regime'].shift(1)).sum()

        return {
            'total_days': total_days,
            'bull_days': bull_days,
            'bear_days': bear_days,
            'bull_pct': (bull_days / total_days * 100) if total_days > 0 else 0.0,
            'bear_pct': (bear_days / total_days * 100) if total_days > 0 else 0.0,
            'regime_changes': regime_changes,
            'avg_regime_duration_days': total_days / regime_changes if regime_changes > 0 else total_days
        }

    def print_regime_summary(self, start_date: str, end_date: str):
        """
        Print regime summary for a date range.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        """
        stats = self.get_regime_statistics(start_date, end_date)

        print(f"\nMarket Regime Summary ({start_date} to {end_date}):")
        print("="*60)
        print(f"  Total Days: {stats['total_days']}")
        print(f"  Bull Market Days: {stats['bull_days']} ({stats['bull_pct']:.1f}%)")
        print(f"  Bear Market Days: {stats['bear_days']} ({stats['bear_pct']:.1f}%)")
        print(f"  Regime Changes: {stats['regime_changes']}")
        print(f"  Avg Regime Duration: {stats['avg_regime_duration_days']:.0f} days")
        print("="*60)


# Convenience functions for quick access

def get_current_regime(quiet: bool = False) -> str:
    """
    Get current market regime (Bull or Bear).

    Args:
        quiet: If True, suppress output messages

    Returns:
        "Bull" or "Bear"
    """
    classifier = RegimeClassifier(lookback_period="1y", quiet=quiet)
    classifier.calculate_regimes()
    return classifier.get_regime_for_date(datetime.now())


def classify_historical_period(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Get regime classification for a historical period.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with daily regime classifications
    """
    classifier = RegimeClassifier()
    classifier.fetch_sp500_data(start_date=start_date, end_date=end_date)
    return classifier.calculate_regimes()
