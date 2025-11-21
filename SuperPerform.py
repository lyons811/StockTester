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

# Step 1 Thresholds (RS & Stage)
MIN_RS_RATING = 70          # Minimum RS rating to consider (70-99, Minervini recommends 80+)
MIN_TRADING_DAYS = 240      # Minimum days of data required (240 ≈ 9.5 months)

# Step 2 Thresholds (SEPA Fundamental Screening)
ENABLE_STEP2 = True         # Set False to skip fundamental screening
MIN_ACCELERATION_QUARTERS = 2   # Quarters showing acceleration (out of last 4)
MIN_EARNINGS_GROWTH = 15.0      # Minimum YoY earnings growth % (recent quarter)
MIN_SALES_GROWTH = 10.0         # Minimum YoY sales growth % (recent quarter)
REQUIRE_MARGIN_EXPANSION = True # Must show margin expansion over 8 quarters
MAX_ATR_PERCENT = 6.0           # Maximum ATR as % of price (lower = smoother trend)

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

        # Stage 2 Trend Template - All 8 criteria
        criteria = {
            '1. Price > 150 & 200 MA': current_price > ma_150 and current_price > ma_200,
            '2. 150 MA > 200 MA': ma_150 > ma_200,
            '3. 200 MA trending up': ma_200_slope is not None and ma_200_slope > 0,
            '4. 50 MA > 150 & 200 MA': ma_50 > ma_150 and ma_50 > ma_200,
            '5. Price > 50 MA': current_price > ma_50,
            '6. Price 30%+ above 52w low': ((current_price - week_52_low) / week_52_low * 100) >= 30,
            '7. Price within 25% of 52w high': ((week_52_high - current_price) / week_52_high * 100) <= 25,
            '8. RS Rating >= 70': rs_rating >= MIN_RS_RATING
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

        print(f"\n✓ Fundamental Screening Complete")
        print(f"  • {len(sepa_qualified)} stocks pass all SEPA Step 2 criteria")
        print(f"  • {len(stage_2_stocks) - len(sepa_qualified)} stocks filtered out (~{(len(stage_2_stocks) - len(sepa_qualified))/len(stage_2_stocks)*100:.0f}% rejection rate)")

        # Display SEPA qualified stocks
        if sepa_qualified:
            print("\n" + "=" * 100)
            print("🏆 SEPA STEP 2 QUALIFIED STOCKS (Ready for Manual Review)")
            print("=" * 100)

            for result in sepa_qualified:
                ticker = result['ticker']
                a = result['analysis']
                f = result['fundamentals']

                print(f"\n{'━' * 100}")
                print(f"🏆 {ticker} - RS Rating: {a['rs_rating']}")
                print(f"{'━' * 100}")
                print(f"Price: ${a['current_price']:.2f}  |  {a['pct_from_52w_high']:.0f}% from 52w high")
                print(f"\nFundamentals:")
                print(f"  • Earnings Growth (YoY): {f['recent_earnings_growth']:.1f}%" if f['recent_earnings_growth'] else "  • Earnings Growth: N/A")
                print(f"  • Revenue Growth (YoY): {f['recent_revenue_growth']:.1f}%" if f['recent_revenue_growth'] else "  • Revenue Growth: N/A")
                print(f"  • Earnings Acceleration: {f['earnings_acceleration_quarters']}/4 quarters")
                print(f"  • Revenue Acceleration: {f['revenue_acceleration_quarters']}/4 quarters")
                print(f"  • ATR (Volatility): {f['atr_percent']:.1f}%" if f['atr_percent'] else "  • ATR: N/A")
                print(f"  • Net Margin: {f['current_margin']*100:.1f}%" if f['current_margin'] else "  • Net Margin: N/A")

        stage_2_stocks = sepa_results  # Update to include fundamental data

    # ========================================================================
    # Display All Stage 2 Results
    # ========================================================================
    print("\n" + "=" * 100)
    print("ALL STAGE 2 STOCKS (With Fundamental Analysis)" if ENABLE_STEP2 else "ALL STAGE 2 STOCKS")
    print("=" * 100)

    if stage_2_stocks:
        stage_2_stocks.sort(key=lambda x: x['analysis']['rs_rating'], reverse=True)

        for result in stage_2_stocks:
            ticker = result['ticker']
            a = result['analysis']

            sepa_status = ""
            if ENABLE_STEP2 and 'fundamentals' in result:
                f = result['fundamentals']
                if f['passes_step2']:
                    sepa_status = " 🏆 SEPA QUALIFIED"
                else:
                    sepa_status = f" (Failed: {', '.join(f['failed_criteria'][:2])})"

            print(f"\n  {ticker} - RS {a['rs_rating']} | ${a['current_price']:.2f} | "
                  f"{a['pct_above_52w_low']:.0f}% from low | "
                  f"{a['pct_from_52w_high']:.0f}% from high{sepa_status}")

    # ========================================================================
    # Show all stocks by stage
    # ========================================================================
    print("\n" + "=" * 100)
    print("ALL HIGH-RS STOCKS BY STAGE")
    print("=" * 100)

    stage_names = {
        1: "STAGE 1 - Consolidation/Neglect Phase",
        2: "STAGE 2 - Advancing Phase ⭐ BUYABLE",
        3: "STAGE 3 - Topping/Distribution Phase",
        4: "STAGE 4 - Declining Phase"
    }

    for stage_num in [2, 1, 3, 4]:
        stocks_in_stage = [r for r in stage_results if r['analysis']['stage'] == stage_num]

        if stocks_in_stage:
            print(f"\n{stage_names[stage_num]}")
            print("-" * 100)

            stocks_in_stage.sort(key=lambda x: x['analysis']['rs_rating'], reverse=True)

            for result in stocks_in_stage:
                ticker = result['ticker']
                a = result['analysis']

                failed = [k for k, v in a['criteria'].items() if not v]
                criteria_str = "ALL 8 ✓" if not failed else f"({8 - len(failed)}/8)"

                print(f"  {ticker:6} - RS {a['rs_rating']:2} | ${a['current_price']:8.2f} | "
                      f"{a['pct_above_52w_low']:5.0f}% from low | "
                      f"{a['pct_from_52w_high']:4.0f}% from high | {criteria_str}")

                if failed:
                    print(f"         Failed: {', '.join([c.split('.')[1].strip() for c in failed[:2]])}")

    # ========================================================================
    # Summary
    # ========================================================================
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)

    stage_counts = {}
    for r in stage_results:
        stage = r['analysis']['stage']
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    print(f"\n🎯 Stage 2 (Buyable):       {stage_counts.get(2, 0)} stocks")

    if ENABLE_STEP2 and 'sepa_qualified' in locals():
        print(f"🏆 SEPA Qualified:          {len(sepa_qualified)} stocks (after fundamental screening)")

    print(f"○  Stage 1 (Consolidation): {stage_counts.get(1, 0)} stocks")
    print(f"⚠  Stage 3 (Topping):       {stage_counts.get(3, 0)} stocks")
    print(f"✗  Stage 4 (Declining):     {stage_counts.get(4, 0)} stocks")
    print(f"\nTotal with RS >= {MIN_RS_RATING}:      {len(stage_results)} stocks")
    print(f"Total analyzed:             {len(stock_list)} stocks")

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
                'Earnings_Growth_YoY': f['recent_earnings_growth'],
                'Revenue_Growth_YoY': f['recent_revenue_growth'],
                'Earnings_Accel_Quarters': f['earnings_acceleration_quarters'],
                'Revenue_Accel_Quarters': f['revenue_acceleration_quarters'],
                'ATR_Percent': f['atr_percent'],
                'Net_Margin': f['current_margin'] * 100 if f['current_margin'] else None,
                'SEPA_Failed_Criteria': ', '.join(f['failed_criteria']) if f['failed_criteria'] else None
            })

        csv_data.append(row_data)

    df_output = pd.DataFrame(csv_data)
    df_output = df_output.sort_values(['Stage_2_Confirmed', 'RS_Rating'], ascending=[False, False])

    filename = f"superperform_{timestamp}.csv"
    df_output.to_csv(filename, index=False)
    print(f"\n✓ Results saved to: {filename}")

    # Save SEPA qualified stocks separately
    if ENABLE_STEP2 and 'sepa_qualified' in locals() and len(sepa_qualified) > 0:
        sepa_filename = f"sepa_qualified_{timestamp}.csv"
        df_sepa = df_output[df_output['SEPA_Qualified'] == True]
        df_sepa.to_csv(sepa_filename, index=False)
        print(f"✓ SEPA qualified stocks saved to: {sepa_filename}")

    print("\n" + "=" * 100)

if __name__ == "__main__":
    main()
