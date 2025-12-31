"""
SuperPerform - Complete Minervini SEPA Analysis
Step 1: IBD RS Rating + Stage 2 Trend Template
Step 2: Fundamental Screening (Earnings/Sales Acceleration, Margins, Volatility)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import json
import os
import re
from pathlib import Path
import time

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_WEB_SCRAPING = True
except ImportError:
    HAS_WEB_SCRAPING = False
    print("WARNING: requests or beautifulsoup4 not installed. Install with: pip install requests beautifulsoup4")

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION - Edit this section to customize
# ============================================================================

# Add your stock tickers here (from your screener results)
STOCK_LIST = [
    "ACNT", "ACRE", "ALMS", "ALTO", "AMGN", "ANVS", "ARVN", "BAER", "BYSI", "CAAP",
    "COKE", "CURE", "CVRX", "DAWN", "DNLI", "DRIO", "DWTX", "EXOZ", "GANX", "GPOR",
    "JAMF", "JBIO", "KLRS", "KMT", "KODK", "KZR", "LBRT", "LLYX", "MEC", "MRSN",
    "MTC", "NEXA", "OBIO", "OMCL", "OMER", "PASG", "PERI", "PODC", "PROF", "PRTA",
    "PUMP", "REGN", "RVLV", "SIM", "SSP", "TALK", "TBBB", "TC", "TDC", "THR",
    "TRAW", "TS", "TWLO", "VFC", "WAT", "XPEL"
]

# Step 1 Thresholds (RS & Stage) - OPTIMIZED FROM BACKTEST DATA
MIN_RS_RATING = 80          # Raised from 70 (backtest shows 80+ has cleaner signals)
MAX_RS_RATING = 94          # RS 95+ often overextended (56.7% win vs 67% for 80-94)
MIN_TRADING_DAYS = 240      # Minimum days of data required (240 ≈ 9.5 months)
MAX_PCT_FROM_HIGH = 10      # Tightened from 25% (69% win at 0-10% vs 45% at 15%+)

# Step 2 Thresholds (SEPA Fundamental Screening)
ENABLE_STEP2 = True         # Set False to skip fundamental screening
MIN_ACCELERATION_QUARTERS = 2   # Quarters showing acceleration (out of last 4)
MIN_EARNINGS_GROWTH = 15.0      # Minimum YoY earnings growth % (recent quarter)
MIN_SALES_GROWTH = 10.0         # Minimum YoY sales growth % (recent quarter)
REQUIRE_MARGIN_EXPANSION = True # Must show margin expansion over 8 quarters
MAX_ATR_PERCENT = 6.0           # Maximum ATR as % of price (lower = smoother trend)

# Entry Timing Thresholds (NEW)
EMA_PULLBACK_THRESHOLD = 5.0    # Within 5% of EMA = buy zone
EMA_EXTENDED_THRESHOLD = 10.0   # >10% above 21 EMA = extended/chasing

# Volume Thresholds (NEW)
VOLUME_STRONG_RATIO = 1.5       # 1.5x 50-day avg = strong volume
VOLUME_WEAK_RATIO = 0.8         # <0.8x avg = weak volume
UP_DOWN_VOLUME_THRESHOLD = 1.2  # Up days should have more volume than down days

# Earnings Warning (NEW)
EARNINGS_DANGER_DAYS = 14       # Within 14 days = danger zone
EARNINGS_CAUTION_DAYS = 45      # Within 45 days = caution

# Sector Concentration (NEW)
MAX_SECTOR_CONCENTRATION = 40   # Warn if >40% of picks in one sector

# Finviz Scraper Settings
USE_FINVIZ_SCRAPER = True   # Set False to use hardcoded STOCK_LIST instead
MAX_PAGES = 4               # Number of Finviz pages to scrape (1 page ≈ 20 stocks)
CACHE_HOURS = 24            # Hours to cache Finviz results before re-scraping

# ============================================================================
# FINVIZ SCRAPER
# ============================================================================

def scrape_finviz_screener(max_pages=MAX_PAGES):
    """
    Scrape stock tickers from Finviz screener
    URL criteria: 30%+ above 52w low, Price above 200 MA, 50 MA above 200 MA
    """
    if not HAS_WEB_SCRAPING:
        print("ERROR: Cannot scrape Finviz without requests and beautifulsoup4")
        print("Install with: pip install requests beautifulsoup4")
        return None

    # Base URL for Finviz screener
    # Filters: 30%+ above 52w low, price > 200MA, 50MA > 200MA
    base_url = "https://finviz.com/screener.ashx?v=411&f=ta_highlow52w_a30h,ta_sma200_pa,ta_sma50_sa200&ft=4"

    tickers = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    print(f"Scraping Finviz screener (max {max_pages} pages)...")

    for page in range(max_pages):
        # Finviz pagination: r=1 (page 1), r=1001 (page 2), r=2001 (page 3), etc.
        # Actually it's r=1, r=21, r=41... for 20 results per page
        # But the user's URLs show r=1001, r=2001, suggesting different pagination
        # Let me use the pattern from user's example: r increases by 1000
        if page == 0:
            url = base_url
        else:
            url = f"{base_url}&r={page * 1000 + 1}"

        try:
            print(f"  Fetching page {page + 1}...", end=" ")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the screener_tickers table cell
            ticker_cells = soup.find_all('td', class_='screener_tickers')

            if not ticker_cells:
                print(f"No more results (page {page + 1})")
                break

            # Extract ticker symbols from spans
            page_tickers = []
            for cell in ticker_cells:
                spans = cell.find_all('span')
                for span in spans:
                    # Extract ticker from onclick attribute or text content
                    onclick = span.get('onclick', '')
                    if 'quote.ashx?t=' in onclick:
                        # Extract ticker from: window.location='quote.ashx?t=TXT&...
                        match = re.search(r"t=([A-Z]+)", onclick)
                        if match:
                            ticker = match.group(1)
                            if ticker not in page_tickers:
                                page_tickers.append(ticker)

            tickers.extend(page_tickers)
            print(f"✓ Found {len(page_tickers)} tickers (total: {len(tickers)})")

            # Be nice to Finviz - add small delay between pages
            if page < max_pages - 1:
                time.sleep(1)

        except requests.exceptions.RequestException as e:
            print(f"✗ Error fetching page {page + 1}: {e}")
            if page == 0:
                # If first page fails, this is a critical error
                return None
            else:
                # If later pages fail, just stop pagination
                break
        except Exception as e:
            print(f"✗ Error parsing page {page + 1}: {e}")
            break

    if not tickers:
        print("ERROR: No tickers found")
        return None

    print(f"✓ Scraped {len(tickers)} unique tickers from Finviz")
    return tickers

def get_stock_list():
    """
    Get stock list either from cache, Finviz scraper, or hardcoded list
    """
    cache_dir = Path(__file__).parent / "cache"
    cache_file = cache_dir / "finviz_tickers.json"

    # If not using scraper, return hardcoded list
    if not USE_FINVIZ_SCRAPER:
        print("Using hardcoded STOCK_LIST")
        return STOCK_LIST

    # Check cache
    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)

            cached_time = datetime.fromisoformat(cache_data['timestamp'])
            cache_age = datetime.now() - cached_time
            cache_age_hours = cache_age.total_seconds() / 3600

            if cache_age_hours < CACHE_HOURS:
                tickers = cache_data['tickers']
                print(f"Using cached Finviz tickers ({len(tickers)} stocks)")
                print(f"  Cache age: {cache_age_hours:.1f} hours (expires in {CACHE_HOURS - cache_age_hours:.1f} hours)")
                return tickers
            else:
                print(f"Cache expired ({cache_age_hours:.1f} hours old)")
        except Exception as e:
            print(f"Warning: Could not read cache: {e}")

    # Scrape Finviz
    print("Fetching fresh data from Finviz...")
    tickers = scrape_finviz_screener(MAX_PAGES)

    if tickers is None:
        print("ERROR: Failed to scrape Finviz screener")
        print("Make sure you have internet connection and Finviz is accessible")
        exit(1)

    # Save to cache
    try:
        cache_dir.mkdir(exist_ok=True)
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'tickers': tickers,
            'source': 'finviz_screener',
            'max_pages': MAX_PAGES
        }
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
        print(f"✓ Cached results to {cache_file}")
    except Exception as e:
        print(f"Warning: Could not save cache: {e}")

    return tickers

# ============================================================================
# RS CALCULATION FUNCTIONS
# ============================================================================

def calculate_ibd_rs(ticker, spy_data):
    """
    Calculate IBD-style Relative Strength for a stock
    Formula: 0.4*(3mo) + 0.2*(6mo) + 0.2*(9mo) + 0.2*(12mo)
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y")

        if len(df) < MIN_TRADING_DAYS:
            return None, f"Insufficient data ({len(df)} days, need {MIN_TRADING_DAYS}+)"

        current_price = df['Close'].iloc[-1]

        # Calculate returns for different periods (trading days)
        periods = {
            '3mo': min(63, len(df)),
            '6mo': min(126, len(df)),
            '9mo': min(189, len(df)),
            '12mo': min(252, len(df), len(spy_data))
        }

        weights = {
            '3mo': 0.4,
            '6mo': 0.2,
            '9mo': 0.2,
            '12mo': 0.2
        }

        returns = {}
        rs_score = 0

        for period_name, days in periods.items():
            if len(df) >= days and len(spy_data) >= days and days > 0:
                past_price = df['Close'].iloc[-days]
                stock_return = ((current_price - past_price) / past_price) * 100

                spy_past_price = spy_data['Close'].iloc[-days]
                spy_current_price = spy_data['Close'].iloc[-1]
                spy_return = ((spy_current_price - spy_past_price) / spy_past_price) * 100

                relative_return = stock_return - spy_return
                rs_score += weights[period_name] * relative_return

                returns[period_name] = stock_return
            else:
                returns[period_name] = None

        return {
            'rs_score': rs_score,
            'returns': returns
        }, None

    except Exception as e:
        return None, str(e)

# ============================================================================
# STAGE ANALYSIS FUNCTIONS
# ============================================================================

def calculate_ma_slope(ma_values, lookback=20):
    """Calculate if MA is trending up"""
    if len(ma_values) < lookback:
        return None
    recent_avg = ma_values[-5:].mean()
    older_avg = ma_values[-lookback:-15].mean()
    return (recent_avg - older_avg) / older_avg * 100

def determine_stage(df, price, ma_50, ma_150, ma_200, criteria):
    """Determine market stage based on price action and MA relationships"""
    if all(criteria.values()):
        return 2

    if price < ma_200 and not criteria['3. 200 MA trending up']:
        return 4

    if price > ma_200 and criteria['3. 200 MA trending up']:
        if ma_50 < ma_200:
            return 1
        else:
            return 3

    return 1

def analyze_stage(ticker, rs_rating):
    """
    Analyze stock stage using Minervini's Stage 2 Trend Template
    Returns stage number and detailed criteria breakdown
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y")

        if len(df) < 200:
            return None, "Insufficient data for MA calculation"

        # Calculate moving averages
        df['MA_50'] = df['Close'].rolling(window=50).mean()
        df['MA_150'] = df['Close'].rolling(window=150).mean()
        df['MA_200'] = df['Close'].rolling(window=200).mean()

        # Get current values
        current_price = df['Close'].iloc[-1]
        ma_50 = df['MA_50'].iloc[-1]
        ma_150 = df['MA_150'].iloc[-1]
        ma_200 = df['MA_200'].iloc[-1]

        # 52-week high/low
        week_52_high = df['High'].max()
        week_52_low = df['Low'].min()

        # Calculate MA slope
        ma_200_slope = calculate_ma_slope(df['MA_200'].dropna())

        # Stage 2 Trend Template - All 9 criteria (optimized from backtest)
        criteria = {
            '1. Price > 150 & 200 MA': current_price > ma_150 and current_price > ma_200,
            '2. 150 MA > 200 MA': ma_150 > ma_200,
            '3. 200 MA trending up': ma_200_slope is not None and ma_200_slope > 0,
            '4. 50 MA > 150 & 200 MA': ma_50 > ma_150 and ma_50 > ma_200,
            '5. Price > 50 MA': current_price > ma_50,
            '6. Price 30%+ above 52w low': ((current_price - week_52_low) / week_52_low * 100) >= 30,
            '7. Price within 10% of 52w high': ((week_52_high - current_price) / week_52_high * 100) <= MAX_PCT_FROM_HIGH,
            '8. RS Rating >= 80': rs_rating >= MIN_RS_RATING,
            '9. RS not overextended': rs_rating <= MAX_RS_RATING
        }

        stage = determine_stage(df, current_price, ma_50, ma_150, ma_200, criteria)

        pct_above_52w_low = ((current_price - week_52_low) / week_52_low * 100)
        pct_from_52w_high = ((week_52_high - current_price) / week_52_high * 100)

        return {
            'stage': stage,
            'criteria': criteria,
            'passes_all_criteria': all(criteria.values()),
            'current_price': current_price,
            'ma_50': ma_50,
            'ma_150': ma_150,
            'ma_200': ma_200,
            'ma_200_slope': ma_200_slope,
            'week_52_high': week_52_high,
            'week_52_low': week_52_low,
            'pct_above_52w_low': pct_above_52w_low,
            'pct_from_52w_high': pct_from_52w_high,
            'rs_rating': rs_rating
        }, None

    except Exception as e:
        return None, str(e)

# ============================================================================
# ENTRY TIMING ANALYSIS (NEW)
# ============================================================================

def analyze_entry_timing(df):
    """
    Analyze if stock is in a buyable pullback zone near 10/21 EMA.
    Returns entry status: BUY_ZONE, EXTENDED, or WATCHLIST
    """
    if len(df) < 21:
        return None

    # Calculate EMAs
    df['EMA_10'] = df['Close'].ewm(span=10, adjust=False).mean()
    df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()

    current_price = df['Close'].iloc[-1]
    ema_10 = df['EMA_10'].iloc[-1]
    ema_21 = df['EMA_21'].iloc[-1]

    # Calculate distance from EMAs
    pct_above_ema_10 = ((current_price - ema_10) / ema_10) * 100
    pct_above_ema_21 = ((current_price - ema_21) / ema_21) * 100

    # Determine entry status
    # BUY_ZONE: Price within 5% above either 10 or 21 EMA (pullback entry)
    # EXTENDED: Price >10% above 21 EMA (chasing)
    # WATCHLIST: In between
    if pct_above_ema_10 <= EMA_PULLBACK_THRESHOLD or pct_above_ema_21 <= EMA_PULLBACK_THRESHOLD:
        if pct_above_ema_10 >= -3 and pct_above_ema_21 >= -3:  # Not too deep below
            entry_status = "BUY_ZONE"
        else:
            entry_status = "WATCHLIST"  # Too deep, might be breaking down
    elif pct_above_ema_21 > EMA_EXTENDED_THRESHOLD:
        entry_status = "EXTENDED"
    else:
        entry_status = "WATCHLIST"

    return {
        'ema_10': ema_10,
        'ema_21': ema_21,
        'pct_above_ema_10': pct_above_ema_10,
        'pct_above_ema_21': pct_above_ema_21,
        'entry_status': entry_status
    }

# ============================================================================
# VOLUME ANALYSIS (NEW)
# ============================================================================

def analyze_volume(df):
    """
    Analyze volume patterns to validate breakouts.
    Returns volume status: STRONG, WEAK, or NORMAL
    """
    if len(df) < 50:
        return None

    # 50-day average volume
    avg_volume_50d = df['Volume'].tail(50).mean()

    # Recent 5-day average volume
    recent_volume = df['Volume'].tail(5).mean()

    # Volume ratio
    volume_ratio = recent_volume / avg_volume_50d if avg_volume_50d > 0 else 1.0

    # Up/Down volume ratio (last 20 days)
    recent_20 = df.tail(20).copy()
    recent_20['Change'] = recent_20['Close'].diff()

    up_days = recent_20[recent_20['Change'] > 0]
    down_days = recent_20[recent_20['Change'] < 0]

    avg_up_volume = up_days['Volume'].mean() if len(up_days) > 0 else 0
    avg_down_volume = down_days['Volume'].mean() if len(down_days) > 0 else 1

    up_down_ratio = avg_up_volume / avg_down_volume if avg_down_volume > 0 else 1.0

    # Determine volume status
    if volume_ratio >= VOLUME_STRONG_RATIO and up_down_ratio >= UP_DOWN_VOLUME_THRESHOLD:
        volume_status = "STRONG"
    elif volume_ratio < VOLUME_WEAK_RATIO or up_down_ratio < 0.8:
        volume_status = "WEAK"
    else:
        volume_status = "NORMAL"

    return {
        'avg_volume_50d': avg_volume_50d,
        'recent_volume': recent_volume,
        'volume_ratio': volume_ratio,
        'up_down_ratio': up_down_ratio,
        'volume_status': volume_status
    }

# ============================================================================
# EARNINGS DATE WARNING (NEW)
# ============================================================================

def get_earnings_warning(ticker):
    """
    Check upcoming earnings date and flag if within danger/caution zone.
    Returns earnings info with warning flag.

    Flags:
    - DANGER: Earnings within 14 days
    - CAUTION: Earnings within 45 days
    - CLEAR: Earnings > 45 days away
    - REPORTED: Last earnings date known, next not yet scheduled
    - N/A: No earnings data (ETFs, funds, etc.)
    """
    try:
        stock = yf.Ticker(ticker)

        # Use stock.calendar which returns simple datetime.date objects
        try:
            calendar = stock.calendar
            if calendar and 'Earnings Date' in calendar:
                earnings_dates = calendar['Earnings Date']

                # No earnings dates at all (ETFs, funds, etc.)
                if not earnings_dates or len(earnings_dates) == 0:
                    return {
                        'next_earnings_date': None,
                        'last_earnings_date': None,
                        'days_until_earnings': None,
                        'earnings_flag': "N/A"
                    }

                # Get the earnings date (first in list)
                earnings_date = earnings_dates[0]
                today = datetime.now().date()
                days_until = (earnings_date - today).days

                if days_until < 0:
                    # Earnings already passed - show as last reported
                    # Check if there's a future date in the list
                    future_date = None
                    for d in earnings_dates:
                        if (d - today).days >= 0:
                            future_date = d
                            break

                    if future_date:
                        # Found a future date
                        days_until = (future_date - today).days
                        if days_until <= EARNINGS_DANGER_DAYS:
                            earnings_flag = "DANGER"
                        elif days_until <= EARNINGS_CAUTION_DAYS:
                            earnings_flag = "CAUTION"
                        else:
                            earnings_flag = "CLEAR"
                        return {
                            'next_earnings_date': future_date.strftime('%Y-%m-%d'),
                            'last_earnings_date': earnings_date.strftime('%Y-%m-%d'),
                            'days_until_earnings': days_until,
                            'earnings_flag': earnings_flag
                        }
                    else:
                        # Only past date available - next earnings TBD
                        return {
                            'next_earnings_date': None,
                            'last_earnings_date': earnings_date.strftime('%Y-%m-%d'),
                            'days_until_earnings': None,
                            'earnings_flag': "REPORTED"
                        }

                # Future earnings date
                if days_until <= EARNINGS_DANGER_DAYS:
                    earnings_flag = "DANGER"
                elif days_until <= EARNINGS_CAUTION_DAYS:
                    earnings_flag = "CAUTION"
                else:
                    earnings_flag = "CLEAR"

                return {
                    'next_earnings_date': earnings_date.strftime('%Y-%m-%d'),
                    'last_earnings_date': None,
                    'days_until_earnings': days_until,
                    'earnings_flag': earnings_flag
                }
        except Exception:
            pass  # Fall through to default

        # Default if no earnings data available
        return {
            'next_earnings_date': None,
            'last_earnings_date': None,
            'days_until_earnings': None,
            'earnings_flag': "N/A"
        }

    except Exception:
        return {
            'next_earnings_date': None,
            'last_earnings_date': None,
            'days_until_earnings': None,
            'earnings_flag': "N/A"
        }

# ============================================================================
# MARKET REGIME FILTER (NEW)
# ============================================================================

def analyze_market_regime(spy_data):
    """
    Analyze SPY to determine overall market health.
    Returns regime: BULLISH, CAUTIOUS, or BEARISH
    """
    if len(spy_data) < 200:
        return {
            'spy_price': None,
            'spy_ma_50': None,
            'spy_ma_200': None,
            'regime': "UNKNOWN",
            'regime_warning': True
        }

    # Calculate MAs
    spy_ma_50 = spy_data['Close'].rolling(window=50).mean().iloc[-1]
    spy_ma_200 = spy_data['Close'].rolling(window=200).mean().iloc[-1]
    spy_price = spy_data['Close'].iloc[-1]

    # Determine regime
    if spy_price > spy_ma_50 and spy_ma_50 > spy_ma_200:
        regime = "BULLISH"
        regime_warning = False
    elif spy_price > spy_ma_200:
        regime = "CAUTIOUS"
        regime_warning = True
    else:
        regime = "BEARISH"
        regime_warning = True

    return {
        'spy_price': spy_price,
        'spy_ma_50': spy_ma_50,
        'spy_ma_200': spy_ma_200,
        'regime': regime,
        'regime_warning': regime_warning
    }

# ============================================================================
# SECTOR TRACKING (NEW)
# ============================================================================

def get_sector(ticker):
    """
    Get sector for a stock from yfinance.
    Returns sector string or 'Unknown'.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return info.get('sector', 'Unknown')
    except Exception:
        return 'Unknown'

def format_earnings_display(earn_data):
    """
    Format earnings data for display in reports.
    Returns a string like: "35d", "12d [!]", "Rpt:10/22", "N/A"
    """
    if not earn_data:
        return "N/A"

    flag = earn_data.get('earnings_flag', 'N/A')
    days = earn_data.get('days_until_earnings')
    last_date = earn_data.get('last_earnings_date')

    if flag == "N/A":
        return "N/A"
    elif flag == "REPORTED":
        # Show last earnings date in MM/DD format
        if last_date:
            try:
                from datetime import datetime as dt
                d = dt.strptime(last_date, '%Y-%m-%d')
                return f"Rpt:{d.month}/{d.day}"
            except:
                return "Rpt:--"
        return "Rpt:--"
    elif flag == "DANGER":
        return f"{days}d [!]"
    elif days is not None:
        return f"{days}d"
    else:
        return flag

def calculate_sector_concentration(results):
    """
    Calculate sector breakdown and flag concentration issues.
    Returns dict with sector counts and warnings.
    """
    sector_counts = {}
    total = len(results)

    for r in results:
        sector = r.get('sector', 'Unknown')
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    # Calculate percentages and flag concentration
    sector_breakdown = {}
    concentrated_sectors = []

    for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count / total * 100) if total > 0 else 0
        sector_breakdown[sector] = {
            'count': count,
            'percentage': pct,
            'concentrated': pct > MAX_SECTOR_CONCENTRATION
        }
        if pct > MAX_SECTOR_CONCENTRATION:
            concentrated_sectors.append(sector)

    return {
        'breakdown': sector_breakdown,
        'concentrated_sectors': concentrated_sectors,
        'has_concentration_warning': len(concentrated_sectors) > 0
    }

# ============================================================================
# STEP 2: FUNDAMENTAL SCREENING (SEPA)
# ============================================================================

def calculate_atr_percent(ticker):
    """Calculate Average True Range as percentage of price"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="3mo")

        if len(df) < 20:
            return None

        # Calculate True Range
        df['H-L'] = df['High'] - df['Low']
        df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
        df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
        df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)

        # ATR is 14-period average of True Range
        atr = df['TR'].rolling(window=14).mean().iloc[-1]
        current_price = df['Close'].iloc[-1]

        atr_percent = (atr / current_price) * 100
        return atr_percent

    except Exception as e:
        return None

def check_acceleration(values):
    """
    Check if values show acceleration pattern
    Returns number of quarters (out of last 4) showing acceleration
    """
    if len(values) < 4:
        return 0

    # Look at last 4 quarters
    recent_4 = values[-4:]

    # Count how many quarters show growth > previous quarter
    acceleration_count = 0
    for i in range(1, len(recent_4)):
        if recent_4[i] > recent_4[i-1]:
            acceleration_count += 1

    return acceleration_count

def analyze_fundamentals(ticker):
    """
    Analyze quarterly earnings, sales, and margins for acceleration
    Returns dict with fundamental metrics and pass/fail for Step 2
    """
    try:
        stock = yf.Ticker(ticker)

        # Get quarterly financials
        quarterly_financials = stock.quarterly_financials
        quarterly_income = stock.quarterly_income_stmt

        if quarterly_financials is None or len(quarterly_financials.columns) < 4:
            return None, "Insufficient quarterly data"

        # Get quarterly earnings (try multiple possible field names)
        earnings_fields = ['Net Income', 'NetIncome', 'Net Income Common Stockholders']
        eps_data = None
        for field in earnings_fields:
            if field in quarterly_income.index:
                eps_data = quarterly_income.loc[field]
                break

        # Get quarterly revenue
        revenue_fields = ['Total Revenue', 'TotalRevenue', 'Revenue']
        revenue_data = None
        for field in revenue_fields:
            if field in quarterly_income.index:
                revenue_data = quarterly_income.loc[field]
                break

        # Get margins from info (most recent)
        info = stock.info
        current_margin = info.get('profitMargins', None)

        # Calculate growth rates and acceleration
        results = {
            'has_earnings_data': eps_data is not None and len(eps_data) >= 4,
            'has_revenue_data': revenue_data is not None and len(revenue_data) >= 4,
            'earnings_acceleration_quarters': 0,
            'revenue_acceleration_quarters': 0,
            'margin_expansion': False,
            'recent_earnings_growth': None,
            'recent_revenue_growth': None,
            'current_margin': current_margin,
            'atr_percent': calculate_atr_percent(ticker)
        }

        # Check earnings acceleration
        if results['has_earnings_data']:
            # Sort by date (most recent first)
            eps_sorted = eps_data.sort_index(ascending=False)

            # Calculate YoY growth for most recent quarter (compare to 4 quarters ago)
            if len(eps_sorted) >= 5:
                recent_eps = eps_sorted.iloc[0]
                year_ago_eps = eps_sorted.iloc[4]
                if year_ago_eps != 0 and not pd.isna(year_ago_eps):
                    results['recent_earnings_growth'] = ((recent_eps - year_ago_eps) / abs(year_ago_eps)) * 100

            # Check acceleration pattern
            eps_values = eps_sorted.head(8).values  # Last 8 quarters
            results['earnings_acceleration_quarters'] = check_acceleration(eps_values[::-1])  # Reverse to chronological

        # Check revenue acceleration
        if results['has_revenue_data']:
            revenue_sorted = revenue_data.sort_index(ascending=False)

            # Calculate YoY growth
            if len(revenue_sorted) >= 5:
                recent_rev = revenue_sorted.iloc[0]
                year_ago_rev = revenue_sorted.iloc[4]
                if year_ago_rev != 0 and not pd.isna(year_ago_rev):
                    results['recent_revenue_growth'] = ((recent_rev - year_ago_rev) / year_ago_rev) * 100

            # Check acceleration
            rev_values = revenue_sorted.head(8).values
            results['revenue_acceleration_quarters'] = check_acceleration(rev_values[::-1])

        # Check margin expansion (simple check: compare recent vs older quarters)
        if current_margin is not None and current_margin > 0:
            # If we have margin data, assume expansion if margin > historical average
            # This is simplified - ideally we'd track quarterly margins
            results['margin_expansion'] = True  # Placeholder - improve with historical margin tracking

        # Determine if passes Step 2 criteria
        passes_step2 = True
        failed_criteria = []

        # Check earnings acceleration
        if results['earnings_acceleration_quarters'] < MIN_ACCELERATION_QUARTERS:
            passes_step2 = False
            failed_criteria.append(f"Earnings acceleration ({results['earnings_acceleration_quarters']}/{MIN_ACCELERATION_QUARTERS} quarters)")

        # Check revenue acceleration
        if results['revenue_acceleration_quarters'] < MIN_ACCELERATION_QUARTERS:
            passes_step2 = False
            failed_criteria.append(f"Revenue acceleration ({results['revenue_acceleration_quarters']}/{MIN_ACCELERATION_QUARTERS} quarters)")

        # Check minimum growth rates
        if results['recent_earnings_growth'] is not None and results['recent_earnings_growth'] < MIN_EARNINGS_GROWTH:
            passes_step2 = False
            failed_criteria.append(f"Earnings growth ({results['recent_earnings_growth']:.1f}% < {MIN_EARNINGS_GROWTH}%)")

        if results['recent_revenue_growth'] is not None and results['recent_revenue_growth'] < MIN_SALES_GROWTH:
            passes_step2 = False
            failed_criteria.append(f"Revenue growth ({results['recent_revenue_growth']:.1f}% < {MIN_SALES_GROWTH}%)")

        # Check volatility (ATR)
        if results['atr_percent'] is not None and results['atr_percent'] > MAX_ATR_PERCENT:
            passes_step2 = False
            failed_criteria.append(f"High volatility (ATR {results['atr_percent']:.1f}% > {MAX_ATR_PERCENT}%)")

        results['passes_step2'] = passes_step2
        results['failed_criteria'] = failed_criteria

        return results, None

    except Exception as e:
        return None, str(e)

def calculate_quality_score(stage_analysis, fundamentals):
    """
    Calculate quality score (0-100) based on backtest-proven edge factors.
    Returns tuple of (score, grade).

    Scoring based on 18-month backtest of 2,453 SEPA signals:
    - Distance from high: Most predictive factor (69% win at 0-10% vs 45% at 15%+)
    - RS Rating: Sweet spot is 85-94, RS 95+ often overextended
    - Earnings Growth: >50% growth shows significantly better returns
    - Revenue Growth: Additional confirmation factor
    - Earnings Acceleration: Momentum confirmation
    """
    score = 0

    # 1. Distance from 52-week high (30 pts max) - MOST IMPORTANT
    pct_from_high = stage_analysis['pct_from_52w_high']
    if pct_from_high <= 5:
        score += 30
    elif pct_from_high <= 10:
        score += 25
    elif pct_from_high <= 15:
        score += 15
    elif pct_from_high <= 20:
        score += 5
    # else: 0 points

    # 2. RS Rating (25 pts max) - sweet spot is 85-94
    rs = stage_analysis['rs_rating']
    if 85 <= rs <= 94:
        score += 25
    elif 80 <= rs <= 84:
        score += 20
    elif 75 <= rs <= 79:
        score += 15
    elif 70 <= rs <= 74:
        score += 10
    elif rs >= 95:
        score += 10  # Penalized - likely overextended

    # 3. Earnings Growth (25 pts max)
    eg = fundamentals.get('recent_earnings_growth')
    if eg is not None:
        if eg > 100:
            score += 25
        elif eg > 50:
            score += 20
        elif eg > 25:
            score += 15
        elif eg > 15:
            score += 10
        else:
            score += 5

    # 4. Revenue Growth (10 pts max)
    rg = fundamentals.get('recent_revenue_growth')
    if rg is not None:
        if rg > 50:
            score += 10
        elif rg > 25:
            score += 7
        elif rg > 10:
            score += 5

    # 5. Earnings Acceleration (10 pts max)
    ea = fundamentals.get('earnings_acceleration_quarters', 0)
    if ea >= 3:
        score += 10
    elif ea >= 2:
        score += 5

    # Determine grade
    if score >= 85:
        grade = 'A'
    elif score >= 70:
        grade = 'B'
    elif score >= 55:
        grade = 'C'
    else:
        grade = 'D'

    return score, grade

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("=" * 100)
    print("SUPERPERFORM - COMPLETE MINERVINI SEPA ANALYSIS")
    print("=" * 100)

    # Get stock list (from Finviz or hardcoded)
    stock_list = get_stock_list()

    print(f"\nConfiguration:")
    print(f"  • Analyzing {len(stock_list)} stocks")
    print(f"  • Stock Source: {'Finviz Screener' if USE_FINVIZ_SCRAPER else 'Hardcoded List'}")
    if USE_FINVIZ_SCRAPER:
        print(f"    - Max Pages: {MAX_PAGES}")
        print(f"    - Cache Duration: {CACHE_HOURS} hours")
    print(f"  • Minimum RS Rating: {MIN_RS_RATING}")
    print(f"  • Step 2 Screening: {'ENABLED' if ENABLE_STEP2 else 'DISABLED'}")
    if ENABLE_STEP2:
        print(f"    - Min Acceleration Quarters: {MIN_ACCELERATION_QUARTERS}/4")
        print(f"    - Min Earnings Growth: {MIN_EARNINGS_GROWTH}% YoY")
        print(f"    - Min Revenue Growth: {MIN_SALES_GROWTH}% YoY")
        print(f"    - Max ATR %: {MAX_ATR_PERCENT}%")

    # ========================================================================
    # STEP 1: Calculate RS Ratings
    # ========================================================================
    print("\n" + "─" * 100)
    print("STEP 1: CALCULATING RELATIVE STRENGTH RATINGS")
    print("─" * 100)
    print("\nDownloading S&P 500 (SPY) benchmark data...")

    try:
        spy = yf.Ticker("SPY")
        spy_data = spy.history(period="1y")

        if spy_data is None or len(spy_data) == 0:
            print("ERROR: Could not fetch SPY data. Exiting.")
            return

        print(f"✓ Downloaded {len(spy_data)} days of SPY data")
        print(f"  Date range: {spy_data.index[0].date()} to {spy_data.index[-1].date()}\n")

    except Exception as e:
        print(f"ERROR: Exception while fetching SPY data: {e}")
        return

    # Analyze market regime (NEW)
    market_regime = analyze_market_regime(spy_data)
    print(f"MARKET REGIME: {market_regime['regime']}")
    if market_regime['spy_price']:
        print(f"  SPY: ${market_regime['spy_price']:.2f} | 50 MA: ${market_regime['spy_ma_50']:.2f} | 200 MA: ${market_regime['spy_ma_200']:.2f}")
    if market_regime['regime_warning']:
        print(f"  [!] WARNING: Market conditions not optimal for new positions\n")
    else:
        print(f"  Market healthy - full position sizes OK\n")

    # Calculate RS for all stocks
    print(f"Calculating RS ratings for {len(stock_list)} stocks...\n")
    rs_results = []

    for i, ticker in enumerate(stock_list, 1):
        print(f"[{i}/{len(stock_list)}] Processing {ticker}...", end=" ")

        rs_data, error = calculate_ibd_rs(ticker, spy_data)

        if rs_data:
            rs_results.append({
                'Symbol': ticker,
                'RS Score': rs_data['rs_score'],
                '3mo Return': rs_data['returns']['3mo'],
                '6mo Return': rs_data['returns']['6mo'],
                '12mo Return': rs_data['returns']['12mo'],
                'Error': None
            })
            print("✓")
        else:
            rs_results.append({
                'Symbol': ticker,
                'RS Score': None,
                '3mo Return': None,
                '6mo Return': None,
                '12mo Return': None,
                'Error': error
            })
            print(f"✗ ({error})")

    # Calculate RS Rating (percentile rank)
    df_rs = pd.DataFrame(rs_results)
    valid_scores = df_rs[df_rs['RS Score'].notna()]['RS Score']
    df_rs['RS Rating'] = df_rs['RS Score'].apply(
        lambda x: int(pd.Series(valid_scores).rank(pct=True)[df_rs[df_rs['RS Score'] == x].index[0]] * 99)
        if pd.notna(x) else None
    )

    # Filter stocks by RS rating
    high_rs_stocks = df_rs[df_rs['RS Rating'] >= MIN_RS_RATING].sort_values('RS Rating', ascending=False)

    print(f"\n✓ RS Calculation Complete")
    print(f"  • {len(high_rs_stocks)} stocks with RS >= {MIN_RS_RATING}")
    print(f"  • {len(df_rs[df_rs['RS Rating'].isna()])} stocks with errors/insufficient data")

    if len(high_rs_stocks) == 0:
        print(f"\nNo stocks meet the RS >= {MIN_RS_RATING} threshold. Exiting.")
        return

    # ========================================================================
    # STEP 2: Analyze Stage for High RS Stocks
    # ========================================================================
    print("\n" + "─" * 100)
    print("STEP 2: STAGE ANALYSIS FOR HIGH RS STOCKS")
    print("─" * 100)
    print(f"\nAnalyzing {len(high_rs_stocks)} stocks with RS >= {MIN_RS_RATING}...\n")

    stage_results = []

    for i, (_, row) in enumerate(high_rs_stocks.iterrows(), 1):
        ticker = row['Symbol']
        rs_rating = row['RS Rating']

        print(f"[{i}/{len(high_rs_stocks)}] Analyzing {ticker} (RS={rs_rating})...", end=" ")

        analysis, error = analyze_stage(ticker, rs_rating)

        if analysis:
            stage_results.append({
                'ticker': ticker,
                'rs_score': row['RS Score'],
                'analysis': analysis
            })
            stage = analysis['stage']
            status = "✓ STAGE 2" if analysis['passes_all_criteria'] else f"Stage {stage}"
            print(status)
        else:
            print(f"✗ ({error})")

    stage_2_stocks = [r for r in stage_results if r['analysis']['passes_all_criteria']]

    print(f"\n✓ Stage Analysis Complete")
    print(f"  • {len(stage_2_stocks)} stocks meet all 8 Stage 2 criteria")

    # ========================================================================
    # STEP 3: Fundamental Screening (SEPA Step 2)
    # ========================================================================
    if ENABLE_STEP2 and len(stage_2_stocks) > 0:
        print("\n" + "─" * 100)
        print("STEP 3: FUNDAMENTAL SCREENING (SEPA STEP 2)")
        print("─" * 100)
        print(f"\nAnalyzing fundamentals for {len(stage_2_stocks)} Stage 2 stocks...")
        print("Checking: Earnings acceleration, Revenue acceleration, Margins, Volatility\n")

        sepa_results = []

        for i, result in enumerate(stage_2_stocks, 1):
            ticker = result['ticker']
            print(f"[{i}/{len(stage_2_stocks)}] {ticker}...", end=" ")

            fundamentals, error = analyze_fundamentals(ticker)

            if fundamentals:
                result['fundamentals'] = fundamentals
                sepa_results.append(result)

                if fundamentals['passes_step2']:
                    print("✓ SEPA QUALIFIED")
                else:
                    print(f"✗ ({fundamentals['failed_criteria'][0]})")
            else:
                print(f"✗ ({error})")

        sepa_qualified = [r for r in sepa_results if r['fundamentals']['passes_step2']]

        # Calculate quality scores for all SEPA qualified stocks
        for result in sepa_qualified:
            score, grade = calculate_quality_score(result['analysis'], result['fundamentals'])
            result['quality_score'] = score
            result['grade'] = grade

        # Sort by quality score (highest first)
        sepa_qualified.sort(key=lambda x: x['quality_score'], reverse=True)

        print(f"\n✓ Fundamental Screening Complete")
        print(f"  • {len(sepa_qualified)} stocks pass all SEPA Step 2 criteria")
        print(f"  • {len(stage_2_stocks) - len(sepa_qualified)} stocks filtered out (~{(len(stage_2_stocks) - len(sepa_qualified))/len(stage_2_stocks)*100:.0f}% rejection rate)")

        # Count by grade
        grade_counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
        for r in sepa_qualified:
            grade_counts[r['grade']] += 1
        print(f"  Quality Grades: A={grade_counts['A']}, B={grade_counts['B']}, C={grade_counts['C']}, D={grade_counts['D']}")

        stage_2_stocks = sepa_results  # Update to include fundamental data

    # ========================================================================
    # STEP 4: ENHANCED ANALYSIS (Entry Timing, Volume, Earnings, Sector)
    # ========================================================================
    if ENABLE_STEP2 and 'sepa_qualified' in locals() and len(sepa_qualified) > 0:
        print("\n" + "-" * 100)
        print("STEP 4: ENHANCED ANALYSIS (Entry, Volume, Earnings, Sector)")
        print("-" * 100)
        print(f"\nAnalyzing {len(sepa_qualified)} SEPA qualified stocks for entry timing...\n")

        for i, result in enumerate(sepa_qualified, 1):
            ticker = result['ticker']
            print(f"[{i}/{len(sepa_qualified)}] {ticker}...", end=" ")

            # Get fresh price data for entry/volume analysis
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period="3mo")

                # Entry timing analysis
                entry_data = analyze_entry_timing(df)
                if entry_data:
                    result['entry'] = entry_data

                # Volume analysis
                volume_data = analyze_volume(df)
                if volume_data:
                    result['volume'] = volume_data

                # Earnings warning
                earnings_data = get_earnings_warning(ticker)
                result['earnings'] = earnings_data

                # Sector
                sector = get_sector(ticker)
                result['sector'] = sector

                # Print status
                entry_status = entry_data['entry_status'] if entry_data else "N/A"
                vol_status = volume_data['volume_status'] if volume_data else "N/A"
                earn_flag = earnings_data['earnings_flag']
                print(f"{entry_status} | Vol:{vol_status} | Earn:{earn_flag} | {sector}")

            except Exception as e:
                print(f"Error: {e}")
                result['entry'] = None
                result['volume'] = None
                result['earnings'] = {'earnings_flag': 'UNKNOWN', 'days_until_earnings': None, 'next_earnings_date': None}
                result['sector'] = 'Unknown'

        # Calculate sector concentration
        sector_analysis = calculate_sector_concentration(sepa_qualified)

        print(f"\n✓ Enhanced Analysis Complete")

    # ========================================================================
    # CLEAN REPORT OUTPUT (NEW FORMAT)
    # ========================================================================
    print("\n")
    print("=" * 100)
    print(f"SUPERPERFORM SEPA ANALYSIS - {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 100)

    # Market Status Header
    print(f"\nMARKET STATUS: {market_regime['regime']}")
    if market_regime['spy_price']:
        above_50 = "Above" if market_regime['spy_price'] > market_regime['spy_ma_50'] else "Below"
        above_200 = "Above" if market_regime['spy_price'] > market_regime['spy_ma_200'] else "Below"
        print(f"  SPY: ${market_regime['spy_price']:.2f} | {above_50} 50 MA (${market_regime['spy_ma_50']:.2f}) | {above_200} 200 MA (${market_regime['spy_ma_200']:.2f})")
    if market_regime['regime'] == "BULLISH":
        print("  Recommendation: Full position sizes OK")
    elif market_regime['regime'] == "CAUTIOUS":
        print("  Recommendation: Reduce position sizes, be selective")
    else:
        print("  Recommendation: Cash preferred, avoid new longs")

    # TOP PICKS Section - Grade A/B, BUY_ZONE, no earnings danger
    if ENABLE_STEP2 and 'sepa_qualified' in locals() and len(sepa_qualified) > 0:
        top_picks = [r for r in sepa_qualified if
                     r.get('grade') in ['A', 'B'] and
                     r.get('entry', {}).get('entry_status') == 'BUY_ZONE' and
                     r.get('earnings', {}).get('earnings_flag') != 'DANGER']

        if top_picks:
            print("\n" + "-" * 100)
            print("TOP PICKS - Ready to Buy (Grade A/B, Buy Zone, Earnings Clear)")
            print("-" * 100)
            print(f"  {'TICKER':<8} {'GRADE':<6} {'RS':<4} {'PRICE':<10} {'ENTRY':<10} {'VOLUME':<8} {'EARNINGS':<10} {'SECTOR':<15}")
            print(f"  {'-'*8} {'-'*6} {'-'*4} {'-'*10} {'-'*10} {'-'*8} {'-'*10} {'-'*15}")

            for r in top_picks:
                ticker = r['ticker']
                grade = r.get('grade', '?')
                rs = r['analysis']['rs_rating']
                price = r['analysis']['current_price']
                entry = r.get('entry', {}).get('entry_status', 'N/A')
                volume = r.get('volume', {}).get('volume_status', 'N/A')
                earn = r.get('earnings', {})
                earn_str = format_earnings_display(earn)
                sector = r.get('sector', 'Unknown')[:15]

                print(f"  {ticker:<8} {grade:<6} {rs:<4} ${price:<9.2f} {entry:<10} {volume:<8} {earn_str:<10} {sector:<15}")

        # WATCHLIST Section - Extended or earnings soon
        watchlist = [r for r in sepa_qualified if r not in top_picks]

        if watchlist:
            print("\n" + "-" * 100)
            print("WATCHLIST - Wait for Pullback or Earnings to Pass")
            print("-" * 100)
            print(f"  {'TICKER':<8} {'GRADE':<6} {'RS':<4} {'PRICE':<10} {'ENTRY':<10} {'VOLUME':<8} {'EARNINGS':<10} {'SECTOR':<15}")
            print(f"  {'-'*8} {'-'*6} {'-'*4} {'-'*10} {'-'*10} {'-'*8} {'-'*10} {'-'*15}")

            for r in watchlist:
                ticker = r['ticker']
                grade = r.get('grade', '?')
                rs = r['analysis']['rs_rating']
                price = r['analysis']['current_price']
                entry = r.get('entry', {}).get('entry_status', 'N/A')
                volume = r.get('volume', {}).get('volume_status', 'N/A')
                earn = r.get('earnings', {})
                earn_str = format_earnings_display(earn)
                sector = r.get('sector', 'Unknown')[:15]

                print(f"  {ticker:<8} {grade:<6} {rs:<4} ${price:<9.2f} {entry:<10} {volume:<8} {earn_str:<10} {sector:<15}")

        # Sector Concentration
        if 'sector_analysis' in locals():
            print("\n" + "-" * 100)
            print("SECTOR CONCENTRATION")
            print("-" * 100)
            for sector, data in sector_analysis['breakdown'].items():
                warn = " [!CONCENTRATED]" if data['concentrated'] else ""
                print(f"  {sector:<20} {data['percentage']:>5.1f}% ({data['count']} stocks){warn}")

    # Summary Stats
    print("\n" + "-" * 100)
    print("SUMMARY")
    print("-" * 100)

    stage_counts = {}
    for r in stage_results:
        stage = r['analysis']['stage']
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    print(f"  Stage 2 (Buyable):       {stage_counts.get(2, 0)} stocks")

    if ENABLE_STEP2 and 'sepa_qualified' in locals():
        print(f"  SEPA Qualified:          {len(sepa_qualified)} stocks")
        if 'top_picks' in locals():
            print(f"  Top Picks (actionable):  {len(top_picks)} stocks")

    print(f"  Stage 1 (Consolidation): {stage_counts.get(1, 0)} stocks")
    print(f"  Stage 3 (Topping):       {stage_counts.get(3, 0)} stocks")
    print(f"  Stage 4 (Declining):     {stage_counts.get(4, 0)} stocks")
    print(f"\n  Total with RS >= {MIN_RS_RATING}:    {len(stage_results)} stocks")
    print(f"  Total analyzed:          {len(stock_list)} stocks")

    # ========================================================================
    # Save to CSV
    # ========================================================================
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save comprehensive results
    csv_data = []
    for r in stage_results:
        ticker = r['ticker']
        a = r['analysis']

        row_data = {
            'Ticker': ticker,
            'RS_Rating': a['rs_rating'],
            'RS_Score': r['rs_score'],
            'Stage': a['stage'],
            'Stage_2_Confirmed': a['passes_all_criteria'],
            'Price': a['current_price'],
            'MA_50': a['ma_50'],
            'MA_150': a['ma_150'],
            'MA_200': a['ma_200'],
            'MA_200_Slope': a['ma_200_slope'],
            '52w_High': a['week_52_high'],
            '52w_Low': a['week_52_low'],
            'Pct_Above_52w_Low': a['pct_above_52w_low'],
            'Pct_From_52w_High': a['pct_from_52w_high'],
            'Criteria_Met': sum(a['criteria'].values()),
            'Failed_Criteria': ', '.join([k.split('.')[1].strip() for k, v in a['criteria'].items() if not v])
        }

        # Add fundamental data if available
        if ENABLE_STEP2 and 'fundamentals' in r:
            f = r['fundamentals']
            row_data.update({
                'SEPA_Qualified': f['passes_step2'],
                'Quality_Score': r.get('quality_score'),
                'Grade': r.get('grade'),
                'Earnings_Growth_YoY': f['recent_earnings_growth'],
                'Revenue_Growth_YoY': f['recent_revenue_growth'],
                'Earnings_Accel_Quarters': f['earnings_acceleration_quarters'],
                'Revenue_Accel_Quarters': f['revenue_acceleration_quarters'],
                'ATR_Percent': f['atr_percent'],
                'Net_Margin': f['current_margin'] * 100 if f['current_margin'] else None,
                'SEPA_Failed_Criteria': ', '.join(f['failed_criteria']) if f['failed_criteria'] else None
            })

        # Add enhanced analysis data (NEW)
        if 'entry' in r and r['entry']:
            row_data.update({
                'Entry_Status': r['entry']['entry_status'],
                'EMA_10': r['entry']['ema_10'],
                'EMA_21': r['entry']['ema_21'],
                'Pct_Above_EMA_10': r['entry']['pct_above_ema_10'],
                'Pct_Above_EMA_21': r['entry']['pct_above_ema_21']
            })

        if 'volume' in r and r['volume']:
            row_data.update({
                'Volume_Status': r['volume']['volume_status'],
                'Volume_Ratio': r['volume']['volume_ratio'],
                'Up_Down_Volume_Ratio': r['volume']['up_down_ratio'],
                'Avg_Volume_50d': r['volume']['avg_volume_50d']
            })

        if 'earnings' in r and r['earnings']:
            row_data.update({
                'Earnings_Flag': r['earnings']['earnings_flag'],
                'Days_Until_Earnings': r['earnings']['days_until_earnings'],
                'Next_Earnings_Date': r['earnings']['next_earnings_date'],
                'Last_Earnings_Date': r['earnings'].get('last_earnings_date')
            })

        if 'sector' in r:
            row_data['Sector'] = r['sector']

        csv_data.append(row_data)

    df_output = pd.DataFrame(csv_data)
    # Sort by Quality Score (if available), then SEPA status, then RS Rating
    sort_cols = ['Quality_Score', 'SEPA_Qualified', 'RS_Rating'] if 'Quality_Score' in df_output.columns else ['Stage_2_Confirmed', 'RS_Rating']
    df_output = df_output.sort_values(sort_cols, ascending=[False] * len(sort_cols))

    filename = f"superperform_{timestamp}.csv"
    df_output.to_csv(filename, index=False)
    print(f"\n✓ Results saved to: {filename}")

    # Save SEPA qualified stocks separately
    if ENABLE_STEP2 and 'sepa_qualified' in locals() and len(sepa_qualified) > 0:
        sepa_filename = f"sepa_qualified_{timestamp}.csv"
        df_sepa = df_output[df_output['SEPA_Qualified'] == True]
        df_sepa.to_csv(sepa_filename, index=False)
        print(f"✓ SEPA qualified stocks saved to: {sepa_filename}")

        # Save top picks separately (NEW)
        if 'top_picks' in locals() and len(top_picks) > 0:
            top_picks_tickers = [r['ticker'] for r in top_picks]
            df_top = df_sepa[df_sepa['Ticker'].isin(top_picks_tickers)]
            top_filename = f"top_picks_{timestamp}.csv"
            df_top.to_csv(top_filename, index=False)
            print(f"✓ Top picks saved to: {top_filename}")

    print("\n" + "=" * 100)
    print(f"Market Regime: {market_regime['regime']} | Analysis complete.")
    print("=" * 100)

if __name__ == "__main__":
    main()
