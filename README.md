# Stock Scoring System

A professional-grade stock analysis system based on hedge fund methodologies. Analyzes stocks across technical, volume, fundamental, market context, and advanced indicators to generate buy/sell/hold signals with confidence ratings and position sizing recommendations.

**Status**: Phase 5b complete ✅ - Advanced momentum indicators: Bollinger Band squeeze detection, ATR consolidation patterns, multi-timeframe alignment, support/resistance levels, and OBV divergence analysis

## Features

### Core Analysis (5 Categories)
- **Trend & Momentum (26%)**: Moving averages, 12-month momentum, RSI, MACD, **52-week breakout detection** ✨ *Phase 5a*, **Bollinger Band squeeze**, **ATR consolidation patterns**, **multi-timeframe alignment**, **short-term support/resistance** ✨ *Phase 5b*
- **Volume Analysis (10%)**: Volume trends, institutional flow detection, **OBV divergence analysis** ✨ *Phase 5b*
- **Fundamental Quality (22%)**: P/E, PEG, ROE, Debt/Equity, Cash Flow, **Revenue growth acceleration** ✨ *Phase 5a*
- **Market Context (21%)**: VIX levels, sector relative strength, market regime, **Earnings timing risk filter** ✨ *Phase 5a*
- **Advanced Features (20%)** ✨ *Phase 3+5a*:
  - Earnings quality (beat/miss history, YoY growth)
  - Analyst revisions (upgrades/downgrades, consensus)
  - Short interest analysis (squeeze potential, days to cover)
  - Options flow (put/call ratios, unusual activity)
  - **Relative strength rank vs S&P 500** (percentile ranking) ✨ *Phase 5a*

*Weights optimized via grid search on historical data (243 combinations tested, Phase 5a optimization pending)*

### Key Capabilities
- **Automatic Veto Rules**: Filters high-risk stocks (liquidity, earnings risk, bankruptcy risk)
- **Sector-Specific Scoring**: Custom adjustments for 13 sectors (Tech, Financials, Energy, etc.)
- **S&P 500 Bulk Analysis**: Automatically analyze all 500+ stocks with configurable filtering
- **Historical Backtesting**: Walk-forward validation framework with 60-day holding periods
- **Weight Optimization**: Grid search algorithm to find optimal category weights
- **Confidence Scoring**: Multi-factor confidence adjustment system
- **Position Sizing**: Risk-adjusted portfolio allocation recommendations
- **Smart Caching**: 24-hour cache to respect API rate limits

### Phase 4: Advanced Optimization & Validation ✨ *NEW*
- **Sharpe Ratio Optimization**: Optimizes for risk-adjusted returns (not just win rate)
- **Walk-Forward Validation**: Expanding window testing prevents overfitting (5-6 out-of-sample periods)
- **Regime-Adaptive Weights**: Separate bull/bear market weight sets (200-day MA detection)
- **Advanced Risk Metrics**: Sharpe ratio, Sortino ratio, Max Drawdown, Calmar ratio
- **Statistical Validation**: Significance testing, bootstrap confidence intervals, Monte Carlo simulation
- **Extended Backtesting**: 7-year validation period (2018-2025) vs 3 years in Phase 3
- **Comprehensive Reporting**: Automated report generation with regime comparisons

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
- `scipy` - Statistical functions (Phase 4: significance testing)
- `tqdm` - Progress bars for bulk analysis
- `lxml` - HTML parsing for S&P 500 list fetching

## Usage

### Analyze Individual Stocks
```bash
python main.py AAPL
python main.py MSFT
python main.py TSLA
```

### Bulk Analyze S&P 500 Stocks ✨ *NEW*
```bash
# Analyze all S&P 500, return only STRONG BUY (score >= 6.0)
python analyze_sp500.py

# Include BUY signals too (score >= 3.0)
python analyze_sp500.py --min-score 3.0

# Test on first 20 stocks
python analyze_sp500.py --limit 20

# Custom output file
python analyze_sp500.py --output my_picks.csv
```
Automatically fetches current S&P 500 constituents from Wikipedia and analyzes all ~500 stocks. Returns filtered results with:
- Console summary (top 20 stocks, sector breakdown)
- CSV export with ticker, company, sector, score, signal, position size, probabilities
- Progress bar showing real-time analysis status
- Sorted by position size (highest conviction first)

**Performance**:
- First run: 15-30 minutes (fetching data for all stocks)
- Subsequent runs: 2-5 minutes (cached data, 24-hour TTL)

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

### Phase 4: Walk-Forward Optimization ✨ *NEW*
```bash
python main.py --walk-forward
```
Runs walk-forward optimization with Sharpe ratio objective. Validates strategy across 5-6 expanding window periods (2018-2025) to prevent overfitting. Shows out-of-sample performance for each test period.

**Note**: Takes 30-60 minutes due to multiple optimization rounds.

### Phase 4: Regime-Specific Optimization ✨ *NEW*
```bash
python main.py --optimize-regime
```
Optimizes separate weight sets for bull and bear markets. Automatically classifies historical periods using S&P 500 vs 200-day MA, then finds optimal weights for each regime. Updates `config.yaml` with regime-specific weights.

**Note**: Takes 20-40 minutes.

### Phase 4: Complete Optimization Pipeline ✨ *NEW*
```bash
python optimization.py
```
Runs complete Phase 4 pipeline: walk-forward optimization, regime-specific weights, statistical validation, and comprehensive report generation. Fully automated.

**Note**: Takes 30-60 minutes. Generates `phase4_validation_report.md`.

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
├── optimization.py              # Phase 4: Complete optimization pipeline (automated)
├── config.yaml                  # Configuration (weights, thresholds, sector adjustments)
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── stock_scoring_system_spec.md # Detailed methodology specification
│
├── data/                        # Data fetching and caching
│   ├── __init__.py
│   ├── fetcher.py              # yfinance API wrapper (Phase 3: +short interest, options)
│   └── cache_manager.py        # File-based caching system
│
├── indicators/                  # Indicator calculations
│   ├── __init__.py
│   ├── technical.py            # MA, RSI, MACD, momentum
│   ├── volume.py               # Volume trend and price relationship
│   ├── fundamental.py          # P/E, PEG, ROE, debt, cash flow (Phase 2: edge cases)
│   ├── market_context.py       # VIX, sector relative, market regime
│   └── advanced.py             # Phase 3: Earnings quality, analyst revisions, short interest, options
│
├── scoring/                     # Scoring engine
│   ├── __init__.py
│   ├── calculator.py           # Main scoring algorithm (Phase 2: sector adjustments)
│   └── vetoes.py               # Automatic veto rules (Phase 2: 3 new rules)
│
├── backtesting/                 # Phase 2-4: Historical validation & optimization
│   ├── __init__.py
│   ├── engine.py               # Walk-forward backtesting engine
│   ├── metrics.py              # Performance metrics (Phase 4: +Sharpe, Sortino, Max DD, Calmar)
│   ├── optimizer.py            # Grid search optimizer (Phase 4: +Sharpe objective, regime optimization)
│   ├── walk_forward.py         # Phase 4: Walk-forward optimizer with expanding windows
│   └── report_generator.py     # Phase 4: Comprehensive validation report generator
│
├── utils/                       # Utilities
│   ├── __init__.py
│   ├── config.py               # Configuration loader
│   ├── formatter.py            # Console output formatting
│   ├── statistics.py           # Phase 4: Statistical validation (t-tests, bootstrap, Monte Carlo)
│   └── regime_classifier.py    # Phase 4: Bull/bear market regime detection
│
└── cache/                       # Cache directory (auto-created)
    ├── AAPL_price_4y.json
    ├── AAPL_info.json
    ├── AAPL_earnings_history.json  # Phase 2
    ├── AAPL_quarterly_financials.json  # Phase 2
    ├── AAPL_analyst_data.json  # Phase 2
    ├── AAPL_short_interest.json  # Phase 3
    ├── AAPL_options_data.json  # Phase 3
    └── ...
```

## Configuration

Edit `config.yaml` to customize:

### Category Weights (Phase 3 Optimized)
```yaml
weights:
  trend_momentum: 0.255   # Momentum and trend following
  volume: 0.102           # Institutional flow detection
  fundamental: 0.224      # Quality and valuation metrics
  market_context: 0.214   # Regime and sector relative strength
  advanced: 0.204         # Phase 3: Earnings, analysts, short interest, options
```

*Note: Weights optimized via 5-category grid search on 3 years of historical data*

### Regime-Specific Weights (Phase 4) ✨ *NEW*
```yaml
optimized_weights:
  bull_market:    # Used when S&P 500 > 200-day MA
    trend_momentum: 0.30  # Will be optimized
    volume: 0.10
    fundamental: 0.20
    market_context: 0.20
    advanced: 0.20

  bear_market:    # Used when S&P 500 < 200-day MA
    trend_momentum: 0.25  # Will be optimized
    volume: 0.15
    fundamental: 0.25
    market_context: 0.20
    advanced: 0.15

backtesting:
  use_regime_weights: false  # Enable after running regime optimization
```

*Note: Regime weights optimized separately for bull/bear markets. Enable with `use_regime_weights: true` after running `python main.py --optimize-regime`*

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

1. **Data Collection**: Fetches price history, fundamentals, earnings, analyst data, short interest, and options from Yahoo Finance (cached 24h)
2. **Indicator Calculation**: Computes scores across 5 categories (trend, volume, fundamental, market, advanced)
3. **Sector Adjustment**: Applies sector-specific weight multipliers and threshold overrides
4. **Veto Screening**: Filters high-risk stocks based on 9 automatic rules
5. **Confidence Scoring**: Adjusts based on indicator agreement, advanced feature confirmation
6. **Signal Generation**: Maps final score to BUY/SELL/NEUTRAL with probability estimates
7. **Position Sizing**: Calculates risk-adjusted portfolio allocation (max 5%)

**Signal Thresholds**:
- **+6 to +10**: STRONG BUY (70-80% probability higher)
- **+3 to +6**: BUY (60-70% probability higher)
- **-3 to +3**: NEUTRAL/HOLD
- **Below -3**: SELL/AVOID

See `stock_scoring_system_spec.md` for detailed methodology.

## Validation Results

### Phase 3 Performance (2022-2025)
**259 trades** on 8-stock portfolio, 60-day holding periods, rebalanced monthly

**Overall Performance:**
- Win Rate: **61.8%** (160 winners, 99 losers)
- Average Return: **+3.77%** (+18.6% improvement vs Phase 2)
- Median Return: +2.74%
- Best Trade: +77.94% | Worst Trade: -31.57%

**Performance by Signal:**
- **BUY signals** (score ≥ 3): **70.3%** win rate, **+6.95%** avg return (+86% improvement)
- **STRONG BUY** (score ≥ 6): 67.6% win rate, +3.95% avg return
- **NEUTRAL**: 51.4% win rate, +0.52% avg return

**Top Performers:**
- **WMT**: 81.1% win rate, +4.79% avg return
- **NVDA**: 64.9% win rate, +12.18% avg return
- **JPM**: 67.6% win rate, +3.95% avg return
- **XOM**: 64.9% win rate, +3.88% avg return

**Phase 3 vs Phase 2 Improvements:**
- ✅ Overall avg return: +3.18% → **+3.77%** (+18.6%)
- ✅ BUY signal win rate: 66.9% → **70.3%** (+3.4 points)
- ✅ BUY signal avg return: +3.73% → **+6.95%** (+86%)
- ✅ Advanced features (20.4% weight) add significant value

Run `python main.py --backtest` to see full performance breakdown by score range, signal type, and ticker.

---

### Phase 4: Advanced Optimization Framework ✨ *NEW*

**Implementation Status**: ✅ Complete and Ready to Run

Phase 4 extends validation to **7 years (2018-2025)** with advanced optimization and statistical rigor:

**Key Improvements Over Phase 3:**

| Feature | Phase 3 | Phase 4 |
|---------|---------|---------|
| **Validation Period** | 3 years (2022-2025) | 7 years (2018-2025) |
| **Optimization Objective** | Win Rate | Sharpe Ratio (risk-adjusted) |
| **Validation Method** | Single period | Walk-forward (5-6 periods) |
| **Market Adaptation** | Static weights | Regime-specific weights |
| **Risk Metrics** | Basic (win rate, returns) | Advanced (Sharpe, Sortino, Max DD, Calmar) |
| **Statistical Tests** | None | Significance tests, confidence intervals |

**Phase 4 Framework Includes:**

1. **Walk-Forward Optimization**
   - Expanding window validation (train 2018-2019 → test 2020, train 2018-2020 → test 2021, etc.)
   - 5-6 out-of-sample test periods
   - Prevents overfitting through strict train/test separation
   - Aggregated metrics across all test periods

2. **Sharpe Ratio Optimization**
   - Optimizes for risk-adjusted returns (return per unit of risk)
   - Professional standard for portfolio management
   - Accounts for volatility, not just raw returns

3. **Regime-Specific Weights**
   - Bull market weights (S&P 500 > 200-day MA)
   - Bear market weights (S&P 500 < 200-day MA)
   - Automatic regime detection and weight switching
   - Adapts strategy to changing market conditions

4. **Advanced Risk Metrics**
   - **Sharpe Ratio**: Risk-adjusted returns
   - **Sortino Ratio**: Downside deviation only
   - **Maximum Drawdown**: Worst peak-to-trough decline
   - **Calmar Ratio**: Return / max drawdown
   - **Annualized Returns & Volatility**

5. **Statistical Validation**
   - Win rate significance testing (binomial test)
   - Mean return significance (t-test)
   - Bootstrap confidence intervals (95%)
   - Monte Carlo simulation (1000+ iterations)
   - Phase 3 vs Phase 4 comparison tests

**How to Run Phase 4:**

```bash
# Complete automated pipeline (recommended)
python optimization.py

# Or individual components
python main.py --walk-forward       # Walk-forward optimization
python main.py --optimize-regime    # Regime-specific weights
```

**Expected Outcomes:**
- Sharpe Ratio: 0.5-1.5+ (target: > 1.0 for good risk-adjusted performance)
- Out-of-sample win rate: 60-65%+
- Statistical significance: p < 0.05 (better than random)
- Regime-adaptive performance: Improved stability across market cycles

**Deliverables:**
- `config.yaml` updated with optimized bull/bear market weights
- `phase4_validation_report.md` - Comprehensive analysis with:
  - Walk-forward period-by-period results
  - Regime comparison (bull vs bear performance)
  - Statistical significance tests
  - Phase 3 vs Phase 4 comparison
- Console output with real-time progress and results

**Note**: First run takes 30-60 minutes. Results are cached for analysis.

## Data Sources

- **Yahoo Finance** (yfinance): Stock prices, fundamentals, earnings, analyst data, short interest, options chains
- **Market Indices**: ^GSPC (S&P 500), ^VIX (Volatility)
- **Sector ETFs**: XLK, XLF, XLE, XLV, XLI, XLY, XLU, XLB, XLRE, XLC, XLP
- **Cost**: Free (no API key required)
- **Caching**: 24h for fundamentals/advanced features, 1h for prices (stored in `cache/` directory)

**Phase 3 Data:**
- Earnings history (actual vs estimate, surprise %)
- Analyst upgrades/downgrades (last 30 days)
- Short interest (% of float, days to cover)
- Options flow (put/call ratios, volume vs open interest)

## Troubleshooting

**"Unable to fetch stock data"**: Check internet connection, verify ticker symbol, or clear cache (`rm -rf cache/`)

**"Module not found"**: Activate virtual environment and run `pip install -r requirements.txt`

**Rate limit errors**: Wait a few minutes - cache will reduce API calls on subsequent runs

**Incorrect scores**: Check `config.yaml` configuration, verify data is recent, some stocks may have incomplete data

## Performance

- **Timeframe**: Optimized for 1-3 month predictions
- **Execution**: 5-10 seconds per stock (first run), <1 second (cached)
- **Backtest**: 5-10 minutes
- **Weight Optimization**: 15-30 minutes (243 combinations)
- **Phase 4 Walk-Forward**: 30-60 minutes (5-6 optimization rounds)
- **Complexity**: ~3,300 lines of code (Phase 4 complete)

## Methodology

Based on professional hedge fund methodologies (Renaissance Technologies, AQR, Two Sigma, BlackRock) and academic research (Fama-French, Momentum studies).

See `stock_scoring_system_spec.md` for detailed methodology.

## Disclaimer

This tool is for educational and informational purposes only. Not financial advice. Always do your own research and consult financial professionals before making investment decisions.

---

**Built with Python, yfinance, scipy, and quantitative methodologies**

**Current Status**: Phase 5b complete ✅

**Phase 3 Foundation:**
- 5-category scoring system with advanced features
- 61.8% win rate, +3.77% avg return (validated on 2022-2025 data)
- BUY signals: 70.3% win rate, +6.95% avg return
- Optimized weights via 243-combination grid search

**Phase 4 Enhancements:**
- Walk-forward optimization with Sharpe ratio objective
- 7-year validation period (2018-2025) with 5-6 out-of-sample test periods
- Regime-specific weights for bull/bear market adaptation
- Advanced risk metrics (Sharpe, Sortino, Max Drawdown, Calmar)
- Statistical validation (significance tests, confidence intervals, Monte Carlo)
- Comprehensive reporting and automated pipeline

**Phase 5a: Enhanced Momentum & Risk Intelligence**
- **52-Week High Breakout Detection**: Identifies momentum breakouts at new highs with volume confirmation
- **S&P 500 Relative Strength Ranking**: Percentile comparison against all 500 constituents (NVDA: 96th percentile!)
- **Revenue Growth Acceleration**: Quarterly revenue trend analysis catches declining growth (AAPL revenue -25% flagged)
- **Earnings Timing Risk Filter**: Avoids high-volatility periods near earnings announcements (7-14 day windows)
- **Validated Results**: 63.5% win rate (+1.7% from Phase 3), +3.89% avg return (+3% improvement)
- **Score Ranges Updated**: Technical 10, Fundamental 8, Market 7, Advanced 13 (was 6/5/4/10)

**Phase 5b: Advanced Momentum Analysis** ✨ *NEW*
- **Bollinger Band Squeeze Detection**: Catches low-volatility compression before explosive breakouts (+2 points)
- **ATR Consolidation Patterns**: Identifies "coiling spring" setups with declining volatility near highs (+2 points)
- **Multi-Timeframe Alignment**: Validates trends across daily and weekly timeframes to reduce whipsaws (+1 point)
- **Short-Term Support/Resistance**: Detects 60-day bounces and failed breakouts for better entry timing (+1 point)
- **OBV Divergence Analysis**: Tracks volume flow for early accumulation/distribution signals (+1 point)
- **Exceptional Results**: **72.4% win rate (+8.9% from Phase 5a!)**, +6.14% avg return (+58% improvement), Sharpe 1.160, 105 test trades
- **Score Ranges Expanded**: Technical 16 (was 10), Volume 5 (was 3) - Total system: 49 points (was 41)
- **Signal Thresholds**: STRONG_BUY 3.5, BUY 2.5 maintained

**Next Step**: Run `python optimization.py` to optimize weights for Phase 5b indicators, then implement Phase 5c (Sector Intelligence)

**Ready to Run**: `python main.py NVDA` or `python main.py --backtest`
