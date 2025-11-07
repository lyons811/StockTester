# Stock Scoring System

A professional-grade stock analysis system based on hedge fund methodologies. Analyzes stocks across technical, volume, fundamental, and market context indicators to generate buy/sell/hold signals with confidence ratings and position sizing recommendations.

**Status**: Phase 2 complete - Validated with 61.8% win rate on 3 years of historical data (2022-2025)

## Features

### Core Analysis
- **Trend & Momentum (40%)**: Moving averages, 12-month momentum, RSI, MACD
- **Volume Analysis (15%)**: Volume trends, institutional flow detection
- **Fundamental Quality (20%)**: P/E, PEG, ROE, Debt/Equity, Cash Flow, Earnings Trends
- **Market Context (25%)**: VIX levels, sector relative strength, market regime detection

*Weights optimized via grid search on historical data*

### Key Capabilities
- **Automatic Veto Rules**: Filters high-risk stocks (liquidity, earnings risk, bankruptcy risk)
- **Sector-Specific Scoring**: Custom adjustments for 13 sectors (Tech, Financials, Energy, etc.)
- **Historical Backtesting**: Walk-forward validation framework with 60-day holding periods
- **Weight Optimization**: Grid search algorithm to find optimal category weights
- **Confidence Scoring**: Multi-factor confidence adjustment system
- **Position Sizing**: Risk-adjusted portfolio allocation recommendations
- **Smart Caching**: 24-hour cache to respect API rate limits

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup

1. **Clone or download the repository**
```bash
cd C:\VSCode\personal\StockTester
```

2. **Create and activate virtual environment** (recommended)
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

### Dependencies
- `yfinance` - Yahoo Finance API for stock data
- `pandas` - Data manipulation and analysis
- `numpy` - Numerical computing
- `pandas-ta` - Technical analysis indicators
- `pyyaml` - Configuration file parsing

## Usage

### Analyze Individual Stocks
```bash
python main.py AAPL
python main.py MSFT
python main.py TSLA
```

### Run Historical Backtest
```bash
python main.py --backtest
```
Validates scoring system on default portfolio (AAPL, MSFT, TSLA, NVDA, JPM, XOM, PFE, WMT) from 2022-2025. Shows win rates, returns, and performance by score range/signal/ticker.

### Optimize Category Weights
```bash
python main.py --optimize-weights
```
Grid search to find optimal category weights. Tests combinations and evaluates on historical data. Exports results to `optimized_weights.yaml`.

**Note**: Optimization takes 10-20 minutes.

### Sample Output
```
================================================================
STOCK ANALYSIS: AAPL (Apple Inc.)
DATE: 2025-11-07 10:51
SECTOR: Technology | MARKET CAP: $3.97T
================================================================

OVERALL SIGNAL: BUY
SCORE: +4.4 / 10
CONFIDENCE: 100%
RECOMMENDED POSITION: 1.7% of portfolio

PROBABILITY ESTIMATES (1-3 month timeframe):
  ↗ Higher:   60-70%
  ↘ Lower:    15-25%
  → Sideways: 15-20%

================================================================
CATEGORY BREAKDOWN
================================================================

✓ TREND & MOMENTUM: +3.0/6 (+50%) - POSITIVE
  • MA Position:       +2  (Bullish (Golden Cross setup))
  • 12-month Momentum: +1  (13.6% - Bullish)
  • RSI (14):          -1  (77 - Overbought)
  • MACD:              +1  (Bullish crossover)

...
```

## Project Structure

```
StockTester/
├── main.py                      # CLI entry point
├── config.yaml                  # Configuration (weights, thresholds, sector adjustments)
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── stock_scoring_system_spec.md # Detailed methodology specification
│
├── data/                        # Data fetching and caching
│   ├── __init__.py
│   ├── fetcher.py              # yfinance API wrapper (Phase 2: +earnings, quarterly data)
│   └── cache_manager.py        # File-based caching system
│
├── indicators/                  # Indicator calculations
│   ├── __init__.py
│   ├── technical.py            # MA, RSI, MACD, momentum
│   ├── volume.py               # Volume trend and price relationship
│   ├── fundamental.py          # P/E, PEG, ROE, debt, cash flow (Phase 2: edge cases)
│   └── market_context.py       # VIX, sector relative, market regime
│
├── scoring/                     # Scoring engine
│   ├── __init__.py
│   ├── calculator.py           # Main scoring algorithm (Phase 2: sector adjustments)
│   └── vetoes.py               # Automatic veto rules (Phase 2: 3 new rules)
│
├── backtesting/                 # Phase 2: Historical validation
│   ├── __init__.py
│   ├── engine.py               # Walk-forward backtesting engine
│   ├── metrics.py              # Performance metrics calculator
│   └── optimizer.py            # Grid search weight optimizer
│
├── utils/                       # Utilities
│   ├── __init__.py
│   ├── config.py               # Configuration loader
│   └── formatter.py            # Console output formatting
│
└── cache/                       # Cache directory (auto-created)
    ├── AAPL_price_4y.json
    ├── AAPL_info.json
    ├── AAPL_earnings_history.json  # Phase 2
    ├── AAPL_quarterly_financials.json  # Phase 2
    └── ...
```

## Configuration

Edit `config.yaml` to customize:

### Category Weights (Phase 2 Optimized)
```yaml
weights:
  trend_momentum: 0.40  # +14% from baseline (captures momentum stocks)
  volume: 0.15          # -25% from baseline (less critical in trending markets)
  fundamental: 0.20     # -20% from baseline (don't over-penalize growth)
  market_context: 0.25  # +25% from baseline (regime detection critical)
```

### Sector-Specific Adjustments (Phase 2)
```yaml
sector_adjustments:
  Technology:
    weight_multipliers:
      trend_momentum: 1.2  # Tech is momentum-driven
      fundamental: 0.9     # Less emphasis on traditional valuation
    threshold_overrides:
      pe_fair: 35          # Higher P/E acceptable for tech
      peg_attractive: 1.5  # Growth-adjusted valuation more important

  Financials:
    weight_multipliers:
      fundamental: 1.3     # Fundamentals critical for banks
      trend_momentum: 0.9  # Less momentum-driven
    threshold_overrides:
      roe_quality: 12.0    # Lower ROE threshold
      debt_equity_healthy: 3.0  # Banks have higher leverage

  # ... (11 more sectors: Energy, Healthcare, Utilities, Materials, etc.)
```

### Technical Parameters
```yaml
technical:
  ma:
    short_period: 50
    long_period: 200
  rsi:
    period: 14
    standard_overbought: 70
    standard_oversold: 30
```

### Veto Rules (Phase 1 + Phase 2)
```yaml
vetoes:
  # Phase 1 Rules
  min_avg_volume: 500000        # Minimum daily volume
  min_market_cap: 300000000     # $300M minimum
  earnings_days_before: 7       # Avoid 7 days before earnings
  max_decline_60d: 0.50         # 50% max decline in 60 days
  max_debt_equity: 3.0          # Maximum debt-to-equity ratio
  min_negative_earnings_quarters: 4  # Consecutive quarters

  # Phase 2 Rules
  # - Consecutive earnings misses (3+ of last 4 quarters)
  # - Cash flow deterioration (quality < 0.5 for 3+ quarters)
  # - Analyst exodus (3+ downgrades in 30 days, no upgrades)
```

### Sector ETF Mappings
```yaml
sector_etfs:
  Technology: XLK
  Financials: XLF
  Energy: XLE
  Healthcare: XLV
  # ... etc
  default: SPY
```

## How It Works

The system analyzes stocks through a multi-stage pipeline:

1. **Data Collection**: Fetches price history, fundamentals, and market data from Yahoo Finance (cached 24h)
2. **Indicator Calculation**: Computes scores across 4 categories (trend, volume, fundamental, market)
3. **Sector Adjustment**: Applies sector-specific weight multipliers and threshold overrides
4. **Veto Screening**: Filters high-risk stocks based on 9 automatic rules
5. **Confidence Scoring**: Adjusts based on indicator agreement, earnings trends, and analyst sentiment
6. **Signal Generation**: Maps final score to BUY/SELL/NEUTRAL with probability estimates
7. **Position Sizing**: Calculates risk-adjusted portfolio allocation (max 5%)

**Signal Thresholds**:
- **+6 to +10**: STRONG BUY (70-80% probability higher)
- **+3 to +6**: BUY (60-70% probability higher)
- **-3 to +3**: NEUTRAL/HOLD
- **Below -3**: SELL/AVOID

See `stock_scoring_system_spec.md` for detailed methodology.

## Validation Results

### Historical Backtest (2022-2025)
- **259 trades** on 8-stock portfolio, 60-day holding periods
- **Overall**: 61.8% win rate, +3.18% avg return
- **BUY signals** (score ≥ 3): 66.9% win rate, +3.73% avg return
- **STRONG BUY** (score ≥ 6): 69.2% win rate, +7.15% avg return
- **Top performer**: NVDA (71.4% win rate, +8.67% avg return)

Run `python main.py --backtest` to see full performance breakdown by score range, signal type, and ticker.

## Data Sources

- **Yahoo Finance** (yfinance): Stock prices, fundamentals, earnings, analyst data
- **Market Indices**: ^GSPC (S&P 500), ^VIX (Volatility)
- **Sector ETFs**: XLK, XLF, XLE, XLV, XLI, XLY, XLU, XLB, XLRE, XLC, XLP
- **Cost**: Free (no API key required)
- **Caching**: 24h for fundamentals, 1h for prices (stored in `cache/` directory)

## Troubleshooting

**"Unable to fetch stock data"**: Check internet connection, verify ticker symbol, or clear cache (`rm -rf cache/`)

**"Module not found"**: Activate virtual environment and run `pip install -r requirements.txt`

**Rate limit errors**: Wait a few minutes - cache will reduce API calls on subsequent runs

**Incorrect scores**: Check `config.yaml` configuration, verify data is recent, some stocks may have incomplete data

## Performance

- **Timeframe**: Optimized for 1-3 month predictions
- **Execution**: 5-10 seconds per stock (first run), <1 second (cached)
- **Backtest**: 5-10 minutes, Weight optimization: 10-20 minutes
- **Complexity**: ~1,100 lines of code

## Methodology

Based on professional hedge fund methodologies (Renaissance Technologies, AQR, Two Sigma, BlackRock) and academic research (Fama-French, Momentum studies).

See `stock_scoring_system_spec.md` for detailed methodology.

## Disclaimer

This tool is for educational and informational purposes only. Not financial advice. Always do your own research and consult financial professionals before making investment decisions.

---

**Built with Python, yfinance, and quantitative methodologies**
**Current Status**: Phase 2 complete - Validated 61.8% win rate on 3 years of historical data
