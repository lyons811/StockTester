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
5. **Entry Timing** - Flags stocks in buy zone vs extended (10/21 EMA)
6. **Volume Analysis** - Validates breakouts with volume confirmation
7. **Earnings Warning** - Flags upcoming earnings within 45 days
8. **Market Regime** - Shows SPY health (bullish/cautious/bearish)
9. **Sector Tracking** - Warns if >40% concentrated in one sector

## Output Example

```
MARKET STATUS: BULLISH
  SPY: $687.01 | Above 50 MA ($676.57) | Above 200 MA ($622.91)
  Recommendation: Full position sizes OK

TOP PICKS - Ready to Buy (Grade A/B, Buy Zone, Earnings Clear)
  TICKER   GRADE  RS   PRICE      ENTRY      VOLUME   EARNINGS   SECTOR
  APP      A      88   $693.71    BUY_ZONE   WEAK     43d        Communication S
  GOOG     B      85   $314.55    BUY_ZONE   WEAK     35d        Communication S

WATCHLIST - Wait for Pullback or Earnings to Pass
  SMCI     B      88   $42.50     EXTENDED   NORMAL   12d [!]    Technology

SECTOR CONCENTRATION
  Technology:    45% (5 stocks) [!CONCENTRATED]
  Healthcare:    25% (3 stocks)
```

## Entry Timing

Based on 10/21 EMA proximity:

| Status | Meaning |
|--------|---------|
| BUY_ZONE | Within 5% of 10 or 21 EMA - good pullback entry |
| EXTENDED | >10% above 21 EMA - chasing risk |
| WATCHLIST | In between - wait for pullback |

## Volume Analysis

| Status | Criteria |
|--------|----------|
| STRONG | Recent volume >1.5x 50-day avg AND up/down ratio >1.2 |
| WEAK | Recent volume <0.8x avg OR up/down ratio <0.8 |
| NORMAL | Everything else |

## Earnings Warning

| Flag | Meaning |
|------|---------|
| `12d [!]` | DANGER - earnings within 14 days |
| `35d` | CAUTION - earnings within 45 days |
| `57d` | CLEAR - earnings >45 days away |
| `Rpt:10/22` | REPORTED - last earnings date, next TBD |
| `N/A` | No earnings data (ETFs, funds) |

## Market Regime

Checked at startup based on SPY:

| Regime | Condition | Recommendation |
|--------|-----------|----------------|
| BULLISH | SPY > 50 MA > 200 MA | Full position sizes OK |
| CAUTIOUS | SPY > 200 MA but < 50 MA | Reduce size, be selective |
| BEARISH | SPY < 200 MA | Cash preferred, avoid new longs |

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
# RS & Stage Thresholds
MIN_RS_RATING = 80          # Minimum RS rating
MAX_RS_RATING = 94          # Avoid overextended stocks
MAX_PCT_FROM_HIGH = 10      # Must be within 10% of 52w high

# Fundamental Screening
MIN_EARNINGS_GROWTH = 15.0  # Minimum YoY earnings growth %
MIN_SALES_GROWTH = 10.0     # Minimum YoY sales growth %

# Entry Timing
EMA_PULLBACK_THRESHOLD = 5.0   # Within 5% of EMA = buy zone
EMA_EXTENDED_THRESHOLD = 10.0  # >10% above EMA = extended

# Volume
VOLUME_STRONG_RATIO = 1.5      # 1.5x avg = strong
UP_DOWN_VOLUME_THRESHOLD = 1.2 # Up days should have more volume

# Earnings
EARNINGS_DANGER_DAYS = 14      # Within 14 days = danger
EARNINGS_CAUTION_DAYS = 45     # Within 45 days = caution

# Sector
MAX_SECTOR_CONCENTRATION = 40  # Warn if >40% in one sector

# Stock Source
USE_FINVIZ_SCRAPER = True   # False = use STOCK_LIST array
MAX_PAGES = 4               # Finviz pages to scrape
```

## Output Files

| File | Contents |
|------|----------|
| `superperform_TIMESTAMP.csv` | All analyzed stocks with full metrics |
| `sepa_qualified_TIMESTAMP.csv` | Only SEPA qualified stocks |
| `top_picks_TIMESTAMP.csv` | Actionable picks (Grade A/B, BUY_ZONE, earnings clear) |

## Stage 2 Criteria (9 total)

1. Price > 150-day and 200-day MA
2. 150-day MA > 200-day MA
3. 200-day MA trending up
4. 50-day MA > 150-day and 200-day MA
5. Price > 50-day MA
6. Price 30%+ above 52-week low
7. Price within 10% of 52-week high
8. RS Rating >= 80
9. RS Rating <= 94

## SEPABacktester

Validates the methodology by simulating weekly SEPA screens over 2 years:

```bash
python SEPABacktester.py
```

**Runtime**: First run downloads data (~30 min), subsequent runs use cache (~20 min).

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No stocks meet criteria | Lower MIN_RS_RATING, increase MAX_PAGES |
| Finviz scrape fails | Check internet, or set USE_FINVIZ_SCRAPER = False |
| "Insufficient data" | yfinance API issue, try again later |
| Slow performance | Normal (5-10 min), reduce MAX_PAGES for faster runs |
| Earnings all UNKNOWN | yfinance doesn't have future date yet - shows last reported |

## References

- *Trade Like a Stock Market Wizard* - Mark Minervini
- IBD Relative Strength methodology
- Data: Yahoo Finance (yfinance), Finviz screener

---

**Not financial advice.** SEPA qualified stocks still require manual review for entry points, catalysts, and risk management.
