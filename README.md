# SuperPerform - Minervini SEPA Stock Analyzer

A Python implementation of Mark Minervini's SEPA methodology from *"Trade Like a Stock Market Wizard"*. Screens stocks through RS ratings, Stage 2 trend template, and fundamental analysis - then ranks them by a **Quality Score** based on 18 months of backtested data.

## Quick Start

```bash
pip install -r requirements.txt
python SuperPerform.py
```

## What It Does

1. **RS Rating** - Calculates IBD-style relative strength vs S&P 500
2. **Stage 2 Template** - Validates 9 technical criteria for uptrend confirmation
3. **Fundamental Screening** - Checks earnings/revenue acceleration
4. **Quality Score** - Ranks stocks A/B/C/D based on backtest-proven edge factors

## Backtest-Optimized Criteria

Based on 18 months of data (2,453 signals, 239 stocks):

| Factor | Finding | Implementation |
|--------|---------|----------------|
| Distance from high | 0-10% = 69% win rate, 15%+ = 45% | Tightened to 10% max |
| RS Rating | Sweet spot is 80-94, RS 95+ underperforms | Range: 80-94 |
| Earnings Growth | >50% growth = +19.5% avg return | Weighted heavily in score |

**Result**: 67% win rate, 3.46 profit factor, +16.7% avg 6-month return

## Quality Score System

Stocks are scored 0-100 and graded:

| Grade | Score | Meaning |
|-------|-------|---------|
| A | 85-100 | Premium setup - highest probability |
| B | 70-84 | Good setup - solid edge |
| C | 55-69 | Average setup - moderate edge |
| D | <55 | Weak setup - marginal edge |

Score components:
- Distance from 52w high (30 pts) - most predictive factor
- RS Rating sweet spot (25 pts)
- Earnings growth (25 pts)
- Revenue growth (10 pts)
- Earnings acceleration (10 pts)

## Configuration

Edit top of `SuperPerform.py`:

```python
# RS & Stage Thresholds (optimized from backtest)
MIN_RS_RATING = 80          # Minimum RS rating
MAX_RS_RATING = 94          # Avoid overextended stocks
MAX_PCT_FROM_HIGH = 10      # Must be within 10% of 52w high

# Fundamental Screening
MIN_EARNINGS_GROWTH = 15.0  # Minimum YoY earnings growth %
MIN_SALES_GROWTH = 10.0     # Minimum YoY sales growth %
MIN_ACCELERATION_QUARTERS = 2

# Stock Source
USE_FINVIZ_SCRAPER = True   # False = use STOCK_LIST array
MAX_PAGES = 4               # Finviz pages to scrape
```

## Output

**Terminal**: Stocks ranked by Quality Score with grades

**CSV Files**:
- `superperform_TIMESTAMP.csv` - All analyzed stocks with metrics
- `sepa_qualified_TIMESTAMP.csv` - Only stocks passing all criteria, sorted by quality

## SEPABacktester

Validates the methodology by simulating weekly SEPA screens over 2 years:

```bash
python SEPABacktester.py
```

Tracks forward performance (1/3/6 month returns, hit rates for +10/20/50% targets).

**Runtime**: First run downloads data (~30 min), subsequent runs use cache (~20 min for full backtest).

## Stage 2 Criteria (9 total)

1. Price > 150-day and 200-day MA
2. 150-day MA > 200-day MA
3. 200-day MA trending up
4. 50-day MA > 150-day and 200-day MA
5. Price > 50-day MA
6. Price 30%+ above 52-week low
7. Price within 10% of 52-week high *(tightened from 25%)*
8. RS Rating >= 80 *(raised from 70)*
9. RS Rating <= 94 *(new - avoid overextension)*

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No stocks meet criteria | Lower MIN_RS_RATING, increase MAX_PAGES |
| Finviz scrape fails | Check internet, or set USE_FINVIZ_SCRAPER = False |
| "Insufficient data" | yfinance API issue, try again later |
| Slow performance | Normal (5-10 min), reduce MAX_PAGES for faster runs |

## References

- *Trade Like a Stock Market Wizard* - Mark Minervini
- IBD Relative Strength methodology
- Data: Yahoo Finance (yfinance), Finviz screener

---

**Not financial advice.** SEPA qualified stocks still require manual review for entry points, catalysts, and risk management.
