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


# Global fetcher instance
fetcher = DataFetcher()
