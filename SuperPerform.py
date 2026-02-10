#!/usr/bin/env python3
"""
SuperPerform - Complete Minervini SEPA Analysis
Step 1: IBD RS Rating + Stage 2 Trend Template
Step 2: Fundamental Screening (Earnings/Sales Acceleration, Margins, Volatility)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import json
import re
from pathlib import Path
import time

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_WEB_SCRAPING = True
except ImportError:
    requests = None
    BeautifulSoup = None
    HAS_WEB_SCRAPING = False
    print("WARNING: requests or beautifulsoup4 not installed. Install with: pip install requests beautifulsoup4")

warnings.filterwarnings('ignore')

# Lightweight caches to reduce repeated API calls
_TICKER_CACHE = {}
_HISTORY_CACHE = {}


def get_ticker_obj(ticker):
    """Get cached yfinance Ticker object."""
    ticker = ticker.upper().strip()
    if ticker not in _TICKER_CACHE:
        _TICKER_CACHE[ticker] = yf.Ticker(ticker)
    return _TICKER_CACHE[ticker]


def get_price_history(ticker, period="1y"):
    """Get cached price history and return a copy for safe mutation."""
    ticker = ticker.upper().strip()
    key = (ticker, period)
    if key not in _HISTORY_CACHE:
        stock = get_ticker_obj(ticker)
        history = stock.history(period=period)
        _HISTORY_CACHE[key] = history if history is not None else pd.DataFrame()
    return _HISTORY_CACHE[key].copy()

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
MAX_PCT_ABOVE_50MA = 20.0   # Avoid climactic names too far above intermediate trend
MAX_DAYS_SINCE_52W_HIGH = 126   # 6 months; stale highs are lower quality
MIN_50MA_SLOPE_PCT = 0.0    # 50-day MA should be rising for valid Stage 2 trends
MAX_150MA_ROLLOVER_PCT = 1.0    # 150-day MA can be flat/slightly down, not rolling over hard

# Step 2 Thresholds (SEPA Fundamental Screening)
ENABLE_STEP2 = True         # Set False to skip fundamental screening
MIN_ACCELERATION_QUARTERS = 2   # Quarters showing acceleration (out of last 4)
MIN_EARNINGS_GROWTH = 15.0      # Minimum YoY earnings growth % (recent quarter)
MIN_SALES_GROWTH = 10.0         # Minimum YoY sales growth % (recent quarter)
REQUIRE_MARGIN_EXPANSION = True # Must show margin expansion over 8 quarters
MAX_ATR_PERCENT = 6.0           # Maximum ATR as % of price (lower = smoother trend)
ACCELERATION_MIN_DELTA = 1.5    # Min QoQ improvement in YoY growth series to count acceleration
MIN_YOY_QUARTERS = 5            # Most feeds provide ~4-6 quarters reliably
MIN_YOY_ACCEL_POINTS = 1        # Allow recent IPOs / sparse feeds; use adaptive acceleration check
MIN_POSITIVE_GROWTH_QUARTERS = 1    # Require at least 1 positive YoY quarter (latest 4)
MAX_EARNINGS_SIGN_FLIPS = 2     # Allow some cyclicality; still filter unstable earnings histories

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
MAX_PAGES = 5               # Number of Finviz pages to scrape (v=411: ~1000 stocks/page)
CACHE_HOURS = 24            # Hours to cache Finviz results before re-scraping

# ============================================================================
# FINVIZ SCRAPER
# ============================================================================

def scrape_finviz_screener(max_pages=MAX_PAGES):
    """
    Scrape stock tickers from Finviz screener
    URL criteria: 30%+ above 52w low, Price above 200 MA, 50 MA above 200 MA
    """
    if not HAS_WEB_SCRAPING or requests is None or BeautifulSoup is None:
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

    detected_total = None
    detected_pages = None
    warned_page_limit = False

    for page in range(max_pages):
        # Finviz v=411 pagination uses r=1,1001,2001,...
        start_row = page * 1000 + 1
        url = base_url if start_row == 1 else f"{base_url}&r={start_row}"

        try:
            print(f"  Fetching page {page + 1}...", end=" ")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            page_tickers = []

            # Primary parser: current Finviz screener layout
            for link in soup.select('a.screener-link-primary'):
                ticker = link.get_text(strip=True).upper()
                if re.fullmatch(r"[A-Z][A-Z0-9.\-]*", ticker):
                    page_tickers.append(ticker)

            # Detect total result count from page header, e.g. "#1 / 4224 Total"
            if detected_total is None:
                text_snapshot = soup.get_text(" ", strip=True)
                total_match = re.search(r"#\s*1\s*/\s*([\d,]+)\s+Total", text_snapshot)
                if total_match:
                    detected_total = int(total_match.group(1).replace(',', ''))
                    detected_pages = max(1, int(np.ceil(detected_total / 1000)))
                    print(f"(detected total: {detected_total}, approx pages: {detected_pages})", end=" ")

            # Fallback parser for older/alternate Finviz markup
            if not page_tickers:
                ticker_cells = soup.find_all('td', class_='screener_tickers')
                for cell in ticker_cells:
                    spans = cell.find_all('span')
                    for span in spans:
                        onclick = span.get('onclick')
                        onclick_str = str(onclick) if onclick is not None else ""
                        if 'quote.ashx?t=' in onclick_str:
                            match = re.search(r"t=([A-Z][A-Z0-9.\-]*)", onclick_str)
                            if match:
                                page_tickers.append(match.group(1))

            # Deduplicate while preserving order
            page_tickers = list(dict.fromkeys(page_tickers))
            if not page_tickers:
                print(f"No more results (page {page + 1})")
                break

            new_count = 0
            for ticker in page_tickers:
                if ticker not in tickers:
                    tickers.append(ticker)
                    new_count += 1

            print(f"✓ Found {new_count} new tickers (total: {len(tickers)})")

            if detected_pages and (page + 1) >= detected_pages:
                break

            if detected_pages and max_pages < detected_pages and not warned_page_limit:
                print(f"  [!] max_pages={max_pages} < detected pages={detected_pages}; increase MAX_PAGES for full coverage")
                warned_page_limit = True

            # Be nice to Finviz - add small delay between pages
            if page < max_pages - 1:
                time.sleep(1)

        except Exception as e:
            if requests is not None and isinstance(e, requests.exceptions.RequestException):
                print(f"✗ Error fetching page {page + 1}: {e}")
                if page == 0:
                    # If first page fails, this is a critical error
                    return None
                # If later pages fail, just stop pagination
                break

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
        return list(dict.fromkeys([t.upper().strip() for t in STOCK_LIST if isinstance(t, str) and t.strip()]))

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
                tickers = list(dict.fromkeys([t.upper().strip() for t in tickers if isinstance(t, str) and t.strip()]))

                cache_max_pages = cache_data.get('max_pages', MAX_PAGES)
                cache_parser_version = cache_data.get('parser_version', 1)
                expected_upper_bound = int(max(cache_max_pages, 1) * 1200)
                if cache_parser_version >= 2 and len(tickers) <= expected_upper_bound:
                    print(f"Using cached Finviz tickers ({len(tickers)} stocks)")
                    print(f"  Cache age: {cache_age_hours:.1f} hours (expires in {CACHE_HOURS - cache_age_hours:.1f} hours)")
                    return tickers

                print(f"Cached ticker set looks stale/inconsistent (count={len(tickers)}, parser_v={cache_parser_version}); refreshing cache.")
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
        raise RuntimeError("Failed to fetch stock list from Finviz")

    # Save to cache
    try:
        cache_dir.mkdir(exist_ok=True)
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'tickers': tickers,
            'source': 'finviz_screener',
            'max_pages': MAX_PAGES,
            'parser_version': 2
        }
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
        print(f"✓ Cached results to {cache_file}")
    except Exception as e:
        print(f"Warning: Could not save cache: {e}")

    return list(dict.fromkeys([t.upper().strip() for t in tickers if isinstance(t, str) and t.strip()]))

# ============================================================================
# RS CALCULATION FUNCTIONS
# ============================================================================

def calculate_ibd_rs(ticker, spy_data):
    """
    Calculate IBD-style Relative Strength for a stock
    Formula: 0.4*(3mo) + 0.2*(6mo) + 0.2*(9mo) + 0.2*(12mo)
    """
    try:
        df = get_price_history(ticker, period="1y")

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

    recent_window = ma_values.iloc[-5:]
    older_window = ma_values.iloc[-lookback:-15]
    if len(older_window) == 0:
        return None

    recent_avg = recent_window.mean()
    older_avg = older_window.mean()
    if pd.isna(recent_avg) or pd.isna(older_avg) or older_avg == 0:
        return None

    return (recent_avg - older_avg) / older_avg * 100

def determine_stage(price, ma_50, ma_150, ma_200, ma_50_slope, ma_150_slope, ma_200_slope, pct_from_52w_high, criteria):
    """Determine market stage based on trend structure and momentum."""
    if all(criteria.values()):
        return 2

    # Stage 4: clear long-term downtrend / deterioration
    if (
        price < ma_200 and
        ma_50 < ma_150 and
        ma_150 <= ma_200 and
        (ma_200_slope is None or ma_200_slope <= 0)
    ):
        return 4

    # Stage 3: above long-term MA but intermediate trend is rolling over
    if (
        price > ma_200 and
        (
            price < ma_50 or
            (ma_50_slope is not None and ma_50_slope <= 0) or
            ((ma_150_slope is not None and ma_150_slope <= 0) and pct_from_52w_high > MAX_PCT_FROM_HIGH)
        )
    ):
        return 3

    # Stage 2 candidate: structural uptrend even if strict template not fully met
    if (
        price > ma_200 and
        ma_50 > ma_200 and
        ma_150 > ma_200 and
        (ma_200_slope is not None and ma_200_slope > 0) and
        (ma_50_slope is not None and ma_50_slope > 0)
    ):
        return 2

    # Otherwise treat as Stage 1 (base-building / transition)
    return 1

def analyze_stage(ticker, rs_rating):
    """
    Analyze stock stage using Minervini's Stage 2 Trend Template
    Returns stage number and detailed criteria breakdown
    """
    try:
        df = get_price_history(ticker, period="1y")

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
        ma_50_slope = calculate_ma_slope(df['MA_50'].dropna())
        ma_150_slope = calculate_ma_slope(df['MA_150'].dropna())
        ma_200_slope = calculate_ma_slope(df['MA_200'].dropna())

        # Additional trend-quality metrics for false-positive reduction
        pct_above_ma_50 = ((current_price - ma_50) / ma_50 * 100) if ma_50 else None
        high_values = df['High'].values
        high_positions = np.where(high_values == week_52_high)[0]
        days_since_52w_high = int(len(df) - 1 - high_positions[-1]) if len(high_positions) > 0 else None

        pct_above_52w_low = ((current_price - week_52_low) / week_52_low * 100)
        pct_from_52w_high = ((week_52_high - current_price) / week_52_high * 100)

        # Stage 2 Trend Template - core + quality criteria
        criteria = {
            '1. Price > 150 & 200 MA': current_price > ma_150 and current_price > ma_200,
            '2. 150 MA > 200 MA': ma_150 > ma_200,
            '3. 200 MA trending up': ma_200_slope is not None and ma_200_slope > 0,
            '4. 50 MA > 150 & 200 MA': ma_50 > ma_150 and ma_50 > ma_200,
            '5. Price > 50 MA': current_price > ma_50,
            '6. Price 30%+ above 52w low': pct_above_52w_low >= 30,
            '7. Price within 10% of 52w high': pct_from_52w_high <= MAX_PCT_FROM_HIGH,
            '8. RS Rating >= 80': rs_rating >= MIN_RS_RATING,
            '9. RS not overextended': rs_rating <= MAX_RS_RATING,
            '10. 50 MA trending up': ma_50_slope is not None and ma_50_slope > MIN_50MA_SLOPE_PCT,
            '11. 150 MA not rolling over': ma_150_slope is not None and ma_150_slope > -MAX_150MA_ROLLOVER_PCT,
            '12. Not too extended from 50 MA': pct_above_ma_50 is not None and pct_above_ma_50 <= MAX_PCT_ABOVE_50MA,
            '13. Recent 52w high': days_since_52w_high is not None and days_since_52w_high <= MAX_DAYS_SINCE_52W_HIGH
        }

        stage = determine_stage(
            current_price,
            ma_50,
            ma_150,
            ma_200,
            ma_50_slope,
            ma_150_slope,
            ma_200_slope,
            pct_from_52w_high,
            criteria
        )

        return {
            'stage': stage,
            'criteria': criteria,
            'criteria_count': len(criteria),
            'passes_all_criteria': all(criteria.values()),
            'current_price': current_price,
            'ma_50': ma_50,
            'ma_150': ma_150,
            'ma_200': ma_200,
            'ma_50_slope': ma_50_slope,
            'ma_150_slope': ma_150_slope,
            'ma_200_slope': ma_200_slope,
            'week_52_high': week_52_high,
            'week_52_low': week_52_low,
            'pct_above_52w_low': pct_above_52w_low,
            'pct_from_52w_high': pct_from_52w_high,
            'pct_above_ma_50': pct_above_ma_50,
            'days_since_52w_high': days_since_52w_high,
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

def _normalize_earnings_date(value):
    """Normalize a yfinance earnings date value to datetime.date."""
    if value is None:
        return None

    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
        try:
            return value
        except Exception:
            return None

    if isinstance(value, str):
        parsed = pd.to_datetime(value, errors='coerce')
        if pd.isna(parsed):
            return None
        return parsed.date()

    return None


def _extract_earnings_dates(calendar_data):
    """Extract normalized earnings dates from yfinance calendar payload."""
    if calendar_data is None:
        return []

    raw_values = []

    if isinstance(calendar_data, pd.DataFrame):
        raw_values = calendar_data.values.flatten().tolist()
    elif isinstance(calendar_data, pd.Series):
        raw_values = calendar_data.tolist()
    elif isinstance(calendar_data, dict):
        raw_values = calendar_data.get('Earnings Date') or calendar_data.get('earningsDate') or []
        if not isinstance(raw_values, (list, tuple, pd.Series, np.ndarray)):
            raw_values = [raw_values]
    elif isinstance(calendar_data, (list, tuple, np.ndarray)):
        raw_values = list(calendar_data)
    else:
        raw_values = [calendar_data]

    dates = []
    for raw in raw_values:
        normalized = _normalize_earnings_date(raw)
        if normalized is not None:
            dates.append(normalized)

    return sorted(set(dates))


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
        stock = get_ticker_obj(ticker)
        earnings_dates = _extract_earnings_dates(stock.calendar)

        if not earnings_dates:
            return {
                'next_earnings_date': None,
                'last_earnings_date': None,
                'days_until_earnings': None,
                'earnings_flag': "N/A"
            }

        today = datetime.now().date()
        future_dates = [d for d in earnings_dates if d >= today]
        past_dates = [d for d in earnings_dates if d < today]

        if future_dates:
            next_date = future_dates[0]
            days_until = (next_date - today).days

            if days_until <= EARNINGS_DANGER_DAYS:
                earnings_flag = "DANGER"
            elif days_until <= EARNINGS_CAUTION_DAYS:
                earnings_flag = "CAUTION"
            else:
                earnings_flag = "CLEAR"

            last_date = past_dates[-1] if past_dates else None
            return {
                'next_earnings_date': next_date.strftime('%Y-%m-%d'),
                'last_earnings_date': last_date.strftime('%Y-%m-%d') if last_date else None,
                'days_until_earnings': days_until,
                'earnings_flag': earnings_flag
            }

        # Only past dates available - next earnings not scheduled yet
        return {
            'next_earnings_date': None,
            'last_earnings_date': past_dates[-1].strftime('%Y-%m-%d') if past_dates else None,
            'days_until_earnings': None,
            'earnings_flag': "REPORTED"
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
        stock = get_ticker_obj(ticker)
        info = stock.info
        sector = info.get('sector', 'Unknown') if isinstance(info, dict) else 'Unknown'
        return sector or 'Unknown'
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


def is_operating_company(info):
    """Return (is_operating_company, reason)."""
    if not isinstance(info, dict):
        return True, None

    quote_type = str(info.get('quoteType', '')).upper()
    if quote_type in {'ETF', 'ETN', 'MUTUALFUND', 'FUND', 'INDEX', 'CRYPTO'}:
        return False, f"Non-operating security ({quote_type})"

    category = str(info.get('category', '')).upper()
    if any(token in category for token in ['ETF', 'FUND', 'INDEX']):
        return False, "Non-operating security (fund/index category)"

    name = f"{info.get('shortName', '')} {info.get('longName', '')}".upper()
    if any(token in name for token in [' ETF', ' ETN', ' FUND', ' TRUST']):
        return False, "Non-operating security (name pattern)"

    return True, None

# ============================================================================
# STEP 2: FUNDAMENTAL SCREENING (SEPA)
# ============================================================================

def calculate_atr_percent(ticker):
    """Calculate Average True Range as percentage of price"""
    try:
        df = get_price_history(ticker, period="3mo")

        if len(df) < 20:
            return None

        # Calculate True Range
        df['H-L'] = df['High'] - df['Low']
        df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
        df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
        df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)

        # ATR is 14-period average of True Range
        atr = df['TR'].rolling(window=14).mean().dropna()
        if atr.empty:
            return None

        atr_value = atr.iloc[-1]
        current_price = df['Close'].iloc[-1]
        if current_price == 0 or pd.isna(current_price):
            return None

        atr_percent = (atr_value / current_price) * 100
        return atr_percent

    except Exception:
        return None

def calculate_yoy_growth_series(values, max_points=4):
    """
    Build YoY growth series from quarterly values sorted most-recent first.
    Example: Q4'25 vs Q4'24, Q3'25 vs Q3'24, ...
    """
    if not isinstance(values, pd.Series) or len(values) < 5:
        return []

    growth_rates = []
    max_idx = min(len(values) - 4, max_points)

    for i in range(max_idx):
        current_val = values.iloc[i]
        year_ago_val = values.iloc[i + 4]

        if pd.isna(current_val) or pd.isna(year_ago_val) or year_ago_val == 0:
            continue

        growth = ((current_val - year_ago_val) / abs(year_ago_val)) * 100
        growth_rates.append(float(growth))

    return growth_rates


def check_acceleration(yoy_growth_rates, min_delta=ACCELERATION_MIN_DELTA):
    """
    Count accelerating quarters in the YoY growth series.
    Uses chronological order and requires a minimum delta to avoid noise.
    """
    if len(yoy_growth_rates) < 2:
        return 0

    chronological = list(reversed(yoy_growth_rates[:4]))
    acceleration_count = 0

    for i in range(1, len(chronological)):
        if (chronological[i] - chronological[i - 1]) >= min_delta:
            acceleration_count += 1

    return acceleration_count


def count_positive_growth_quarters(yoy_growth_rates, lookback=4):
    """Count positive YoY growth quarters in the recent series."""
    recent = yoy_growth_rates[:lookback]
    return sum(1 for g in recent if g > 0)


def count_sign_flips(values, lookback=8):
    """Count profit/loss sign flips in recent quarterly values."""
    if not isinstance(values, pd.Series):
        return 0

    recent_values = values.head(lookback).tolist()
    cleaned = [v for v in recent_values if not pd.isna(v) and v != 0]
    if len(cleaned) < 2:
        return 0

    flips = 0
    prev_sign = 1 if cleaned[0] > 0 else -1
    for value in cleaned[1:]:
        curr_sign = 1 if value > 0 else -1
        if curr_sign != prev_sign:
            flips += 1
        prev_sign = curr_sign

    return flips

def analyze_fundamentals(ticker):
    """
    Analyze quarterly earnings, sales, and margins for acceleration
    Returns dict with fundamental metrics and pass/fail for Step 2
    """
    try:
        stock = get_ticker_obj(ticker)

        info = {}
        try:
            info = stock.info or {}
        except Exception:
            info = {}

        is_company, skip_reason = is_operating_company(info)
        if not is_company:
            return None, skip_reason

        # Get quarterly income statement (contains both revenue and net income rows)
        quarterly_income = stock.quarterly_income_stmt
        if quarterly_income is None or quarterly_income.empty:
            return None, "Insufficient quarterly data"

        # Get quarterly earnings (try multiple possible field names)
        earnings_fields = [
            'Net Income',
            'NetIncome',
            'Net Income Common Stockholders',
            'NetIncomeCommonStockholders'
        ]
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

        if isinstance(eps_data, pd.DataFrame):
            eps_data = eps_data.iloc[0]
        if isinstance(revenue_data, pd.DataFrame):
            revenue_data = revenue_data.iloc[0]

        eps_clean = pd.Series(dtype=float)
        revenue_clean = pd.Series(dtype=float)

        if isinstance(eps_data, pd.Series):
            eps_clean = pd.to_numeric(eps_data, errors='coerce').dropna().sort_index(ascending=False)
        if isinstance(revenue_data, pd.Series):
            revenue_clean = pd.to_numeric(revenue_data, errors='coerce').dropna().sort_index(ascending=False)

        current_margin = info.get('profitMargins', None) if isinstance(info, dict) else None
        if isinstance(current_margin, (pd.Series, pd.DataFrame, np.ndarray, list, tuple, dict)):
            current_margin = None
        elif isinstance(current_margin, (int, float, np.floating)):
            if np.isnan(current_margin):
                current_margin = None
        elif current_margin is not None:
            current_margin = None

        # Calculate growth rates and acceleration
        results = {
            'has_earnings_data': len(eps_clean) >= MIN_YOY_QUARTERS,
            'has_revenue_data': len(revenue_clean) >= MIN_YOY_QUARTERS,
            'earnings_acceleration_quarters': 0,
            'revenue_acceleration_quarters': 0,
            'earnings_yoy_growth_series': [],
            'revenue_yoy_growth_series': [],
            'positive_earnings_growth_quarters': 0,
            'positive_revenue_growth_quarters': 0,
            'earnings_sign_flips': 0,
            'margin_expansion': False,
            'recent_earnings_growth': None,
            'recent_revenue_growth': None,
            'current_margin': current_margin,
            'recent_net_margin': None,
            'prior_net_margin': None,
            'atr_percent': calculate_atr_percent(ticker)
        }

        # Check earnings acceleration
        if results['has_earnings_data']:
            eps_yoy = calculate_yoy_growth_series(eps_clean, max_points=4)
            results['earnings_yoy_growth_series'] = eps_yoy
            if len(eps_yoy) > 0:
                results['recent_earnings_growth'] = eps_yoy[0]
            results['earnings_acceleration_quarters'] = check_acceleration(eps_yoy)
            results['positive_earnings_growth_quarters'] = count_positive_growth_quarters(eps_yoy)
            results['earnings_sign_flips'] = count_sign_flips(eps_clean)

        # Check revenue acceleration
        if results['has_revenue_data']:
            revenue_yoy = calculate_yoy_growth_series(revenue_clean, max_points=4)
            results['revenue_yoy_growth_series'] = revenue_yoy
            if len(revenue_yoy) > 0:
                results['recent_revenue_growth'] = revenue_yoy[0]
            results['revenue_acceleration_quarters'] = check_acceleration(revenue_yoy)
            results['positive_revenue_growth_quarters'] = count_positive_growth_quarters(revenue_yoy)

        # Check margin expansion using derived quarterly net margins
        if results['has_earnings_data'] and results['has_revenue_data']:
            margin_df = pd.concat([
                eps_clean.rename('net_income'),
                revenue_clean.rename('revenue')
            ], axis=1).dropna()
            margin_df = margin_df[margin_df['revenue'] != 0].sort_index(ascending=False)

            recent_margin = None
            older_margin = None

            if len(margin_df) >= 8:
                recent_margin = (margin_df['net_income'].iloc[:4] / margin_df['revenue'].iloc[:4]).mean()
                older_margin = (margin_df['net_income'].iloc[4:8] / margin_df['revenue'].iloc[4:8]).mean()
            elif len(margin_df) >= 5:
                recent_margin = margin_df['net_income'].iloc[0] / margin_df['revenue'].iloc[0]
                older_margin = margin_df['net_income'].iloc[4] / margin_df['revenue'].iloc[4]

            if recent_margin is not None and older_margin is not None and not pd.isna(recent_margin) and not pd.isna(older_margin):
                results['margin_expansion'] = recent_margin > older_margin
                results['recent_net_margin'] = recent_margin * 100
                results['prior_net_margin'] = older_margin * 100

                # Fallback to derived current margin if info endpoint is missing
                if results['current_margin'] is None:
                    results['current_margin'] = recent_margin

        # Determine if passes Step 2 criteria
        passes_step2 = True
        failed_criteria = []

        if not results['has_earnings_data']:
            passes_step2 = False
            failed_criteria.append(f"Missing earnings data (need {MIN_YOY_QUARTERS}+ quarters)")

        if not results['has_revenue_data']:
            passes_step2 = False
            failed_criteria.append(f"Missing revenue data (need {MIN_YOY_QUARTERS}+ quarters)")

        if results['has_earnings_data'] and len(results['earnings_yoy_growth_series']) < MIN_YOY_ACCEL_POINTS:
            passes_step2 = False
            failed_criteria.append(f"Insufficient earnings YoY history ({len(results['earnings_yoy_growth_series'])}/{MIN_YOY_ACCEL_POINTS})")

        if results['has_revenue_data'] and len(results['revenue_yoy_growth_series']) < MIN_YOY_ACCEL_POINTS:
            passes_step2 = False
            failed_criteria.append(f"Insufficient revenue YoY history ({len(results['revenue_yoy_growth_series'])}/{MIN_YOY_ACCEL_POINTS})")

        required_earn_accel = min(MIN_ACCELERATION_QUARTERS, max(0, len(results['earnings_yoy_growth_series']) - 1))
        required_rev_accel = min(MIN_ACCELERATION_QUARTERS, max(0, len(results['revenue_yoy_growth_series']) - 1))

        # Check earnings acceleration
        if results['has_earnings_data'] and required_earn_accel > 0 and results['earnings_acceleration_quarters'] < required_earn_accel:
            passes_step2 = False
            failed_criteria.append(f"Earnings acceleration ({results['earnings_acceleration_quarters']}/{required_earn_accel} quarters)")

        # Check revenue acceleration
        if results['has_revenue_data'] and required_rev_accel > 0 and results['revenue_acceleration_quarters'] < required_rev_accel:
            passes_step2 = False
            failed_criteria.append(f"Revenue acceleration ({results['revenue_acceleration_quarters']}/{required_rev_accel} quarters)")

        # Check minimum growth rates
        if results['recent_earnings_growth'] is None:
            passes_step2 = False
            failed_criteria.append("Earnings growth unavailable")
        elif results['recent_earnings_growth'] < MIN_EARNINGS_GROWTH:
            passes_step2 = False
            failed_criteria.append(f"Earnings growth ({results['recent_earnings_growth']:.1f}% < {MIN_EARNINGS_GROWTH}%)")

        if results['recent_revenue_growth'] is None:
            passes_step2 = False
            failed_criteria.append("Revenue growth unavailable")
        elif results['recent_revenue_growth'] < MIN_SALES_GROWTH:
            passes_step2 = False
            failed_criteria.append(f"Revenue growth ({results['recent_revenue_growth']:.1f}% < {MIN_SALES_GROWTH}%)")

        if results['positive_earnings_growth_quarters'] < MIN_POSITIVE_GROWTH_QUARTERS:
            passes_step2 = False
            failed_criteria.append(f"Earnings consistency ({results['positive_earnings_growth_quarters']}/{MIN_POSITIVE_GROWTH_QUARTERS} positive YoY quarters)")

        if results['positive_revenue_growth_quarters'] < MIN_POSITIVE_GROWTH_QUARTERS:
            passes_step2 = False
            failed_criteria.append(f"Revenue consistency ({results['positive_revenue_growth_quarters']}/{MIN_POSITIVE_GROWTH_QUARTERS} positive YoY quarters)")

        if results['earnings_sign_flips'] > MAX_EARNINGS_SIGN_FLIPS:
            passes_step2 = False
            failed_criteria.append(f"Unstable earnings ({results['earnings_sign_flips']} profit/loss sign flips)")

        if REQUIRE_MARGIN_EXPANSION and not results['margin_expansion']:
            passes_step2 = False
            failed_criteria.append("No margin expansion")

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

    # 5. Earnings/Revenue Acceleration (15 pts max combined)
    ea = fundamentals.get('earnings_acceleration_quarters', 0)
    if ea >= 3:
        score += 8
    elif ea >= 2:
        score += 4

    ra = fundamentals.get('revenue_acceleration_quarters', 0)
    if ra >= 3:
        score += 7
    elif ra >= 2:
        score += 3

    # 6. Stability penalties/bonuses (false-positive reduction)
    sign_flips = fundamentals.get('earnings_sign_flips', 0)
    if sign_flips > 0:
        score -= min(15, sign_flips * 7)

    if fundamentals.get('positive_earnings_growth_quarters', 0) >= 3:
        score += 3

    if fundamentals.get('positive_revenue_growth_quarters', 0) >= 3:
        score += 2

    score = max(0, min(100, score))

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

    sepa_qualified = []
    sector_analysis = None
    top_picks = []

    # Get stock list (from Finviz or hardcoded)
    try:
        stock_list = get_stock_list()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return

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
        spy_data = get_price_history("SPY", period="1y")

        if spy_data is None or len(spy_data) == 0:
            print("ERROR: Could not fetch SPY data. Exiting.")
            return

        start_date = pd.to_datetime(spy_data.index[0]).date()
        end_date = pd.to_datetime(spy_data.index[-1]).date()
        print(f"✓ Downloaded {len(spy_data)} days of SPY data")
        print(f"  Date range: {start_date} to {end_date}\n")

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
    df_rs['RS Rating'] = np.nan
    valid_mask = df_rs['RS Score'].notna()
    if len(df_rs.loc[valid_mask]) > 0:
        percentile_ranks = df_rs.loc[valid_mask, 'RS Score'].rank(pct=True, method='max')
        rs_ratings = np.ceil(percentile_ranks * 99).clip(lower=1, upper=99).astype(int)
        df_rs.loc[valid_mask, 'RS Rating'] = rs_ratings

    # Filter stocks by RS rating
    high_rs_stocks = df_rs[df_rs['RS Rating'] >= MIN_RS_RATING].sort_values(by='RS Rating', ascending=False)

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
    criteria_count = len(stage_2_stocks[0]['analysis']['criteria']) if stage_2_stocks else 0
    print(f"  • {len(stage_2_stocks)} stocks meet all {criteria_count} Stage 2 criteria")

    # ========================================================================
    # STEP 3: Fundamental Screening (SEPA Step 2)
    # ========================================================================
    if ENABLE_STEP2 and len(stage_2_stocks) > 0:
        print("\n" + "─" * 100)
        print("STEP 3: FUNDAMENTAL SCREENING (SEPA STEP 2)")
        print("─" * 100)
        print(f"\nAnalyzing fundamentals for {len(stage_2_stocks)} Stage 2 stocks...")
        print("Checking: YoY acceleration, growth consistency, margins, and volatility\n")

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
    if ENABLE_STEP2 and len(sepa_qualified) > 0:
        print("\n" + "-" * 100)
        print("STEP 4: ENHANCED ANALYSIS (Entry, Volume, Earnings, Sector)")
        print("-" * 100)
        print(f"\nAnalyzing {len(sepa_qualified)} SEPA qualified stocks for entry timing...\n")

        for i, result in enumerate(sepa_qualified, 1):
            ticker = result['ticker']
            print(f"[{i}/{len(sepa_qualified)}] {ticker}...", end=" ")

            # Get fresh price data for entry/volume analysis
            try:
                df = get_price_history(ticker, period="3mo")

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

    # TOP PICKS Section - stricter false-positive filters
    if ENABLE_STEP2 and len(sepa_qualified) > 0:
        market_allows_new_longs = market_regime['regime'] != "BEARISH"
        top_picks = [r for r in sepa_qualified if
                     r.get('grade') in ['A', 'B'] and
                     r.get('entry', {}).get('entry_status') == 'BUY_ZONE' and
                     r.get('volume', {}).get('volume_status') != 'WEAK' and
                     r.get('earnings', {}).get('earnings_flag') in ['CLEAR', 'REPORTED'] and
                     r.get('analysis', {}).get('pct_above_ma_50') is not None and
                     r.get('analysis', {}).get('pct_above_ma_50') <= MAX_PCT_ABOVE_50MA]

        if not market_allows_new_longs:
            top_picks = []

        if top_picks:
            print("\n" + "-" * 100)
            print("TOP PICKS - Ready to Buy (Grade A/B, Buy Zone, Healthy Volume, Earnings Clear)")
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
        if sector_analysis:
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

    if ENABLE_STEP2:
        print(f"  SEPA Qualified:          {len(sepa_qualified)} stocks")
        if top_picks:
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
            'MA_50_Slope': a.get('ma_50_slope'),
            'MA_150_Slope': a.get('ma_150_slope'),
            'MA_200_Slope': a['ma_200_slope'],
            '52w_High': a['week_52_high'],
            '52w_Low': a['week_52_low'],
            'Pct_Above_52w_Low': a['pct_above_52w_low'],
            'Pct_From_52w_High': a['pct_from_52w_high'],
            'Pct_Above_MA_50': a.get('pct_above_ma_50'),
            'Days_Since_52w_High': a.get('days_since_52w_high'),
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
                'Positive_Earnings_Growth_Quarters': f.get('positive_earnings_growth_quarters'),
                'Positive_Revenue_Growth_Quarters': f.get('positive_revenue_growth_quarters'),
                'Earnings_Sign_Flips': f.get('earnings_sign_flips'),
                'ATR_Percent': f['atr_percent'],
                'Net_Margin': f['current_margin'] * 100 if f.get('current_margin') is not None else None,
                'Recent_Net_Margin': f.get('recent_net_margin'),
                'Prior_Net_Margin': f.get('prior_net_margin'),
                'Earnings_YoY_Series': ', '.join([f"{x:.1f}" for x in f.get('earnings_yoy_growth_series', [])]),
                'Revenue_YoY_Series': ', '.join([f"{x:.1f}" for x in f.get('revenue_yoy_growth_series', [])]),
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
    if ENABLE_STEP2 and len(sepa_qualified) > 0:
        sepa_filename = f"sepa_qualified_{timestamp}.csv"
        df_sepa = df_output[df_output['SEPA_Qualified'] == True].copy()
        df_sepa.to_csv(sepa_filename, index=False)
        print(f"✓ SEPA qualified stocks saved to: {sepa_filename}")

        # Save top picks separately (NEW)
        if len(top_picks) > 0:
            top_picks_tickers = [r['ticker'] for r in top_picks]
            df_top = df_sepa[df_sepa['Ticker'].isin(top_picks_tickers)].copy()
            top_filename = f"top_picks_{timestamp}.csv"
            df_top.to_csv(top_filename, index=False)
            print(f"✓ Top picks saved to: {top_filename}")

    print("\n" + "=" * 100)
    print(f"Market Regime: {market_regime['regime']} | Analysis complete.")
    print("=" * 100)

if __name__ == "__main__":
    main()
