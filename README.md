# Stock Scoring System - Phase 1 MVP

A professional-grade stock analysis system based on hedge fund methodologies. Analyzes stocks across technical, volume, fundamental, and market context indicators to generate buy/sell/hold signals with confidence ratings and position sizing recommendations.

## Features

### Core Analysis Categories
- **Trend & Momentum (35% weight)**: Moving averages, 12-month momentum, RSI, MACD
- **Volume & Institutions (20% weight)**: Volume trend analysis, volume-price relationships
- **Fundamental Quality (25% weight)**: P/E, PEG, ROE, Debt/Equity, Cash Flow Quality
- **Market Context (20% weight)**: VIX levels, sector relative strength, market regime detection

### Key Capabilities
- **Automatic Veto Rules**: Filters out high-risk stocks (low liquidity, earnings risk, bankruptcy risk, falling knives)
- **Confidence Scoring**: Adjusts signals based on indicator agreement/conflict
- **Position Sizing**: Recommends portfolio allocation based on score strength, volatility (beta), and market regime
- **Smart Caching**: 24-hour file-based cache to respect API rate limits
- **Configurable Thresholds**: YAML-based configuration for easy tuning

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

### Basic Usage
```bash
python main.py TICKER
```

### Examples
```bash
# Analyze Apple
python main.py AAPL

# Analyze Microsoft
python main.py MSFT

# Analyze Tesla
python main.py TSLA
```

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
├── config.yaml                  # Configuration (weights, thresholds, sector ETF mappings)
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── stock_scoring_system_spec.md # Detailed methodology specification
│
├── data/                        # Data fetching and caching
│   ├── __init__.py
│   ├── fetcher.py              # yfinance API wrapper
│   └── cache_manager.py        # File-based caching system
│
├── indicators/                  # Indicator calculations
│   ├── __init__.py
│   ├── technical.py            # MA, RSI, MACD, momentum
│   ├── volume.py               # Volume trend and price relationship
│   ├── fundamental.py          # P/E, PEG, ROE, debt, cash flow
│   └── market_context.py       # VIX, sector relative, market regime
│
├── scoring/                     # Scoring engine
│   ├── __init__.py
│   ├── calculator.py           # Main scoring algorithm
│   └── vetoes.py               # Automatic veto rules
│
├── utils/                       # Utilities
│   ├── __init__.py
│   ├── config.py               # Configuration loader
│   └── formatter.py            # Console output formatting
│
└── cache/                       # Cache directory (auto-created)
    ├── AAPL_price_2y.json
    ├── AAPL_info.json
    └── ...
```

## Configuration

Edit `config.yaml` to customize:

### Category Weights
```yaml
weights:
  trend_momentum: 0.35
  volume: 0.20
  fundamental: 0.25
  market_context: 0.20
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

### Veto Rules
```yaml
vetoes:
  min_avg_volume: 500000        # Minimum daily volume
  min_market_cap: 300000000     # $300M minimum
  earnings_days_before: 7       # Avoid 7 days before earnings
  max_decline_60d: 0.50         # 50% max decline in 60 days
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

### 1. Data Collection
- Fetches 2 years of price history from Yahoo Finance
- Retrieves fundamental data (P/E, ROE, debt, cash flow)
- Gets market context (VIX, S&P 500, sector ETF)
- Caches all data for 24 hours to minimize API calls

### 2. Indicator Calculation
Each category calculates raw scores:
- **Technical**: -6 to +6 points
- **Volume**: -3 to +3 points
- **Fundamental**: -2 to +5 points (asymmetric - rewards quality)
- **Market Context**: -3 to +4 points (asymmetric - rewards fear)

### 3. Normalization & Weighting
- Raw scores normalized to -100% to +100%
- Weighted by category importance
- Combined into total percentage score

### 4. Confidence Adjustment
Adjusts based on:
- Indicator agreement (boost if 3+ categories agree)
- Indicator conflict (reduce if 2 positive, 2 negative)
- Extreme volatility (reduce during VIX > 40)
- Trend/fundamental divergence (reduce if conflicting)

### 5. Signal Generation
Final score (-10 to +10) mapped to signals:
- **+6 to +10**: STRONG BUY (70-80% probability higher)
- **+3 to +6**: BUY (60-70% probability higher)
- **-3 to +3**: NEUTRAL/HOLD
- **-6 to -3**: SELL/AVOID
- **-10 to -6**: STRONG SELL

### 6. Position Sizing
Calculated based on:
- Score strength (higher score = larger position)
- Volatility adjustment (reduce high-beta stocks)
- Market regime (reduce in bear markets)
- Maximum cap: 5% of portfolio

### 7. Automatic Vetoes
Stocks are disqualified if they meet any:
- Average volume < 500K shares
- Market cap < $300M
- Earnings within 7 days
- Price down >50% in 60 days
- Debt/Equity > 3.0
- Negative earnings 4+ consecutive quarters

## Example Results

### AAPL (Buy Signal)
- **Score**: +4.4 / 10
- **Signal**: BUY
- **Position**: 1.7% of portfolio
- **Why**: Golden Cross, +13.6% momentum, outperforming sector +7.6%
- **Risks**: Overbought RSI (77), expensive P/E (36)

### TSLA (Hold Signal)
- **Score**: +2.8 / 10
- **Signal**: NEUTRAL/HOLD
- **Position**: 0.4% of portfolio
- **Why**: Massive momentum (+73.2%) but P/E 296 with declining earnings
- **Risks**: Speculative valuation, high volatility (beta 1.87)

### MSFT (Hold Signal)
- **Score**: +1.1 / 10
- **Signal**: NEUTRAL/HOLD
- **Position**: 0.6% of portfolio
- **Why**: Quality company but underperforming sector by -11.7%
- **Risks**: Expensive valuation, sector weakness

## Data Sources

- **Stock Data**: Yahoo Finance (via yfinance)
- **Market Indices**: ^GSPC (S&P 500), ^VIX (Volatility Index)
- **Sector ETFs**: XLK, XLF, XLE, XLV, XLI, XLY, XLU, XLB, XLRE, XLC, XLP
- **Cost**: Free (no API key required)

## Caching System

- **Duration**: 24 hours for fundamentals, 1 hour for price data
- **Location**: `cache/` directory
- **Format**: JSON files
- **Benefits**:
  - Faster repeat queries
  - Respects Yahoo Finance rate limits
  - Reduces network calls
- **Clear cache**: Delete files in `cache/` directory

## Future Enhancements (Phase 2+)

### Phase 2: Enhanced Fundamentals
- Refined scoring weights based on backtesting
- Sector-specific adjustments
- Confidence scoring improvements
- Historical backtesting framework

### Phase 3: Advanced Features
- Earnings history tracking (beat/miss analysis)
- Analyst revision monitoring
- Short interest analysis
- Options flow detection
- Insider trading activity

### Phase 4: Optimization
- Walk-forward optimization
- Parameter tuning across market regimes
- Statistical validation
- Performance metrics (Sharpe ratio, win rate)

### Phase 5: Real-Time Monitoring
- Daily automated scoring for watchlists
- Alert system for signal changes
- Portfolio tracking and rebalancing
- Web dashboard

## Troubleshooting

### Common Issues

**"Unable to fetch stock data"**
- Check internet connection
- Verify ticker symbol is valid
- Try clearing cache: `rm -rf cache/`

**"Module not found"**
- Ensure virtual environment is activated
- Run: `pip install -r requirements.txt`

**Rate limit errors**
- Wait a few minutes
- Cache will reduce API calls on subsequent runs

**Incorrect scores**
- Check `config.yaml` for proper configuration
- Verify data is recent (check cache timestamps)
- Some stocks may have incomplete fundamental data

## Methodology

This system is based on professional hedge fund methodologies from:
- Renaissance Technologies
- AQR Capital Management
- Two Sigma
- BlackRock Systematic
- Academic research (Fama-French, Momentum studies)

See `stock_scoring_system_spec.md` for detailed methodology and research basis.

## Performance Notes

- **Timeframe**: Optimized for 1-3 month predictions
- **Complexity**: Medium (~700 lines of code)
- **Execution Time**: 5-10 seconds per stock (first run), <1 second (cached)
- **Accuracy**: Phase 1 baseline (backtesting in Phase 4)

## License

This project is for educational and personal use.

## Contributing

This is Phase 1 MVP. Future enhancements welcome!

Areas for contribution:
- Backtesting framework
- Additional indicators
- Sector-specific models
- Performance tracking
- Web interface

## Disclaimer

This tool is for informational purposes only. It does not constitute financial advice. Always do your own research and consult with financial professionals before making investment decisions. Past performance does not guarantee future results.

## Contact & Support

For issues or questions, please refer to the specification document (`stock_scoring_system_spec.md`) for detailed methodology and implementation details.

---

**Built with Python, yfinance, and professional quantitative methodologies.**
