# SuperPerform - Minervini SEPA Stock Analyzer

A Python implementation of Mark Minervini's **SEPA (Specific Entry Point Analysis)** methodology from the book *"Trade Like a Stock Market Wizard"*. This tool automates the multi-step screening process to identify high-potential stock candidates that meet Minervini's strict criteria for superperformance.

## What It Does

SuperPerform automates the complete SEPA analysis process:

### Step 1: Relative Strength (RS) Rating
- Calculates IBD-style relative strength ratings for all stocks
- Formula: `0.4*(3mo) + 0.2*(6mo) + 0.2*(9mo) + 0.2*(12mo)`
- Compares stock performance against S&P 500 (SPY)
- Filters to stocks with RS ≥ 70 (configurable)

### Step 2: Stage 2 Trend Template (8 Criteria)
Validates all 8 of Minervini's Stage 2 criteria:
1. Price above both 150-day and 200-day moving averages
2. 150-day MA above 200-day MA
3. 200-day MA trending up for 1+ months
4. 50-day MA above both 150-day and 200-day MAs
5. Price above 50-day MA
6. Price at least 30% above 52-week low
7. Price within 25% of 52-week high
8. RS Rating ≥ 70

### Step 3: Fundamental Screening (SEPA Step 2)
Analyzes quarterly financials for growth acceleration:
- **Earnings Acceleration**: Quarter-over-quarter growth improvement
- **Revenue Acceleration**: Consistent sales growth acceleration
- **Margin Expansion**: Net profit margin trending up
- **Price Volatility**: ATR analysis for trend smoothness
- **~95% rejection rate** (matches Minervini's description)

### Result: SEPA Qualified Stocks
Stocks that pass all criteria are ready for manual review (SEPA Step 4), where you analyze:
- Catalysts (new products, FDA approvals, etc.)
- Entry points (VCP patterns, pullbacks)
- Company fundamentals and guidance
- Sector strength

## Features

- **Automatic Finviz Scraping**: Fetches stocks from Finviz screener (configurable filters)
- **24-Hour Caching**: Saves scraped tickers to avoid re-scraping
- **Comprehensive Analysis**: RS ratings, Stage analysis, and fundamental screening
- **Historical Backtesting**: Validate SEPA methodology with 2 years of historical data
- **Multiple CSV Outputs**:
  - `superperform_TIMESTAMP.csv` - All results with detailed metrics
  - `sepa_qualified_TIMESTAMP.csv` - Only elite stocks that passed all filters
  - `backtest_results_TIMESTAMP.csv` - Historical backtest results
- **Configurable Thresholds**: Easily adjust screening parameters
- **Progress Tracking**: Real-time feedback during analysis
- **Parallel Processing**: Multi-core support for faster backtesting

## Installation

1. **Clone or download** this repository

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the analyzer**:
   ```bash
   python SuperPerform.py
   ```

4. **Run the backtester** (optional - validates methodology):
   ```bash
   python SEPABacktester.py
   ```

## Configuration

Edit the configuration section at the top of `SuperPerform.py`:

### Stock Source
```python
USE_FINVIZ_SCRAPER = True   # Set False to use hardcoded STOCK_LIST
MAX_PAGES = 4               # Number of Finviz pages to scrape
CACHE_HOURS = 24            # Cache duration before re-scraping
```

### Step 1: RS & Stage Thresholds
```python
MIN_RS_RATING = 70          # Minimum RS rating (70-99)
MIN_TRADING_DAYS = 240      # Minimum data required (~9.5 months)
```

### Step 2: Fundamental Screening
```python
ENABLE_STEP2 = True                 # Toggle fundamental screening
MIN_ACCELERATION_QUARTERS = 2       # Quarters showing acceleration (out of 4)
MIN_EARNINGS_GROWTH = 15.0          # Minimum YoY earnings growth %
MIN_SALES_GROWTH = 10.0             # Minimum YoY sales growth %
MAX_ATR_PERCENT = 6.0               # Maximum volatility (lower = smoother)
```

### Finviz Screener URL
To change the Finviz screener criteria:
1. Go to [Finviz Screener](https://finviz.com/screener.ashx)
2. Set your filters (current default: 30%+ above 52w low, Price > 200MA, 50MA > 200MA)
3. Copy the URL
4. Update line 75 in `SuperPerform.py`:
   ```python
   base_url = "https://finviz.com/screener.ashx?v=411&f=YOUR_FILTERS"
   ```

### Manual Stock List
If you prefer to analyze a specific list of stocks:
1. Set `USE_FINVIZ_SCRAPER = False`
2. Update the `STOCK_LIST` array (lines 19-26):
   ```python
   STOCK_LIST = [
       "AAPL", "MSFT", "GOOGL", ...
   ]
   ```

## Output Explained

### Terminal Output

```
SUPERPERFORM - COMPLETE MINERVINI SEPA ANALYSIS
====================================================================================================

Configuration:
  • Analyzing 80 stocks
  • Stock Source: Finviz Screener
  • Minimum RS Rating: 70
  • Step 2 Screening: ENABLED

STEP 1: CALCULATING RELATIVE STRENGTH RATINGS
  [1/80] Processing AAPL... ✓
  ...
  • 14 stocks with RS >= 70

STEP 2: STAGE ANALYSIS FOR HIGH RS STOCKS
  [1/14] Analyzing AAPL (RS=99)... ✓ STAGE 2
  ...
  • 10 stocks meet all 8 Stage 2 criteria

STEP 3: FUNDAMENTAL SCREENING (SEPA STEP 2)
  [1/10] AAPL... ✓ SEPA QUALIFIED
  [2/10] MSFT... ✗ (Revenue acceleration (1/2 quarters))
  ...
  • 3 stocks pass all SEPA Step 2 criteria
  • 7 stocks filtered out (~70% rejection rate)

SEPA STEP 2 QUALIFIED STOCKS (Ready for Manual Review)
  AAPL - RS 99 | $150.00 | 5% from 52w high
    • Earnings Growth (YoY): 25.3%
    • Revenue Growth (YoY): 18.2%
    • Earnings Acceleration: 3/4 quarters
    • Revenue Acceleration: 2/4 quarters
    • ATR (Volatility): 2.1%
    • Net Margin: 24.5%
```

### CSV Files

**superperform_TIMESTAMP.csv** contains:
- Ticker symbol
- RS Rating and Score
- Stage (1-4)
- Current price and moving averages
- 52-week high/low metrics
- Stage 2 criteria pass/fail
- Fundamental metrics (if Step 2 enabled)
- SEPA qualification status

**sepa_qualified_TIMESTAMP.csv** contains:
- Only stocks that passed ALL criteria
- Ready for manual review and entry point analysis

## Cache Management

Scraped tickers are cached in `cache/finviz_tickers.json` for 24 hours.

**To force a fresh scrape:**
1. Delete the cache file: `rm cache/finviz_tickers.json`
2. Or wait 24 hours for automatic cache expiration

**Cache file format:**
```json
{
  "timestamp": "2025-11-21T10:30:00",
  "tickers": ["AAPL", "MSFT", ...],
  "source": "finviz_screener",
  "max_pages": 4
}
```

## Understanding the Methodology

### Why This Matters

Mark Minervini's SEPA process is designed to identify stocks with the highest probability of becoming superperformers (100-300%+ gains). The multi-step filtering dramatically narrows down thousands of stocks to a small handful of elite candidates.

**Key Principles:**
1. **Stage 2 = Buyable**: Only buy stocks in Stage 2 uptrends
2. **Acceleration Matters**: Look for earnings/sales growth that's INCREASING, not just positive
3. **Relative Strength**: Best stocks outperform the market by wide margins
4. **Low Volatility**: Smooth, steady uptrends indicate institutional accumulation
5. **95% Fail**: Most stocks fail fundamental screening - that's the point!

### The Four Market Stages

- **Stage 1**: Consolidation/Neglect - sideways movement, building base
- **Stage 2**: Advancing - strong uptrend, institutional buying (BUY HERE)
- **Stage 3**: Topping/Distribution - volatile, erratic swings (SELL HERE)
- **Stage 4**: Declining - downtrend, lower lows (AVOID)

### Why Acceleration Beats Growth

A stock with 10% → 15% → 22% → 35% earnings growth (accelerating) is far more powerful than one with 40% → 38% → 35% (decelerating), even though the latter has higher absolute growth. Acceleration signals improving business momentum and future potential.

## Common Use Cases

### Daily/Weekly Routine
1. Run SuperPerform.py once per week
2. Review SEPA qualified stocks (typically 0-5 stocks)
3. Manually analyze each for:
   - Entry points (pullbacks to 50-day MA, VCP patterns)
   - Catalysts (news, products, earnings)
   - Sector leadership
4. Set alerts and watch for proper entry setups

### Custom Screening
1. Modify Finviz URL to focus on specific sectors or market caps
2. Adjust `MIN_RS_RATING` to be more/less selective
3. Tweak fundamental thresholds based on market conditions
4. Run on your existing stock watchlist (set `USE_FINVIZ_SCRAPER = False`)

### Backtesting Study
Use `SEPABacktester.py` to historically validate the SEPA methodology (see below)

---

## SEPABacktester - Historical Performance Validation

The `SEPABacktester.py` script answers the question: **"Do SEPA-qualified stocks actually go up?"**

It simulates running SuperPerform.py weekly over the past 2 years and tracks how each qualified stock performed afterward.

### How It Works

1. **Downloads stock universe** (~500-1000 stocks from S&P 500, NASDAQ-100, etc.)
2. **Caches 2.5 years of price data** locally for fast analysis
3. **For each Monday over 2 years** (~104 weeks):
   - Filters stocks meeting Finviz-like criteria (30%+ above 52w low, price > 200MA, 50MA > 200MA)
   - Calculates RS ratings and Stage 2 criteria
   - Runs fundamental screening (earnings/revenue acceleration)
   - Records stocks that pass all SEPA criteria
4. **Tracks forward performance** for each qualified stock:
   - 1-month, 3-month, 6-month returns
   - Maximum gain within 6 months
   - Days to hit +10%, +20%, +50% targets

### Running the Backtester

```bash
python SEPABacktester.py
```

### Configuration

Edit the configuration section at the top of `SEPABacktester.py`:

```python
TEST_MODE = False           # True for quick test (40 stocks, 3 months)
BACKTEST_YEARS = 2          # How far back to test
CHECK_FREQUENCY = 'weekly'  # Check every Monday
NUM_WORKERS = 23            # Parallel workers (auto-detected)
```

### Runtime Estimates

| Mode | Stocks | Period | Time |
|------|--------|--------|------|
| Test Mode | 40 | 3 months | 2-5 minutes |
| Full Backtest | 500-1000 | 2 years | 4-8 hours |

**Note**: First run downloads all price data (~30-60 min). Subsequent runs use cached data and are faster.

### Output Files

Results are saved to the `results/` directory:

- **`backtest_results_TIMESTAMP.csv`** - All qualification events with metrics:
  ```
  date, ticker, entry_price, rs_rating, earnings_accel, revenue_accel,
  return_1mo, return_3mo, return_6mo, max_gain_6mo, days_to_10pct, days_to_20pct
  ```

- **`backtest_summary_TIMESTAMP.txt`** - Aggregated statistics

### Sample Output

```
SEPA BACKTESTER RESULTS
================================================================================
Total qualification events: 1,247
Unique stocks: 312

WIN RATES (Positive Returns):
  1-month: 58.2% (726/1247)
  3-month: 62.1% (775/1247)
  6-month: 65.8% (821/1247)

HIT RATES (Target Achieved within 6 months):
  +10%: 45.3% hit (avg 32 days)
  +20%: 28.7% hit (avg 58 days)
  +50%: 12.4% hit (avg 89 days)

AVERAGE RETURNS:
  1-month: +4.2% avg, +3.1% median
  3-month: +11.8% avg, +8.5% median
  6-month: +18.5% avg, +12.2% median
  Max gain (6mo): +32.1% avg

TOP 10 BEST PERFORMERS (by max gain):
  SMCI   +450% (qualified 2023-06-12)
  NVDA   +280% (qualified 2023-01-09)
  ...
```

### Cache Management

Price data is cached in `cache/price_data/` as CSV files per ticker.

**To force fresh data download:**
```bash
rm -rf cache/price_data/
python SEPABacktester.py
```

### Interpreting Results

- **Win Rate > 50%**: Strategy has edge over random selection
- **Hit Rate for +20%**: Key metric - how often do qualified stocks become "winners"
- **Average vs Median**: Large gap indicates a few big winners skew the average
- **Best Performers**: Look for patterns in timing and sectors

### Limitations

- **Survivorship Bias**: Delisted stocks may be missing from universe
- **Point-in-Time Fundamentals**: Uses 45-day delay assumption for earnings availability
- **No Transaction Costs**: Results don't account for commissions or slippage
- **Look-Ahead Bias Mitigation**: Only uses data available on each historical date

---

## Limitations & Disclaimers

- **Not Financial Advice**: This is an educational tool. Do your own research.
- **Data Quality**: Relies on yfinance data which can have gaps or errors
- **Fundamental Data**: Quarterly data from yfinance may be incomplete for some stocks
- **Manual Review Required**: SEPA qualified stocks still need Step 4 (manual analysis)
- **No Guarantees**: Passing all criteria doesn't guarantee future performance
- **Market Conditions Matter**: Works best in bull markets (overall market in Stage 2)

## Troubleshooting

### "No stocks meet RS >= 70 threshold"
- Lower `MIN_RS_RATING` to 60-65
- Increase `MAX_PAGES` to scrape more stocks
- Market may be weak - check if SPY is in Stage 2

### "Failed to scrape Finviz screener"
- Check internet connection
- Finviz may be temporarily down
- Possible rate limiting - wait a few minutes
- Set `USE_FINVIZ_SCRAPER = False` and use manual list

### "Insufficient quarterly data" for all stocks
- yfinance API may be having issues
- Try again later
- Some stocks (ETFs, recent IPOs) lack quarterly data
- Set `ENABLE_STEP2 = False` to skip fundamental screening

### Script is very slow
- Normal - analyzing 50-100 stocks takes 5-10 minutes
- Reduce `MAX_PAGES` to analyze fewer stocks
- Fundamental screening adds significant time
- Cache helps on subsequent runs (within 24 hours)

## Performance Tips

- **Use caching**: Let cache work for you - don't force refresh unless needed
- **Limit MAX_PAGES**: Start with 2-3 pages (40-60 stocks) for faster results
- **Disable STEP2 initially**: Run without fundamental screening first to see Stage 2 candidates
- **Run during off-hours**: Less network congestion, faster API responses

## Contributing

This is a personal project, but suggestions welcome! Areas for improvement:
- Better fundamental data sources (Alpha Vantage, IEX, etc.)
- VCP pattern detection automation
- Entry point identification
- Sector rotation analysis
- Chart pattern recognition

## References

- **Book**: *Trade Like a Stock Market Wizard* by Mark Minervini
- **Methodology**: SEPA (Specific Entry Point Analysis)
- **IBD**: Investor's Business Daily (RS rating methodology)
- **Data Source**: Yahoo Finance via yfinance
- **Screener**: Finviz.com

## License

This project is for educational purposes. Use at your own risk.

---

**Remember**: The best traders combine quantitative screening (this tool) with qualitative analysis (catalysts, charts, news) and proper risk management. No system is perfect - focus on managing risk and cutting losses quickly.

**Happy Trading! 📈**
