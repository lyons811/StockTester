"""
Data fetcher using yfinance API with caching support.
Retrieves stock data, fundamental data, and market indices.
"""

import yfinance as yf
import pandas as pd
from typing import Dict, Any, Optional, Tuple, cast

from .cache_manager import cache
from utils.config import config


class DataFetcher:
    """Fetches stock data from yfinance with caching."""

    def __init__(self, use_cache: bool = True):
        """
        Initialize data fetcher.

        Args:
            use_cache: Whether to use caching
        """
        self.use_cache = use_cache and config.get('cache.enabled', True)
        self.cache_duration = config.get('cache.cache_duration_hours', 24)
        self.price_cache_duration = config.get('cache.price_cache_duration_hours', 1)

    def get_stock_data(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """
        Get historical price data for a stock.

        Args:
            ticker: Stock ticker symbol
            period: Time period (e.g., '1y', '2y', '6mo')

        Returns:
            DataFrame with OHLCV data or None if error
        """
        cache_key = f"{ticker}_price_{period}"

        # Check cache
        if self.use_cache:
            cached_data = cache.get(cache_key, max_age_hours=self.price_cache_duration)
            if cached_data is not None:
                return pd.DataFrame(cached_data)

        try:
            # Fetch from yfinance
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)

            if df.empty:
                return None

            # Cache the data (convert index to string for JSON serialization)
            if self.use_cache:
                df_copy = df.copy()
                df_copy.index = df_copy.index.astype(str)
                cache.set(cache_key, cast(Dict[str, Any], df_copy.to_dict()))

            return df

        except Exception as e:
            print(f"Error fetching price data for {ticker}: {e}")
            return None

    def get_stock_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get stock information and fundamentals.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with stock info or None if error
        """
        cache_key = f"{ticker}_info"

        # Check cache
        if self.use_cache:
            cached_data = cache.get(cache_key, max_age_hours=self.cache_duration)
            if cached_data is not None:
                return cached_data

        try:
            # Fetch from yfinance
            stock = yf.Ticker(ticker)
            info = stock.info

            if not info:
                return None

            # Cache the data
            if self.use_cache:
                cache.set(cache_key, info)

            return info

        except Exception as e:
            print(f"Error fetching info for {ticker}: {e}")
            return None

    def get_financials(self, ticker: str) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """
        Get financial statements for a stock.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Tuple of (income_statement, balance_sheet, cash_flow) DataFrames
        """
        cache_key = f"{ticker}_financials"

        # Check cache
        if self.use_cache:
            cached_data = cache.get(cache_key, max_age_hours=self.cache_duration)
            if cached_data is not None:
                income = pd.DataFrame(cached_data.get('income_statement'))
                balance = pd.DataFrame(cached_data.get('balance_sheet'))
                cashflow = pd.DataFrame(cached_data.get('cash_flow'))
                return income, balance, cashflow

        try:
            # Fetch from yfinance
            stock = yf.Ticker(ticker)
            income_statement = stock.financials
            balance_sheet = stock.balance_sheet
            cash_flow = stock.cashflow

            # Cache the data
            if self.use_cache:
                cache.set(cache_key, {
                    'income_statement': income_statement.to_dict() if not income_statement.empty else {},
                    'balance_sheet': balance_sheet.to_dict() if not balance_sheet.empty else {},
                    'cash_flow': cash_flow.to_dict() if not cash_flow.empty else {}
                })

            return income_statement, balance_sheet, cash_flow

        except Exception as e:
            print(f"Error fetching financials for {ticker}: {e}")
            return None, None, None

    def get_market_data(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """
        Get market index data (S&P 500, VIX, sector ETFs).

        Args:
            ticker: Index/ETF ticker symbol
            period: Time period

        Returns:
            DataFrame with historical data or None if error
        """
        cache_key = f"{ticker}_market_{period}"

        # Check cache
        if self.use_cache:
            cached_data = cache.get(cache_key, max_age_hours=self.price_cache_duration)
            if cached_data is not None:
                return pd.DataFrame(cached_data)

        try:
            # Fetch from yfinance
            index = yf.Ticker(ticker)
            df = index.history(period=period)

            if df.empty:
                return None

            # Cache the data (convert index to string for JSON serialization)
            if self.use_cache:
                df_copy = df.copy()
                df_copy.index = df_copy.index.astype(str)
                cache.set(cache_key, cast(Dict[str, Any], df_copy.to_dict()))

            return df

        except Exception as e:
            print(f"Error fetching market data for {ticker}: {e}")
            return None

    def get_current_price(self, ticker: str) -> Optional[float]:
        """
        Get current price for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Current price or None if error
        """
        info = self.get_stock_info(ticker)
        if info:
            # Try different price fields
            price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            return price
        return None

    def get_sector(self, ticker: str) -> Optional[str]:
        """
        Get sector for a stock.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Sector name or None if not found
        """
        info = self.get_stock_info(ticker)
        if info:
            return info.get('sector')
        return None

    def get_sector_etf(self, ticker: str) -> str:
        """
        Get appropriate sector ETF for a stock.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Sector ETF ticker (defaults to SPY if sector not found)
        """
        sector = self.get_sector(ticker)
        if sector:
            return config.get_sector_etf(sector)
        return config.get_sector_etf('default')

    def get_beta(self, ticker: str) -> float:
        """
        Get beta for a stock.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Beta value (defaults to 1.0 if not found)
        """
        info = self.get_stock_info(ticker)
        if info and 'beta' in info:
            beta = info.get('beta')
            if beta and not pd.isna(beta):
                return float(beta)
        return 1.0  # Default beta if not available

    def get_market_cap(self, ticker: str) -> Optional[float]:
        """
        Get market capitalization.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Market cap in dollars or None
        """
        info = self.get_stock_info(ticker)
        if info:
            return info.get('marketCap')
        return None

    def get_average_volume(self, ticker: str) -> Optional[float]:
        """
        Get average daily volume.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Average volume or None
        """
        info = self.get_stock_info(ticker)
        if info:
            return info.get('averageVolume')
        return None

    def get_earnings_history(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Get earnings history (last 4 quarters actual vs estimate).

        Args:
            ticker: Stock ticker symbol

        Returns:
            DataFrame with earnings history or None if error
        """
        cache_key = f"{ticker}_earnings_history"

        # Check cache
        if self.use_cache:
            cached_data = cache.get(cache_key, max_age_hours=self.cache_duration)
            if cached_data is not None:
                return pd.DataFrame(cached_data)

        try:
            # Fetch from yfinance
            stock = yf.Ticker(ticker)
            earnings_hist = stock.earnings_history

            if earnings_hist is None or earnings_hist.empty:
                return None

            # Cache the data (convert index to string for JSON serialization)
            if self.use_cache:
                df_copy = earnings_hist.copy()
                if hasattr(df_copy.index, 'astype'):
                    df_copy.index = df_copy.index.astype(str)
                cache.set(cache_key, cast(Dict[str, Any], df_copy.to_dict()))

            return earnings_hist

        except Exception as e:
            print(f"Error fetching earnings history for {ticker}: {e}")
            return None

    def get_quarterly_financials(self, ticker: str) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """
        Get quarterly financial statements.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Tuple of (quarterly_income, quarterly_balance, quarterly_cashflow) DataFrames
        """
        cache_key = f"{ticker}_quarterly_financials"

        # Check cache
        if self.use_cache:
            cached_data = cache.get(cache_key, max_age_hours=self.cache_duration)
            if cached_data is not None:
                income = pd.DataFrame(cached_data.get('quarterly_income'))
                balance = pd.DataFrame(cached_data.get('quarterly_balance'))
                cashflow = pd.DataFrame(cached_data.get('quarterly_cashflow'))
                return income, balance, cashflow

        try:
            # Fetch from yfinance
            stock = yf.Ticker(ticker)
            quarterly_income = stock.quarterly_income_stmt
            quarterly_balance = stock.quarterly_balance_sheet
            quarterly_cashflow = stock.quarterly_cashflow

            # Cache the data (convert indices/columns to string for JSON serialization)
            if self.use_cache:
                def safe_to_dict(df):
                    if df.empty:
                        return {}
                    df_copy = df.copy()
                    if hasattr(df_copy.index, 'astype'):
                        df_copy.index = df_copy.index.astype(str)
                    if hasattr(df_copy.columns, 'astype'):
                        df_copy.columns = df_copy.columns.astype(str)
                    return df_copy.to_dict()

                cache.set(cache_key, {
                    'quarterly_income': safe_to_dict(quarterly_income),
                    'quarterly_balance': safe_to_dict(quarterly_balance),
                    'quarterly_cashflow': safe_to_dict(quarterly_cashflow)
                })

            return quarterly_income, quarterly_balance, quarterly_cashflow

        except Exception as e:
            print(f"Error fetching quarterly financials for {ticker}: {e}")
            return None, None, None

    def get_analyst_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get analyst data (recommendations, price targets, upgrades/downgrades).

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with analyst data or None if error
        """
        cache_key = f"{ticker}_analyst_data"

        # Check cache
        if self.use_cache:
            cached_data = cache.get(cache_key, max_age_hours=self.cache_duration)
            if cached_data is not None:
                return cached_data

        try:
            # Fetch from yfinance
            stock = yf.Ticker(ticker)

            analyst_data = {}

            # Price targets
            try:
                analyst_data['price_targets'] = stock.analyst_price_targets
            except:
                analyst_data['price_targets'] = None

            # Helper to safely convert DataFrame to dict
            def safe_df_to_dict(df):
                if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                    return None
                df_copy = df.copy()
                if hasattr(df_copy.index, 'astype'):
                    df_copy.index = df_copy.index.astype(str)
                if hasattr(df_copy.columns, 'astype'):
                    df_copy.columns = df_copy.columns.astype(str)
                return df_copy.to_dict()

            # Recommendations
            try:
                recommendations = stock.recommendations
                analyst_data['recommendations'] = safe_df_to_dict(recommendations)
            except:
                analyst_data['recommendations'] = None

            # Upgrades/Downgrades
            try:
                upgrades = stock.upgrades_downgrades
                analyst_data['upgrades_downgrades'] = safe_df_to_dict(upgrades)
            except:
                analyst_data['upgrades_downgrades'] = None

            # Cache the data
            if self.use_cache:
                cache.set(cache_key, analyst_data)

            return analyst_data

        except Exception as e:
            print(f"Error fetching analyst data for {ticker}: {e}")
            return None

    def get_short_interest(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get short interest data for a stock.

        Uses yfinance's shortPercentOfFloat field. Falls back to attempting
        to scrape FinViz if yfinance data is unavailable.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with short interest data or None if unavailable
        """
        cache_key = f"{ticker}_short_interest"

        # Check cache
        if self.use_cache:
            cached_data = cache.get(cache_key, max_age_hours=self.cache_duration)
            if cached_data is not None:
                return cached_data

        try:
            # Fetch from yfinance
            stock = yf.Ticker(ticker)
            info = stock.info

            short_data = {}

            # Get short percent of float
            if 'shortPercentOfFloat' in info and info['shortPercentOfFloat'] is not None:
                # yfinance returns as decimal (0.15 = 15%)
                short_data['short_percent_float'] = info['shortPercentOfFloat'] * 100
            else:
                # Try alternative field names
                if 'sharesShort' in info and 'floatShares' in info:
                    shares_short = info.get('sharesShort', 0)
                    float_shares = info.get('floatShares', 1)
                    if float_shares > 0:
                        short_data['short_percent_float'] = (shares_short / float_shares) * 100

            # Calculate days to cover if volume data available
            if 'sharesShort' in info and 'averageVolume' in info:
                shares_short = info.get('sharesShort', 0)
                avg_volume = info.get('averageVolume', 1)
                if avg_volume > 0:
                    short_data['days_to_cover'] = shares_short / avg_volume

            # If no data found, return None
            if not short_data:
                return None

            # Cache the data
            if self.use_cache:
                cache.set(cache_key, short_data)

            return short_data

        except Exception as e:
            print(f"Error fetching short interest for {ticker}: {e}")
            return None

    def get_options_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get basic options data including put/call ratios and volume metrics.

        Uses yfinance's options chains to calculate put/call ratios and
        detect unusual activity.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with options metrics or None if unavailable
        """
        cache_key = f"{ticker}_options_data"

        # Check cache
        if self.use_cache:
            cached_data = cache.get(cache_key, max_age_hours=self.cache_duration)
            if cached_data is not None:
                return cached_data

        try:
            # Fetch from yfinance
            stock = yf.Ticker(ticker)

            # Get available expiration dates
            expirations = stock.options

            if not expirations or len(expirations) == 0:
                return None

            # Use the nearest expiration (first in list)
            nearest_exp = expirations[0]

            # Get option chain for nearest expiration
            opt_chain = stock.option_chain(nearest_exp)

            if opt_chain is None:
                return None

            calls = opt_chain.calls
            puts = opt_chain.puts

            if calls.empty or puts.empty:
                return None

            # Calculate put/call volume ratio
            call_volume = calls['volume'].sum() if 'volume' in calls.columns else 0
            put_volume = puts['volume'].sum() if 'volume' in puts.columns else 0

            if call_volume == 0:
                put_call_ratio = 2.0  # Assume high P/C if no call volume
            else:
                put_call_ratio = put_volume / call_volume

            # Calculate put/call open interest ratio
            call_oi = calls['openInterest'].sum() if 'openInterest' in calls.columns else 0
            put_oi = puts['openInterest'].sum() if 'openInterest' in puts.columns else 0

            # Detect unusual activity (volume > 2x open interest)
            unusual_activity = False
            if call_oi > 0 and call_volume > (2 * call_oi):
                unusual_activity = True
            if put_oi > 0 and put_volume > (2 * put_oi):
                unusual_activity = True

            options_data = {
                'put_call_ratio': put_call_ratio,
                'call_volume': call_volume,
                'put_volume': put_volume,
                'call_open_interest': call_oi,
                'put_open_interest': put_oi,
                'unusual_activity': unusual_activity,
                'expiration': nearest_exp
            }

            # Cache the data
            if self.use_cache:
                cache.set(cache_key, options_data)

            return options_data

        except Exception as e:
            print(f"Error fetching options data for {ticker}: {e}")
            return None


# Global fetcher instance
fetcher = DataFetcher()
