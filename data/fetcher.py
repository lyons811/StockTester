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

    def get_sp500_constituents(self) -> Optional[pd.DataFrame]:
        """
        Get S&P 500 constituent list from Wikipedia (Phase 5a).

        Fetches and caches the current S&P 500 ticker list with company names and sectors.
        Used for relative strength percentile ranking.

        Returns:
            DataFrame with columns: ticker, company, sector
            None if fetch fails
        """
        import requests
        from io import StringIO

        cache_key = "sp500_constituents"

        # Check cache (24-hour cache)
        if self.use_cache:
            cached_data = cache.get(cache_key, max_age_hours=24)
            if cached_data is not None:
                try:
                    df = pd.DataFrame.from_dict(cached_data)
                    # Verify it has the expected columns
                    if all(col in df.columns for col in ['ticker', 'company', 'sector']):
                        return df
                    # If columns are wrong, clear cache and fetch fresh
                except:
                    pass  # If cache is corrupted, fetch fresh

        try:
            # Fetch from Wikipedia
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Parse HTML table
            tables = pd.read_html(StringIO(response.text))

            # Find the table with S&P 500 stocks (usually has 'Symbol' and 'Security' columns)
            # Wikipedia sometimes changes table order, so search for the right one
            sp500_table = None
            for table in tables:
                cols = [str(c).lower() for c in table.columns]
                if ('symbol' in cols or any('symbol' in c for c in cols)) and len(table) > 400:
                    sp500_table = table
                    break

            if sp500_table is None:
                raise ValueError(f"Could not find S&P 500 table. Found {len(tables)} tables.")

            # Debug: Check what columns we actually have
            actual_columns = sp500_table.columns.tolist()

            # Try to find the right column names (Wikipedia might change format)
            # Be more specific to avoid duplicate mappings
            column_mapping = {}
            for col in actual_columns:
                col_str = str(col)
                col_lower = col_str.lower()
                # Only map if we haven't already mapped this target
                if 'ticker' not in column_mapping.values() and col_str in ['Symbol', 'Ticker']:
                    column_mapping[col] = 'ticker'
                elif 'company' not in column_mapping.values() and col_str in ['Security', 'Company', 'Name']:
                    column_mapping[col] = 'company'
                elif 'sector' not in column_mapping.values() and col_str in ['GICS Sector', 'Sector']:
                    column_mapping[col] = 'sector'

            # If we couldn't find all required columns, raise error with helpful message
            if len(column_mapping) < 3:
                raise ValueError(f"Could not map all required columns. Found: {actual_columns}")

            # Rename columns for consistency
            sp500_table = sp500_table.rename(columns=column_mapping)

            # Select relevant columns
            sp500_df = sp500_table[['ticker', 'company', 'sector']].copy()

            # Cache the data (use 'list' orient for better reconstruction)
            if self.use_cache:
                cache.set(cache_key, cast(Dict[str, Any], sp500_df.to_dict(orient='list')))

            return sp500_df

        except Exception as e:
            print(f"Error fetching S&P 500 constituents: {e}")
            return None

    def get_sp500_returns_bulk(self, period: str = '6mo', lookback_days: int = 120) -> Optional[Dict[str, float]]:
        """
        Get 6-month returns for ALL S&P 500 stocks in a single bulk download (Phase 5a optimization).

        This method dramatically improves performance by fetching all 500 stocks at once
        instead of making 500 individual API calls. Results are cached for 24 hours.

        Args:
            period: Time period for return calculation (default: '6mo')
            lookback_days: Minimum days required for valid return calculation (default: 120)

        Returns:
            Dictionary mapping ticker -> 6-month return percentage
            Returns None if bulk fetch fails
        """
        cache_key = f"sp500_{period}_returns"

        # Check cache (24-hour cache - same as constituents)
        if self.use_cache:
            cached_data = cache.get(cache_key, max_age_hours=24)
            if cached_data is not None:
                return cached_data

        try:
            # Get S&P 500 constituent list
            constituents = self.get_sp500_constituents()
            if constituents is None or constituents.empty:
                return None

            tickers = constituents['ticker'].tolist()

            # Bulk download all S&P 500 stocks at once (MASSIVE performance improvement)
            # This replaces 500 individual API calls with 1 bulk call
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # Suppress yfinance warnings
                bulk_data = yf.download(
                    tickers,
                    period=period,
                    group_by='ticker',
                    threads=True,  # Use threading for faster download
                    progress=False  # Suppress progress bar
                )

            # Calculate 6-month returns for each stock
            returns_dict = {}

            # Type check: ensure bulk_data is valid
            if bulk_data is None or bulk_data.empty:
                return None

            for ticker in tickers:
                try:
                    # Handle multi-ticker vs single-ticker DataFrame structure
                    if len(tickers) == 1:
                        ticker_data = bulk_data
                    else:
                        ticker_data = bulk_data[ticker] if ticker in bulk_data.columns.get_level_values(0) else None

                    if ticker_data is None or ticker_data.empty:
                        continue

                    # Get Close prices
                    if isinstance(ticker_data, pd.DataFrame) and 'Close' in ticker_data.columns:
                        close_prices = ticker_data['Close'].dropna()
                    elif isinstance(ticker_data, pd.Series):
                        close_prices = ticker_data.dropna()
                    else:
                        continue

                    # Require minimum data points
                    if len(close_prices) < lookback_days:
                        continue

                    # Calculate return
                    start_price = close_prices.iloc[0]
                    end_price = close_prices.iloc[-1]

                    if start_price > 0:
                        return_pct = ((end_price - start_price) / start_price) * 100
                        returns_dict[ticker] = return_pct

                except Exception:
                    # Skip individual stocks that fail
                    continue

            # Cache the results
            if self.use_cache and returns_dict:
                cache.set(cache_key, returns_dict)

            return returns_dict

        except Exception as e:
            print(f"Error in bulk S&P 500 returns fetch: {e}")
            return None


# Global fetcher instance
fetcher = DataFetcher()
