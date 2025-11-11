# Phase 5: Enhanced Momentum & Risk Intelligence

## Executive Summary

**Goal**: Increase win rate from 63.5% to 70-75%+ and capture more high-momentum winners (NVDA-style +9-10% returns) while filtering bad setups.

**Strategy**: Add momentum detection, smart money tracking, fundamental acceleration, and improved risk filters. Focus on maximizing upside for long-only portfolio with medium risk tolerance.

---

## Key Problems Identified from Backtest

### 1. **Signal Distribution Too Narrow**
- **Problem**: No STRONG BUY or STRONG SELL signals generated (all stocks scored 0-6 range)
- **Impact**: Missing best setups, taking mediocre trades
- **Solution**: Add high-conviction momentum indicators to push exceptional stocks to 6.0+ scores

### 2. **Bear Market Vulnerability (2022)**
- **Problem**: Win rate dropped to 46.4% during bear market (vs 70%+ in bull markets)
- **Impact**: -132% return in single year wiped out gains
- **Solution**: Better regime-adaptive risk filters (avoid weak setups in bear markets)

### 3. **Missing High-Momentum Winners**
- **Problem**: NVDA averaged +9.75%, but only 68.6% win rate (should be higher for such strong stock)
- **Impact**: Leaving alpha on the table
- **Solution**: Add momentum acceleration and consolidation breakout detection

### 4. **Sector Performance Variance**
- **Problem**: PFE only 51.2% win rate (+0.43% avg) vs WMT 70.9% (+2.74%)
- **Impact**: One-size-fits-all scoring hurts pharma/healthcare
- **Solution**: Sector-specific indicator adjustments

### 5. **Loss Streak Management**
- **Problem**: Longest loss streak = 16 trades (could wipe out account with leverage)
- **Impact**: Psychological and capital risk
- **Solution**: Better entry timing filters (avoid choppy consolidations, pre-earnings)

---

## Phase 5 Enhancements

### **Category 1: Technical Indicators (Expand Existing)**

#### **A. Bollinger Bands Mean Reversion + Squeeze**
**Purpose**: Catch oversold bounces and volatility breakouts
- Calculate 20-period BB (2 standard deviations)
- **Score +1**: Price touches lower BB in established uptrend (50 EMA > 200 EMA)
- **Score +2**: BB squeeze (bandwidth < 20th percentile) + breakout above upper BB
- **Score -1**: Price at upper BB with overbought RSI (>70)
- **Veto**: Avoid stocks in BB squeeze without clear trend (sideways chop)

**Data**: Price history (already fetched)

#### **B. Support/Resistance Breakout Detection**
**Purpose**: Better entry timing at key levels
- **Score +2**: Breaking above 52-week high on above-average volume
- **Score +1**: Bouncing off major support (prior high/low within 2%)
- **Score -1**: Stuck at resistance, multiple failed breakout attempts
- **Score -2**: Breaking below 52-week low

**Data**: yfinance history (52-week high/low available)

#### **C. Price Consolidation Detection**
**Purpose**: Identify "coiling springs" before explosive moves
- Calculate ATR (Average True Range, 14-day)
- **Score +1**: ATR declining for 10+ days while price near highs (accumulation)
- **Score +2**: Tight 5-10 day consolidation after 20%+ rally (continuation setup)
- **Score -1**: Wide ATR spikes (volatility, uncertainty)

**Data**: Price history (OHLC for ATR calculation)

#### **D. Multi-Timeframe Trend Alignment**
**Purpose**: Reduce whipsaws, only trade when all timeframes agree
- Check daily, weekly trends (50 EMA slope)
- **Score +1**: Daily and weekly both uptrend (aligned bullish)
- **Score -1**: Daily uptrend but weekly downtrend (counter-trend, risky)
- **No score**: Both downtrend (already filtered by existing MA logic)

**Data**: Price history (already fetched)

**Technical Category Impact**: +4-6 new scoring points available (widen signal range)

---

### **Category 2: Fundamental Indicators (Expand Existing)**

#### **A. Revenue & Earnings Growth Acceleration**
**Purpose**: Catch "growth on growth" compounders like NVDA
- Fetch quarterly revenue/EPS (last 4 quarters)
- **Score +2**: Revenue growth accelerating (Q-3: 10% → Q-2: 15% → Q-1: 20%+)
- **Score +1**: Earnings growth accelerating (EPS % increase rising)
- **Score 0**: Stable growth (not accelerating/decelerating)
- **Score -1**: Growth decelerating (slowing down)
- **Veto**: Revenue decline for 2+ consecutive quarters

**Data**: yfinance `quarterly_financials` (revenue), `quarterly_earnings` (EPS)

#### **B. Profit Margin Expansion**
**Purpose**: Quality signal (pricing power, efficiency)
- Fetch gross/operating margins (TTM vs 1-year ago)
- **Score +1**: Margins expanding (gaining pricing power)
- **Score 0**: Margins stable
- **Score -1**: Margins contracting (competition/cost pressure)

**Data**: yfinance `info['grossMargins']`, `info['operatingMargins']`

#### **C. Free Cash Flow Quality**
**Purpose**: Better than accounting earnings (real cash generation)
- **Score +1**: FCF > Net Income (high quality earnings)
- **Score +1**: FCF yield > 5% (cheap on cash flow basis)
- **Score -1**: FCF < Net Income (accounting tricks or CapEx heavy)

**Data**: yfinance `info['freeCashflow']`, `info['netIncome']`

**Fundamental Category Impact**: +3-4 new scoring points available

---

### **Category 3: Advanced Indicators (Expand Existing)**

#### **A. Insider Buying Activity**
**Purpose**: Strongest bullish signal (they know before market)
- Fetch SEC Form 4 filings (insider transactions, last 90 days)
- **Score +3**: Cluster buying (3+ insiders buying within 30 days)
- **Score +2**: Large purchase (>$500k by officer/director)
- **Score +1**: Single insider buy (smaller amount)
- **Score -2**: Heavy insider selling (multiple sales)
- **Score 0**: No insider activity

**Data**: yfinance `insider_purchases` / `insider_transactions` (or SEC Edgar API if needed)
**Fallback**: If not available, use institutional ownership changes from `info['heldPercentInstitutions']`

#### **B. Relative Strength Rank vs S&P 500**
**Purpose**: Market leadership (top 20% outperform)
- Calculate 6-month return vs SPY
- Rank percentile across S&P 500
- **Score +2**: Top 20% (RS rank 80-100) - market leader
- **Score +1**: Top 50% (RS rank 50-80) - above average
- **Score 0**: Bottom 50% - laggard
- **Score -1**: Bottom 20% - worst performers

**Data**: Price history (stock vs ^GSPC), already fetched

#### **C. On-Balance Volume (OBV) Divergence**
**Purpose**: Confirm accumulation/distribution
- Calculate cumulative OBV
- **Score +1**: OBV rising while price flat/down (accumulation)
- **Score +1**: OBV confirming price uptrend (healthy)
- **Score -1**: OBV falling while price rising (distribution, warning)

**Data**: Price history with volume (already fetched)

**Advanced Category Impact**: +5-6 new scoring points available

---

### **Category 4: Risk Filters (New Sub-Category within Market Context)**

#### **A. Days Until Earnings**
**Purpose**: Avoid pre-earnings volatility, trade post-earnings clarity
- Fetch next earnings date
- **Score -2**: Earnings within 7 days (high risk, avoid)
- **Score -1**: Earnings within 14 days (risky)
- **Score 0**: Earnings >14 days away (safe)
- **Score +1**: Just reported earnings (<5 days ago, trend clear)

**Data**: yfinance `info['earningsDate']` or `calendar['Earnings Date']`

#### **B. Volatility Risk Adjustment**
**Purpose**: Reduce position size on wild stocks
- Use existing beta, add ATR check
- **Adjust confidence down 20%**: Beta > 1.8 AND ATR > 3%
- **Adjust confidence up 10%**: Beta < 1.0 AND ATR < 1.5%

**Data**: Already have beta, calculate ATR from price history

#### **C. Recent Gap Detection**
**Purpose**: Avoid gap-fill weakness
- Check for large gaps (>5%) in last 5 days
- **Score -1**: Recent gap up unfilled (likely to fill, weakness)
- **Score +1**: Recent gap down filled (strength, bought dip)

**Data**: Price history (daily open vs prior close)

**Risk Filter Impact**: -2 to +1 scoring points (mostly defensive)

---

### **Category 5: Sector-Specific Intelligence**

#### **Pharma/Healthcare Adjustments** (Fixes PFE 51% problem)
- **Lower weight on momentum** (30% → 20%): Pharma moves on FDA news, not momentum
- **Higher weight on fundamentals** (22% → 30%): Value-driven sector
- **Add pipeline check**: Score +1 if R&D spend > 15% of revenue (innovation proxy)
- **Penalize generic exposure**: Score -1 if gross margin < 60% (commodity pharma)

#### **Tech/Growth Adjustments** (Optimize NVDA captures)
- **Higher weight on momentum** (26% → 35%): Trend is your friend in tech
- **Higher weight on advanced** (20% → 25%): Earnings beats, options flow matter more
- **Require revenue acceleration**: Can't get STRONG BUY without accelerating revenue

#### **Retail/Consumer Adjustments**
- **Add same-store sales check**: Score +1 if comp store sales growing
- **Seasonal awareness**: Boost score in Q4 (holiday), reduce in Q1 (post-holiday slump)

#### **Financials Adjustments**
- **Interest rate sensitivity**: Score +1 in rising rate environment (banks benefit)
- **Credit quality**: Require low NPL ratio (non-performing loans < 2%)

**Sector Impact**: Better win rates for weak sectors (PFE → 60%+), stronger signals for winners (NVDA)

---

## Scoring System Adjustments

### **New Score Ranges** (Widen distribution to enable STRONG BUY/SELL)

**Current Problem**: Max score ~6.0 (no STRONG BUY threshold reached)

**Phase 5 Solution**: Add 10-15 new scoring points across categories

| Score Range | Signal | Expected Win Rate | Action |
|-------------|--------|-------------------|--------|
| **≥ 7.5** | **STRONG BUY** | **75-85%** | Max position (5% portfolio) |
| **4.0 to 7.5** | BUY | 65-75% | Standard position (2-3%) |
| **0 to 4.0** | NEUTRAL/HOLD | 55-65% | Small position (0.5-1%) or skip |
| **-4.0 to 0** | WEAK/AVOID | 40-50% | Skip entirely |
| **≤ -4.0** | **STRONG AVOID** | **<35%** | Never trade |

**Why this works**:
- Current system tops out at +6 (all categories maxed)
- Phase 5 adds ~12 new points possible → new max ~18 points
- STRONG BUY at 7.5 = top 10-15% of stocks only
- Prevents mediocre stocks from getting BUY signal

---

## Implementation Approach

### **Integration with Existing System**

**DO NOT create 6th category** - Keep 5-category structure:
1. **Technical** (26% → 28%): Add BB, support/resistance, consolidation, multi-timeframe
2. **Volume** (10%): Keep as-is (already strong)
3. **Fundamental** (22% → 24%): Add revenue acceleration, margins, FCF quality
4. **Market Context** (21% → 20%): Add risk filters (days to earnings, volatility)
5. **Advanced** (20% → 28%): Add insider buying, relative strength, OBV

**Sector Adjustments**: Override base weights dynamically per sector

### **File Structure Changes**

**New Files**:
- `indicators/momentum_advanced.py` - Bollinger Bands, consolidation, multi-timeframe
- `indicators/fundamental_growth.py` - Revenue acceleration, margin trends, FCF
- `indicators/smart_money.py` - Insider buying, institutional changes
- `indicators/risk_filters.py` - Days to earnings, gap detection
- `scoring/sector_adjustments.py` - Sector-specific weight overrides

**Modified Files**:
- `scoring/calculator.py` - Import new indicators, apply sector adjustments
- `config.yaml` - Add Phase 5 thresholds (BB squeeze percentile, RS rank cutoffs, etc.)
- `run_phase4_optimization.py` → `run_optimization.py` - Optimize new indicators

### **Optimization Process**

**Step 1**: Add indicators incrementally (1-2 at a time)
- Test each indicator individually (does it improve win rate?)
- Remove if no improvement (keep system lean)

**Step 2**: Re-run weight optimization
- Existing `run_phase4_optimization.py` script works
- Expands search space to include new indicator weights
- Optimize on 2018-2023 data, validate on 2024 holdout

**Step 3**: Sector-specific optimization
- Run separate optimizations per sector (13 sectors)
- Store sector weight overrides in `config.yaml`

**Step 4**: Adjust score thresholds
- Backtest with new indicators → observe score distribution
- Set STRONG BUY threshold at score where win rate = 75%+
- Set STRONG AVOID threshold at score where win rate = <40%

---

## Expected Performance Improvements

### **Conservative Estimate** (60% of indicators work as expected)

| Metric | Current | Phase 5 Target |
|--------|---------|----------------|
| Overall Win Rate | 63.5% | **70-72%** |
| Bull Market Win Rate | 70% | **75-78%** |
| Bear Market Win Rate | 46% | **55-60%** |
| Avg Return | +3.89% | **+5-6%** |
| Sharpe Ratio | 0.653 | **0.9-1.1** |
| STRONG BUY Trades | 0 | **8-12% of trades** |
| STRONG BUY Win Rate | N/A | **75-85%** |

### **Aggressive Estimate** (80% of indicators work, optimal implementation)

| Metric | Current | Phase 5 Target |
|--------|---------|----------------|
| Overall Win Rate | 63.5% | **73-76%** |
| Avg Return | +3.89% | **+6-8%** |
| Sharpe Ratio | 0.653 | **1.2-1.5** |
| NVDA-like Stocks (high momentum) | 68.6% | **80-85%** |
| PFE-like Stocks (pharma) | 51.2% | **62-65%** |

---

## Risk Considerations

### **What Could Go Wrong**

1. **Overfitting Risk**: Adding 10+ indicators could overfit to 2018-2024 data
   - **Mitigation**: Use walk-forward validation, require statistical significance (p < 0.05)
   - **Mitigation**: Test on out-of-sample data (2025 forward)

2. **Data Quality Issues**: yfinance occasionally has stale/missing data
   - **Mitigation**: Graceful degradation (if insider data missing, score = 0, don't crash)
   - **Mitigation**: Cache validation (reject obviously wrong data)

3. **Complexity Creep**: More indicators = harder to understand/debug
   - **Mitigation**: Document each indicator clearly
   - **Mitigation**: Feature importance analysis (remove low-value indicators)

4. **Execution Risk**: Personal account means real money
   - **Mitigation**: Paper trade Phase 5 for 1-2 months first
   - **Mitigation**: Start with small position sizes on STRONG BUY signals

---

## Development Phases

### **Phase 5a: Quick Wins** ✅ **COMPLETE** (Implemented Nov 2025)
Implemented highest-impact, lowest-complexity indicators:
1. ✅ Relative Strength Rank vs S&P 500 (`indicators/advanced.py`) - S&P 500 percentile ranking
2. ✅ Revenue Growth Acceleration (`indicators/fundamental.py`) - Quarterly revenue trend analysis
3. ✅ Days Until Earnings (`indicators/market_context.py`) - Event risk filter
4. ✅ 52-Week High Breakout (`indicators/technical.py`) - Momentum breakout detection

**Actual Impact**: +1.7% win rate improvement (61.8% → 63.5%), +3% average return improvement
**Status**: Complete, awaiting weight optimization (`python optimization.py`)

### **Phase 5b: Smart Money (2-3 weeks)**
Add data-intensive but high-value signals:
1. Insider Buying (SEC filings, requires parsing)
2. Institutional Ownership Changes (13F filings)
3. OBV Divergence (simple but effective)

**Expected Impact**: +2-4% win rate improvement

### **Phase 5c: Advanced Momentum (2-3 weeks)**
Add sophisticated technical analysis:
1. Bollinger Bands + Squeeze
2. Price Consolidation Detection
3. Multi-Timeframe Alignment
4. Support/Resistance Levels

**Expected Impact**: +2-3% win rate improvement

### **Phase 5d: Sector Intelligence (1-2 weeks)**
Optimize per-sector weights and thresholds:
1. Pharma adjustments (fix PFE)
2. Tech adjustments (optimize NVDA)
3. Retail, Financials adjustments

**Expected Impact**: +1-3% win rate improvement for weak sectors

### **Phase 5e: Integration & Optimization (2-3 weeks)**
1. Update `run_optimization.py` with all new indicators
2. Re-optimize weights on full dataset
3. Adjust score thresholds for STRONG BUY/SELL
4. Comprehensive backtesting report
5. Documentation updates

---

## Success Metrics

### **Phase 5 is successful if**:
1. ✅ Overall win rate improves to **70%+** (from 63.5%)
2. ✅ System generates STRONG BUY signals on **8-12% of trades** with **75%+ win rate**
3. ✅ Bear market win rate improves to **55%+** (from 46.4% in 2022)
4. ✅ High-momentum stocks (NVDA-type) hit **80%+ win rate**
5. ✅ Weak sectors (PFE-type) improve to **60%+ win rate**
6. ✅ Sharpe ratio improves to **>1.0** (from 0.653)
7. ✅ Loss streaks reduced to **<10 trades** (from 16)
8. ✅ Average return increases to **+5-6%** (from +3.89%)

### **Phase 5 fails if**:
1. ❌ Win rate doesn't improve or decreases
2. ❌ Overfitting detected (backtest great, live trading poor)
3. ❌ System becomes too complex to understand/maintain
4. ❌ Data fetching becomes unreliable (too many API calls)
5. ❌ Optimization takes >2 hours to run (too slow for iteration)

---

## Long-Term Vision (Phase 6+)

If Phase 5 succeeds, future enhancements could include:
- **Machine learning**: Train gradient boosting model on historical signals
- **Options strategies**: Sell puts on STRONG BUY stocks (premium income)
- **Portfolio optimization**: Modern portfolio theory for multi-stock allocation
- **Real-time alerts**: Webhook to Discord/Telegram when STRONG BUY appears
- **Automated trading**: Integration with IBKR/Alpaca API for execution
- **Tax optimization**: Harvest losses, hold winners >1 year for long-term capital gains

---

## Conclusion

Phase 5 addresses the key weaknesses identified in backtesting:
- **Narrow signal distribution** → Add 10+ points to enable STRONG BUY/SELL
- **Bear market weakness** → Better risk filters (earnings timing, volatility)
- **Missing momentum winners** → Add acceleration, breakouts, relative strength
- **Sector underperformance** → Pharma/tech/retail specific adjustments
- **Loss streaks** → Better entry timing (consolidation, multi-timeframe)

**Implementation**: Integrate into existing 5-category system, optimize with `run_optimization.py`, test incrementally.

**Expected Outcome**: 70-75% win rate, 5-6% average return, Sharpe >1.0, profitable in all market regimes.

**Timeline**: 6-10 weeks for full implementation (can deploy in stages for faster feedback).

**Risk**: Overfitting, complexity, data quality - mitigate with walk-forward validation and incremental rollout.
