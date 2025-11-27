"""
SEPABacktester - Historical Backtest of Minervini SEPA Strategy
================================================================
Simulates running SuperPerform.py weekly over the past 2 years to measure
how well SEPA-qualified stocks actually performed.

Features:
- Downloads and caches all NASDAQ/NYSE stock data
- Runs historical SEPA analysis for each week
- Tracks forward performance (1mo, 3mo, 6mo returns)
- Parallelized for speed
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import warnings
import json
import time
import sys

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

# Backtest Settings
TEST_MODE = False                    # Set to False for full backtest
BACKTEST_YEARS = 2                  # How far back to test (ignored in test mode)
CHECK_FREQUENCY = 'weekly'          # 'weekly' or 'monthly'

if TEST_MODE:
    # Test mode: 3 months, starting 9 months ago
    START_DATE = datetime.now() - timedelta(days=270)
    END_DATE = datetime.now() - timedelta(days=180)
else:
    START_DATE = datetime.now() - timedelta(days=BACKTEST_YEARS * 365)
    END_DATE = datetime.now() - timedelta(days=180)  # Stop 6 months ago to allow forward tracking

# Stock Universe
MIN_MARKET_CAP = 50_000_000         # $50M minimum market cap
MIN_PRICE = 5.0                     # Minimum stock price
MIN_VOLUME = 100_000                # Minimum average daily volume

# Test mode stock list (small sample for quick testing)
TEST_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "CRM", "NFLX",
    "AVGO", "COST", "ADBE", "PEP", "CSCO", "INTC", "QCOM", "TXN", "AMAT", "MU",
    "LRCX", "KLAC", "SNPS", "CDNS", "MRVL", "ON", "SMCI", "ARM", "PANW", "CRWD",
    "ZS", "FTNT", "DDOG", "NET", "SNOW", "MDB", "TEAM", "WDAY", "NOW", "UBER"
]

# SEPA Criteria (same as SuperPerform.py)
MIN_RS_RATING = 70
MIN_TRADING_DAYS = 240
MIN_ACCELERATION_QUARTERS = 2
MIN_EARNINGS_GROWTH = 15.0
MIN_SALES_GROWTH = 10.0
MAX_ATR_PERCENT = 6.0

# Performance Tracking
TRACK_MONTHS = [1, 3, 6]            # Forward return periods
HIT_TARGETS = [10, 20, 50]          # % gain targets to track

# Parallelization
NUM_WORKERS = max(1, multiprocessing.cpu_count() - 1)

# Cache Settings
CACHE_DIR = Path(__file__).parent / "cache"
PRICE_CACHE_DIR = CACHE_DIR / "price_data"
RESULTS_DIR = Path(__file__).parent / "results"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def ensure_directories():
    """Create cache and results directories if they don't exist"""
    CACHE_DIR.mkdir(exist_ok=True)
    PRICE_CACHE_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)

def get_monday_dates(start_date, end_date):
    """Generate list of Monday dates between start and end"""
    dates = []
    current = start_date

    # Move to first Monday
    while current.weekday() != 0:
        current += timedelta(days=1)

    while current <= end_date:
        dates.append(current)
        current += timedelta(days=7)

    return dates

def safe_div(a, b):
    """Safe division that returns None for invalid operations"""
    if b == 0 or pd.isna(b) or pd.isna(a):
        return None
    return a / b

# ============================================================================
# STOCK UNIVERSE FUNCTIONS
# ============================================================================

def download_stock_universe():
    """
    Download list of all NASDAQ/NYSE stocks from official NASDAQ API
    Returns list of ticker symbols
    """
    print("Downloading stock universe...")

    tickers = set()

    # Headers that mimic a real browser - NASDAQ API requires these
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Origin': 'https://www.nasdaq.com',
        'Referer': 'https://www.nasdaq.com/market-activity/stocks/screener',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
    }

    # Method 1: NASDAQ Official API - Get ALL listed stocks
    try:
        import requests

        print("  Fetching from NASDAQ API...")
        url = 'https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&offset=0'
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()

        # The API returns data in data.table.rows (not data.rows)
        table_data = data.get('data', {}).get('table', {})
        rows = table_data.get('rows', []) if isinstance(table_data, dict) else []

        # Fallback: try data.rows if table.rows is empty
        if len(rows) == 0:
            rows = data.get('data', {}).get('rows', [])

        print(f"  NASDAQ API returned {len(rows)} total rows")

        nasdaq_tickers = []
        skipped_warrants = 0
        skipped_market_cap = 0

        for row in rows:
            symbol = row.get('symbol', '')
            market_cap_str = row.get('marketCap', '')

            # Skip if no symbol
            if not symbol:
                continue

            # Skip warrants, rights, units, preferred shares
            if any(symbol.endswith(suffix) for suffix in ['W', 'R', 'U', 'WS']):
                skipped_warrants += 1
                continue
            if '+' in symbol or '^' in symbol:
                skipped_warrants += 1
                continue
            # Skip 5+ char symbols ending in common warrant/unit patterns
            if len(symbol) >= 5 and symbol[-1] in ['W', 'R', 'U']:
                skipped_warrants += 1
                continue

            # Parse market cap - handle string format like "43763960916.00"
            try:
                # Remove any commas and convert
                if market_cap_str and market_cap_str != '':
                    mc = float(str(market_cap_str).replace(',', ''))
                else:
                    mc = 0

                # Skip very small market caps (< $50M) - likely penny stocks
                if mc > 0 and mc < MIN_MARKET_CAP:
                    skipped_market_cap += 1
                    continue
            except (ValueError, TypeError):
                pass  # Keep if we can't parse - don't skip

            nasdaq_tickers.append(symbol)

        tickers.update(nasdaq_tickers)
        print(f"  Added {len(nasdaq_tickers)} stocks from NASDAQ API")
        print(f"    (Skipped {skipped_warrants} warrants/rights/units, {skipped_market_cap} below ${MIN_MARKET_CAP/1e6:.0f}M market cap)")

    except Exception as e:
        import traceback
        print(f"  Warning: Could not fetch from NASDAQ API: {e}")
        traceback.print_exc()

    # Method 2: Get S&P 500 from GitHub (backup/supplement)
    try:
        from io import StringIO

        url = 'https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv'
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        sp500_df = pd.read_csv(StringIO(response.text))
        sp500_tickers = sp500_df['Symbol'].str.replace('.', '-', regex=False).tolist()
        initial = len(tickers)
        tickers.update(sp500_tickers)
        print(f"  Added {len(tickers) - initial} additional S&P 500 stocks")
    except Exception as e:
        print(f"  Warning: Could not fetch S&P 500 list: {e}")

    # Method 3: NASDAQ-100 (embedded for reliability)
    nasdaq100 = [
        "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "AVGO", "GOOG", "META", "TSLA", "NFLX",
        "ASML", "COST", "PLTR", "AMD", "CSCO", "AZN", "MU", "TMUS", "SHOP", "ISRG",
        "PEP", "AMAT", "APP", "LRCX", "LIN", "AMGN", "QCOM", "INTC", "INTU", "PDD",
        "BKNG", "GILD", "KLAC", "TXN", "ARM", "ADBE", "PANW", "ADI", "CRWD", "HON",
        "CEG", "VRTX", "MELI", "ADP", "SBUX", "CMCSA", "ORLY", "DASH", "CDNS", "REGN",
        "MAR", "SNPS", "MRVL", "CTAS", "MDLZ", "MNST", "ABNB", "CSX", "AEP", "ADSK",
        "IDXX", "FTNT", "WBD", "PYPL", "ROST", "WDAY", "DDOG", "PCAR", "MSTR", "EA",
        "NXPI", "BKR", "XEL", "ROP", "EXC", "FAST", "TTWO", "FANG", "AXON", "CCEP",
        "ZS", "PAYX", "TEAM", "CPRT", "KDP", "CTSH", "GEHC", "VRSK", "KHC", "CSGP",
        "MCHP", "ODFL", "BIIB", "CHTR", "DXCM", "LULU", "ON", "GFS", "CDW", "TTD",
    ]
    initial = len(tickers)
    tickers.update(nasdaq100)
    added = len(tickers) - initial
    if added > 0:
        print(f"  Added {added} additional NASDAQ-100 stocks")

    # Method 4: Read from local CSV files if available
    nasdaq_file = CACHE_DIR / "nasdaq_screener.csv"
    nyse_file = CACHE_DIR / "nyse_screener.csv"

    for f in [nasdaq_file, nyse_file]:
        if f.exists():
            try:
                df = pd.read_csv(f)
                if 'Symbol' in df.columns:
                    file_tickers = df['Symbol'].tolist()
                    initial = len(tickers)
                    tickers.update(file_tickers)
                    added = len(tickers) - initial
                    if added > 0:
                        print(f"  Added {added} tickers from {f.name}")
            except Exception:
                pass

    # Clean up tickers - remove any invalid ones
    clean_tickers = set()
    for t in tickers:
        if not isinstance(t, str):
            continue
        t = t.strip().upper()
        # Valid ticker: 1-5 chars, alphanumeric or hyphen, no special endings
        if len(t) < 1 or len(t) > 6:
            continue
        if not all(c.isalnum() or c == '-' or c == '.' for c in t):
            continue
        # Skip warrants/rights/units again (double check)
        if t.endswith('W') or t.endswith('R') or t.endswith('U'):
            if len(t) > 2:  # Allow single letter tickers like 'A'
                continue
        clean_tickers.add(t.replace('.', '-'))  # Normalize BRK.B to BRK-B

    print(f"  Total unique tickers: {len(clean_tickers)}")
    return sorted(list(clean_tickers))

def get_stock_universe():
    """Get stock universe from cache or download fresh"""
    # In test mode, use small predefined list
    if TEST_MODE:
        print(f"TEST MODE: Using {len(TEST_STOCKS)} test stocks")
        return TEST_STOCKS

    cache_file = CACHE_DIR / "stock_universe.json"

    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)

            cache_age = datetime.now() - datetime.fromisoformat(data['timestamp'])
            if cache_age.days < 7:
                print(f"Using cached stock universe ({len(data['tickers'])} stocks)")
                return data['tickers']
        except Exception:
            pass

    tickers = download_stock_universe()

    # Save to cache
    try:
        with open(cache_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'tickers': tickers
            }, f)
    except Exception as e:
        print(f"Warning: Could not save universe cache: {e}")

    return tickers

# ============================================================================
# DATA FETCHING & CACHING
# ============================================================================

def fetch_price_data(ticker, start_date, end_date):
    """Fetch price data for a single ticker"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_date, end=end_date)

        if df is None or len(df) < 50:
            return None

        return df
    except Exception:
        return None

def get_cached_price_data(ticker):
    """Get price data from cache"""
    cache_file = PRICE_CACHE_DIR / f"{ticker}.csv"

    if cache_file.exists():
        try:
            df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            return df
        except Exception:
            pass

    return None

def save_price_data(ticker, df):
    """Save price data to cache"""
    cache_file = PRICE_CACHE_DIR / f"{ticker}.csv"
    try:
        df.to_csv(cache_file)
    except Exception:
        pass

def fetch_all_price_data(tickers, start_date, end_date, force_refresh=False):
    """
    Fetch and cache price data for all tickers
    Uses batch downloading for efficiency
    """
    print(f"\nFetching price data for {len(tickers)} stocks...")
    print(f"Date range: {start_date.date()} to {end_date.date()}")

    # Check which tickers need downloading
    tickers_to_download = []
    cached_data = {}

    for ticker in tickers:
        if not force_refresh:
            df = get_cached_price_data(ticker)
            if df is not None and len(df) > 100:
                cached_data[ticker] = df
                continue
        tickers_to_download.append(ticker)

    print(f"  Cached: {len(cached_data)} stocks")
    print(f"  To download: {len(tickers_to_download)} stocks")

    if tickers_to_download:
        # Download in batches to avoid overwhelming the API
        batch_size = 100
        downloaded = 0
        failed = 0

        for i in range(0, len(tickers_to_download), batch_size):
            batch = tickers_to_download[i:i + batch_size]
            print(f"  Downloading batch {i//batch_size + 1}/{(len(tickers_to_download)-1)//batch_size + 1}...", end=" ")

            try:
                # Batch download
                data = yf.download(
                    batch,
                    start=start_date,
                    end=end_date,
                    group_by='ticker',
                    progress=False,
                    threads=True
                )

                # Process each ticker in batch
                for ticker in batch:
                    try:
                        if len(batch) == 1:
                            df = data
                        else:
                            df = data[ticker].dropna(how='all')

                        if df is not None and len(df) > 50:
                            save_price_data(ticker, df)
                            cached_data[ticker] = df
                            downloaded += 1
                        else:
                            failed += 1
                    except Exception:
                        failed += 1

                print(f"OK ({downloaded} downloaded, {failed} failed)")

            except Exception as e:
                print(f"Error: {e}")
                failed += len(batch)

            # Rate limiting
            time.sleep(0.5)

    print(f"  Total stocks with data: {len(cached_data)}")
    return cached_data

def fetch_spy_data(start_date, end_date):
    """Fetch SPY benchmark data"""
    cache_file = CACHE_DIR / "spy_benchmark.csv"

    # Check cache
    if cache_file.exists():
        try:
            df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            if len(df) > 100:
                print("Using cached SPY data")
                return df
        except Exception:
            pass

    # Download fresh
    print("Downloading SPY benchmark data...")
    try:
        spy = yf.Ticker("SPY")
        df = spy.history(start=start_date, end=end_date)

        if df is not None and len(df) > 100:
            df.to_csv(cache_file)
            return df
    except Exception as e:
        print(f"Error fetching SPY: {e}")

    return None

# ============================================================================
# HISTORICAL ANALYSIS FUNCTIONS (Adapted from SuperPerform.py)
# ============================================================================

def calculate_ma_slope(ma_values, lookback=20):
    """Calculate if MA is trending up (from SuperPerform.py)"""
    if len(ma_values) < lookback:
        return None
    recent_avg = ma_values[-5:].mean()
    older_avg = ma_values[-lookback:-15].mean()
    return (recent_avg - older_avg) / older_avg * 100

def check_acceleration(values):
    """Check if values show acceleration pattern (from SuperPerform.py)"""
    if len(values) < 4:
        return 0

    recent_4 = values[-4:]
    acceleration_count = 0
    for i in range(1, len(recent_4)):
        if recent_4[i] > recent_4[i-1]:
            acceleration_count += 1

    return acceleration_count

def passes_finviz_filter_historical(df, as_of_date):
    """
    Check if stock passes Finviz-style pre-filter as of a specific date
    Criteria: 30%+ above 52w low, Price > 200MA, 50MA > 200MA
    """
    try:
        # Filter to data up to as_of_date
        df_hist = df[df.index <= as_of_date]

        if len(df_hist) < 252:  # Need 1 year of data
            return False, None

        # Get data for calculations
        current_price = df_hist['Close'].iloc[-1]

        # 52-week high/low (252 trading days)
        df_52w = df_hist.tail(252)
        week_52_high = df_52w['High'].max()
        week_52_low = df_52w['Low'].min()

        # Moving averages
        ma_50 = df_hist['Close'].tail(50).mean()
        ma_200 = df_hist['Close'].tail(200).mean()

        # Check criteria
        pct_above_52w_low = ((current_price - week_52_low) / week_52_low) * 100

        passes = (
            pct_above_52w_low >= 30 and       # 30%+ above 52w low
            current_price > ma_200 and         # Price > 200MA
            ma_50 > ma_200                     # 50MA > 200MA
        )

        if passes:
            return True, {
                'price': current_price,
                'ma_50': ma_50,
                'ma_200': ma_200,
                'week_52_high': week_52_high,
                'week_52_low': week_52_low,
                'pct_above_52w_low': pct_above_52w_low
            }

        return False, None

    except Exception:
        return False, None

def calculate_ibd_rs_historical(ticker, spy_df, price_df, as_of_date):
    """
    Calculate IBD-style RS rating as of a specific historical date
    Adapted from SuperPerform.py
    """
    try:
        # Filter to data up to as_of_date
        df = price_df[price_df.index <= as_of_date]
        spy = spy_df[spy_df.index <= as_of_date]

        if len(df) < MIN_TRADING_DAYS or len(spy) < MIN_TRADING_DAYS:
            return None, "Insufficient data"

        current_price = df['Close'].iloc[-1]

        periods = {
            '3mo': min(63, len(df)),
            '6mo': min(126, len(df)),
            '9mo': min(189, len(df)),
            '12mo': min(252, len(df), len(spy))
        }

        weights = {'3mo': 0.4, '6mo': 0.2, '9mo': 0.2, '12mo': 0.2}

        rs_score = 0
        for period_name, days in periods.items():
            if len(df) >= days and len(spy) >= days and days > 0:
                past_price = df['Close'].iloc[-days]
                stock_return = ((current_price - past_price) / past_price) * 100

                spy_past = spy['Close'].iloc[-days]
                spy_current = spy['Close'].iloc[-1]
                spy_return = ((spy_current - spy_past) / spy_past) * 100

                rs_score += weights[period_name] * (stock_return - spy_return)

        return {'rs_score': rs_score}, None

    except Exception as e:
        return None, str(e)

def analyze_stage_historical(ticker, price_df, rs_rating, as_of_date):
    """
    Analyze stock stage using Minervini's criteria as of a historical date
    Adapted from SuperPerform.py
    """
    try:
        df = price_df[price_df.index <= as_of_date].copy()

        if len(df) < 200:
            return None, "Insufficient data"

        # Calculate moving averages
        df['MA_50'] = df['Close'].rolling(window=50).mean()
        df['MA_150'] = df['Close'].rolling(window=150).mean()
        df['MA_200'] = df['Close'].rolling(window=200).mean()

        current_price = df['Close'].iloc[-1]
        ma_50 = df['MA_50'].iloc[-1]
        ma_150 = df['MA_150'].iloc[-1]
        ma_200 = df['MA_200'].iloc[-1]

        # 52-week metrics
        df_52w = df.tail(252)
        week_52_high = df_52w['High'].max()
        week_52_low = df_52w['Low'].min()

        ma_200_slope = calculate_ma_slope(df['MA_200'].dropna())

        # Stage 2 criteria
        criteria = {
            'price_above_150_200': current_price > ma_150 and current_price > ma_200,
            'ma150_above_200': ma_150 > ma_200,
            'ma200_trending_up': ma_200_slope is not None and ma_200_slope > 0,
            'ma50_above_150_200': ma_50 > ma_150 and ma_50 > ma_200,
            'price_above_50': current_price > ma_50,
            'price_30pct_above_low': ((current_price - week_52_low) / week_52_low * 100) >= 30,
            'price_within_25pct_high': ((week_52_high - current_price) / week_52_high * 100) <= 25,
            'rs_above_70': rs_rating >= MIN_RS_RATING
        }

        passes_all = all(criteria.values())

        pct_above_52w_low = ((current_price - week_52_low) / week_52_low * 100)
        pct_from_52w_high = ((week_52_high - current_price) / week_52_high * 100)

        return {
            'stage': 2 if passes_all else 1,
            'passes_all_criteria': passes_all,
            'criteria': criteria,
            'current_price': current_price,
            'ma_50': ma_50,
            'ma_150': ma_150,
            'ma_200': ma_200,
            'week_52_high': week_52_high,
            'week_52_low': week_52_low,
            'pct_above_52w_low': pct_above_52w_low,
            'pct_from_52w_high': pct_from_52w_high,
            'rs_rating': rs_rating
        }, None

    except Exception as e:
        return None, str(e)

def calculate_atr_percent_historical(price_df, as_of_date):
    """Calculate ATR as percentage of price as of a historical date"""
    try:
        df = price_df[price_df.index <= as_of_date].tail(90).copy()

        if len(df) < 20:
            return None

        df['H-L'] = df['High'] - df['Low']
        df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
        df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
        df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)

        atr = df['TR'].rolling(window=14).mean().iloc[-1]
        current_price = df['Close'].iloc[-1]

        return (atr / current_price) * 100

    except Exception:
        return None

def analyze_fundamentals_historical(ticker, as_of_date):
    """
    Analyze fundamentals with point-in-time awareness
    Only considers quarters that would have been reported by as_of_date
    """
    try:
        stock = yf.Ticker(ticker)

        quarterly_income = stock.quarterly_income_stmt

        if quarterly_income is None or len(quarterly_income.columns) < 4:
            return None, "Insufficient quarterly data"

        # Filter to quarters reported before as_of_date
        # Rule: Quarter data available ~45 days after quarter end
        valid_quarters = []
        for col in quarterly_income.columns:
            quarter_end = pd.to_datetime(col)
            report_date = quarter_end + timedelta(days=45)
            if report_date <= as_of_date:
                valid_quarters.append(col)

        if len(valid_quarters) < 4:
            return None, "Insufficient historical quarters"

        # Use only valid quarters
        quarterly_income = quarterly_income[valid_quarters]

        # Get earnings data
        earnings_fields = ['Net Income', 'NetIncome', 'Net Income Common Stockholders']
        eps_data = None
        for field in earnings_fields:
            if field in quarterly_income.index:
                eps_data = quarterly_income.loc[field]
                break

        # Get revenue data
        revenue_fields = ['Total Revenue', 'TotalRevenue', 'Revenue']
        revenue_data = None
        for field in revenue_fields:
            if field in quarterly_income.index:
                revenue_data = quarterly_income.loc[field]
                break

        results = {
            'has_earnings_data': eps_data is not None and len(eps_data) >= 4,
            'has_revenue_data': revenue_data is not None and len(revenue_data) >= 4,
            'earnings_acceleration_quarters': 0,
            'revenue_acceleration_quarters': 0,
            'recent_earnings_growth': None,
            'recent_revenue_growth': None,
        }

        # Check earnings
        if results['has_earnings_data']:
            eps_sorted = eps_data.sort_index(ascending=False)

            if len(eps_sorted) >= 5:
                recent = eps_sorted.iloc[0]
                year_ago = eps_sorted.iloc[4]
                if year_ago != 0 and not pd.isna(year_ago):
                    results['recent_earnings_growth'] = ((recent - year_ago) / abs(year_ago)) * 100

            eps_values = eps_sorted.head(8).values
            results['earnings_acceleration_quarters'] = check_acceleration(eps_values[::-1])

        # Check revenue
        if results['has_revenue_data']:
            rev_sorted = revenue_data.sort_index(ascending=False)

            if len(rev_sorted) >= 5:
                recent = rev_sorted.iloc[0]
                year_ago = rev_sorted.iloc[4]
                if year_ago != 0 and not pd.isna(year_ago):
                    results['recent_revenue_growth'] = ((recent - year_ago) / year_ago) * 100

            rev_values = rev_sorted.head(8).values
            results['revenue_acceleration_quarters'] = check_acceleration(rev_values[::-1])

        # Determine pass/fail
        passes = True
        failed = []

        if results['earnings_acceleration_quarters'] < MIN_ACCELERATION_QUARTERS:
            passes = False
            failed.append(f"Earnings accel ({results['earnings_acceleration_quarters']}/{MIN_ACCELERATION_QUARTERS})")

        if results['revenue_acceleration_quarters'] < MIN_ACCELERATION_QUARTERS:
            passes = False
            failed.append(f"Revenue accel ({results['revenue_acceleration_quarters']}/{MIN_ACCELERATION_QUARTERS})")

        if results['recent_earnings_growth'] is not None and results['recent_earnings_growth'] < MIN_EARNINGS_GROWTH:
            passes = False
            failed.append(f"Earnings growth ({results['recent_earnings_growth']:.1f}%)")

        if results['recent_revenue_growth'] is not None and results['recent_revenue_growth'] < MIN_SALES_GROWTH:
            passes = False
            failed.append(f"Revenue growth ({results['recent_revenue_growth']:.1f}%)")

        results['passes_step2'] = passes
        results['failed_criteria'] = failed

        return results, None

    except Exception as e:
        return None, str(e)

# ============================================================================
# PERFORMANCE TRACKING
# ============================================================================

def track_performance(ticker, entry_date, entry_price, price_df):
    """
    Track forward performance from entry date
    Returns dict with returns and hit metrics
    """
    try:
        # Get data after entry date
        df_forward = price_df[price_df.index > entry_date]

        if len(df_forward) < 20:
            return None

        results = {
            'entry_date': entry_date,
            'entry_price': entry_price,
        }

        # Calculate returns at different periods
        for months in TRACK_MONTHS:
            target_date = entry_date + timedelta(days=months * 30)
            df_period = df_forward[df_forward.index <= target_date]

            if len(df_period) > 0:
                end_price = df_period['Close'].iloc[-1]
                results[f'return_{months}mo'] = ((end_price - entry_price) / entry_price) * 100
            else:
                results[f'return_{months}mo'] = None

        # Calculate max gain in 6 months
        df_6mo = df_forward[df_forward.index <= entry_date + timedelta(days=180)]
        if len(df_6mo) > 0:
            max_price = df_6mo['High'].max()
            results['max_gain_6mo'] = ((max_price - entry_price) / entry_price) * 100

            # Max drawdown before max gain
            max_idx = df_6mo['High'].idxmax()
            df_before_max = df_6mo[df_6mo.index <= max_idx]
            if len(df_before_max) > 0:
                min_price = df_before_max['Low'].min()
                results['max_drawdown'] = ((min_price - entry_price) / entry_price) * 100
            else:
                results['max_drawdown'] = 0
        else:
            results['max_gain_6mo'] = None
            results['max_drawdown'] = None

        # Days to hit targets
        for target in HIT_TARGETS:
            target_price = entry_price * (1 + target / 100)
            hit_df = df_6mo[df_6mo['High'] >= target_price]

            if len(hit_df) > 0:
                hit_date = hit_df.index[0]
                results[f'days_to_{target}pct'] = (hit_date - entry_date).days
            else:
                results[f'days_to_{target}pct'] = None

        return results

    except Exception:
        return None

# ============================================================================
# MAIN BACKTEST FUNCTIONS
# ============================================================================

def process_single_week(args):
    """
    Process a single week of backtesting
    Designed to run in parallel
    """
    week_date, tickers, price_cache, spy_df = args

    qualified_stocks = []
    debug_stats = {'finviz': 0, 'rs_valid': 0, 'rs_high': 0, 'stage2': 0, 'fundamentals': 0}

    # Step 1: Pre-filter with Finviz-like criteria
    pre_filtered = []
    for ticker in tickers:
        if ticker not in price_cache:
            continue

        passes, data = passes_finviz_filter_historical(price_cache[ticker], week_date)
        if passes:
            pre_filtered.append((ticker, data))

    debug_stats['finviz'] = len(pre_filtered)

    if not pre_filtered:
        return week_date, qualified_stocks, debug_stats

    # Step 2: Calculate RS ratings
    rs_scores = {}
    for ticker, _ in pre_filtered:
        rs_data, _ = calculate_ibd_rs_historical(ticker, spy_df, price_cache[ticker], week_date)
        if rs_data:
            rs_scores[ticker] = rs_data['rs_score']

    debug_stats['rs_valid'] = len(rs_scores)

    if not rs_scores:
        return week_date, qualified_stocks, debug_stats

    # Calculate RS ratings (percentile rank)
    scores = list(rs_scores.values())
    for ticker in rs_scores:
        percentile = sum(1 for s in scores if s <= rs_scores[ticker]) / len(scores) * 99
        rs_scores[ticker] = int(percentile)

    # Filter by RS >= 70
    high_rs = {t: r for t, r in rs_scores.items() if r >= MIN_RS_RATING}
    debug_stats['rs_high'] = len(high_rs)

    if not high_rs:
        return week_date, qualified_stocks, debug_stats

    # Step 3: Stage 2 analysis
    stage2_stocks = []
    for ticker, rs_rating in high_rs.items():
        analysis, _ = analyze_stage_historical(ticker, price_cache[ticker], rs_rating, week_date)
        if analysis and analysis['passes_all_criteria']:
            stage2_stocks.append((ticker, rs_rating, analysis))

    debug_stats['stage2'] = len(stage2_stocks)

    if not stage2_stocks:
        return week_date, qualified_stocks, debug_stats

    # Step 4: Fundamental screening
    for ticker, rs_rating, stage_data in stage2_stocks:
        fundamentals, error = analyze_fundamentals_historical(ticker, week_date)

        if fundamentals and fundamentals['passes_step2']:
            debug_stats['fundamentals'] += 1
            # Track forward performance
            perf = track_performance(
                ticker,
                week_date,
                stage_data['current_price'],
                price_cache[ticker]
            )

            qualified_stocks.append({
                'date': week_date,
                'ticker': ticker,
                'entry_price': stage_data['current_price'],
                'rs_rating': rs_rating,
                'pct_from_high': stage_data['pct_from_52w_high'],
                'earnings_accel': fundamentals['earnings_acceleration_quarters'],
                'revenue_accel': fundamentals['revenue_acceleration_quarters'],
                'earnings_growth': fundamentals['recent_earnings_growth'],
                'revenue_growth': fundamentals['recent_revenue_growth'],
                **({k: v for k, v in perf.items() if k not in ['entry_date', 'entry_price']} if perf else {})
            })

    return week_date, qualified_stocks, debug_stats

def run_backtest():
    """Main backtest execution"""
    ensure_directories()

    print("=" * 80)
    print("SEPA BACKTESTER - Historical Performance Analysis")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  Backtest period: {START_DATE.date()} to {END_DATE.date()}")
    print(f"  Check frequency: {CHECK_FREQUENCY}")
    print(f"  Parallel workers: {NUM_WORKERS}")

    # Step 1: Get stock universe
    tickers = get_stock_universe()
    print(f"\nStock universe: {len(tickers)} stocks")

    # Step 2: Fetch SPY data
    data_start = START_DATE - timedelta(days=365)  # Extra year for lookback
    data_end = datetime.now()

    spy_df = fetch_spy_data(data_start, data_end)
    if spy_df is None:
        print("ERROR: Could not fetch SPY data")
        return

    # Step 3: Fetch all price data
    price_cache = fetch_all_price_data(tickers, data_start, data_end)

    if not price_cache:
        print("ERROR: No price data available")
        return

    # Step 4: Generate check dates
    check_dates = get_monday_dates(START_DATE, END_DATE)
    print(f"\nBacktest dates: {len(check_dates)} weeks")

    # Step 5: Run backtest
    print(f"\nRunning backtest with {NUM_WORKERS} parallel workers...")
    print("-" * 80)

    all_results = []

    # Prepare arguments for parallel processing
    args_list = [
        (date, list(price_cache.keys()), price_cache, spy_df)
        for date in check_dates
    ]

    # Process in parallel
    completed = 0
    total_stats = {'finviz': 0, 'rs_valid': 0, 'rs_high': 0, 'stage2': 0, 'fundamentals': 0}

    with ProcessPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = {executor.submit(process_single_week, args): args[0] for args in args_list}

        for future in as_completed(futures):
            completed += 1
            week_date, results, debug_stats = future.result()

            # Aggregate debug stats
            for key in total_stats:
                total_stats[key] += debug_stats.get(key, 0)

            if results:
                all_results.extend(results)
                print(f"  [{completed}/{len(check_dates)}] {week_date.date()}: {len(results)} SEPA qualified")
            else:
                if completed % 10 == 0:
                    print(f"  [{completed}/{len(check_dates)}] Progress...")

    # Print debug summary
    print("\n" + "-" * 80)
    print("FILTERING SUMMARY (across all weeks):")
    print(f"  Passed Finviz filter (30%+ above low, >200MA, 50MA>200MA): {total_stats['finviz']:,}")
    print(f"  Had valid RS scores: {total_stats['rs_valid']:,}")
    print(f"  RS >= 70: {total_stats['rs_high']:,}")
    print(f"  Passed Stage 2 (all 8 criteria): {total_stats['stage2']:,}")
    print(f"  Passed Fundamentals (SEPA qualified): {total_stats['fundamentals']:,}")

    print("-" * 80)

    # Step 6: Generate report
    generate_report(all_results)

def generate_report(results):
    """Generate backtest report and save results"""
    if not results:
        print("\nNo SEPA-qualified stocks found in backtest period.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(results)

    # Save detailed results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = RESULTS_DIR / f"backtest_results_{timestamp}.csv"
    df.to_csv(results_file, index=False)
    print(f"\nDetailed results saved to: {results_file}")

    # Generate summary
    print("\n" + "=" * 80)
    print("SEPA BACKTESTER RESULTS")
    print("=" * 80)

    print(f"\nTotal qualification events: {len(df)}")
    print(f"Unique stocks: {df['ticker'].nunique()}")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")

    # Win rates
    print("\nWIN RATES (Positive Returns):")
    for months in TRACK_MONTHS:
        col = f'return_{months}mo'
        if col in df.columns:
            valid = df[col].dropna()
            if len(valid) > 0:
                win_rate = (valid > 0).sum() / len(valid) * 100
                print(f"  {months}-month: {win_rate:.1f}% ({(valid > 0).sum()}/{len(valid)})")

    # Hit rates
    print("\nHIT RATES (Target Achieved within 6 months):")
    for target in HIT_TARGETS:
        col = f'days_to_{target}pct'
        if col in df.columns:
            valid = df[col].dropna()
            hit_rate = len(valid) / len(df) * 100
            if len(valid) > 0:
                avg_days = valid.mean()
                print(f"  +{target}%: {hit_rate:.1f}% hit (avg {avg_days:.0f} days)")
            else:
                print(f"  +{target}%: {hit_rate:.1f}% hit")

    # Average returns
    print("\nAVERAGE RETURNS:")
    for months in TRACK_MONTHS:
        col = f'return_{months}mo'
        if col in df.columns:
            valid = df[col].dropna()
            if len(valid) > 0:
                avg = valid.mean()
                median = valid.median()
                print(f"  {months}-month: {avg:+.1f}% avg, {median:+.1f}% median")

    if 'max_gain_6mo' in df.columns:
        valid = df['max_gain_6mo'].dropna()
        if len(valid) > 0:
            print(f"  Max gain (6mo): {valid.mean():+.1f}% avg")

    # Best performers
    print("\nTOP 10 BEST PERFORMERS (by max gain):")
    if 'max_gain_6mo' in df.columns:
        top = df.nlargest(10, 'max_gain_6mo')[['date', 'ticker', 'entry_price', 'max_gain_6mo']]
        for _, row in top.iterrows():
            print(f"  {row['ticker']:6} +{row['max_gain_6mo']:.0f}% (qualified {row['date'].date() if hasattr(row['date'], 'date') else row['date']})")

    # Worst performers
    print("\nBOTTOM 10 WORST PERFORMERS (by 3-month return):")
    if 'return_3mo' in df.columns:
        valid = df[df['return_3mo'].notna()]
        if len(valid) > 0:
            bottom = valid.nsmallest(10, 'return_3mo')[['date', 'ticker', 'entry_price', 'return_3mo']]
            for _, row in bottom.iterrows():
                print(f"  {row['ticker']:6} {row['return_3mo']:+.0f}% (qualified {row['date'].date() if hasattr(row['date'], 'date') else row['date']})")

    # Save summary
    summary_file = RESULTS_DIR / f"backtest_summary_{timestamp}.txt"
    with open(summary_file, 'w') as f:
        f.write(f"SEPA Backtester Summary\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Total qualifications: {len(df)}\n")
        f.write(f"Unique stocks: {df['ticker'].nunique()}\n")

        for months in TRACK_MONTHS:
            col = f'return_{months}mo'
            if col in df.columns:
                valid = df[col].dropna()
                if len(valid) > 0:
                    f.write(f"{months}mo win rate: {(valid > 0).sum() / len(valid) * 100:.1f}%\n")
                    f.write(f"{months}mo avg return: {valid.mean():.1f}%\n")

    print(f"\nSummary saved to: {summary_file}")
    print("=" * 80)

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    run_backtest()
