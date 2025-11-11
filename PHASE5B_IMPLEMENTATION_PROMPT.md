# Implementation Prompt: Phase 5b Smart Money Tracking

## Context
I have a stock analysis system (StockTester) that scores stocks across 5 categories using technical, volume, fundamental, market context, and advanced indicators. **Phase 5a is complete** with 63.5% win rate (up from 61.8%) after adding relative strength ranking, revenue acceleration, earnings timing, and 52-week breakout detection.

Now I want to implement **Phase 5b: Smart Money Tracking** to capture institutional buying signals and insider confidence, targeting **65-67% win rate**.

## Pre-Implementation Reading
**CRITICAL: Read these files first to understand the system:**
1. `README.md` - Understand Phase 5a results, current architecture, and usage
2. `phase5.md` - Read Phase 5b section (lines ~346-352):
   - Smart Money indicators description
   - Expected impact (+2-4% win rate improvement)
3. `config.yaml` - See Phase 5a configuration structure
4. `scoring/calculator.py` - Understand how Phase 5a indicators were integrated (lines ~415-430)
5. `indicators/advanced.py` - See existing advanced indicators (earnings, analyst, short interest, options, relative strength)
6. `data/fetcher.py` - Understand data fetching patterns, caching, and what's already available

## Your Task: Implement Phase 5b Smart Money Indicators

Implement these 3 indicators (institutional/insider signals):

### 1. **Insider Buying Activity (SEC Form 4)**
- Track insider purchases (Form 4 filings) over last 90 days
- Focus on significant purchases: >$100K, by C-suite/directors (not just routine compensation)
- Score: +2 = Multiple insiders buying (3+), +1 = Single significant purchase, 0 = No activity, -1 = Insider selling
- Add to "Advanced" category (already has earnings, analyst, short interest, options, relative strength)
- **File to create**: `indicators/insider_activity.py`
- **Function**: `calculate_insider_buying(ticker) -> Dict[str, Any]`
- **Data source**: SEC EDGAR API or yfinance `Ticker(ticker).insider_purchases` or `financialdatasets.ai` API (free tier)

**Challenge**: SEC data requires parsing. If too complex, use yfinance `insider_transactions` or skip if unavailable.

### 2. **Institutional Ownership Changes (13F Filings)**
- Calculate institutional ownership % change over last quarter
- Track if smart money (e.g., Vanguard, BlackRock, Berkshire) is accumulating
- Score: +2 = Institutional ownership increasing >5%, +1 = Increasing 0-5%, 0 = Stable, -1 = Decreasing >5%
- Add to "Advanced" category
- **File to create**: `indicators/institutional_flow.py`
- **Function**: `calculate_institutional_changes(ticker) -> Dict[str, Any]`
- **Data source**: yfinance `Ticker(ticker).institutional_holders` or `major_holders`

**Challenge**: 13F data is quarterly, may be stale. Use latest available, mark data age in output.

### 3. **On-Balance Volume (OBV) Divergence**
- Calculate OBV from price/volume data (already fetched)
- Detect bullish divergence: Price making lower lows, OBV making higher lows (accumulation)
- Detect bearish divergence: Price making higher highs, OBV making lower highs (distribution)
- Score: +2 = Bullish divergence, +1 = OBV trending up, 0 = Neutral, -1 = OBV trending down, -2 = Bearish divergence
- Add to "Volume" category (currently only has volume trend and volume-price relationship)
- **File to create**: `indicators/obv_analysis.py`
- **Function**: `calculate_obv_divergence(stock_df) -> Dict[str, Any]`
- **Data source**: Existing `stock_df` (already has price/volume history)

**Challenge**: Divergence detection requires identifying peaks/troughs. Use simple 20-day rolling comparison if complex.

## Implementation Steps

### Step 1: Create New Indicator Files

Create the 3 new indicator files listed above. Follow the existing Phase 5a pattern:
- Each function returns `Dict[str, Any]` with keys: `'score'`, `'signal'`, `'explanation'`, and relevant data
- Handle missing data gracefully (return `score=0`, `signal='Data unavailable'`)
- Add docstrings explaining the logic and scoring
- Use the cache system (fetcher already caches data with 24h TTL)

### Step 2: Update config.yaml

Add Phase 5b configuration section after Phase 5a:

```yaml
# Phase 5b: Smart Money Tracking
phase5b:
  insider_buying:
    lookback_days: 90  # 3 months
    significant_purchase_threshold: 100000  # $100K+ purchases
    multiple_insiders_threshold: 3  # 3+ insiders buying

  institutional_flow:
    ownership_increase_significant: 0.05  # 5% increase threshold
    ownership_increase_moderate: 0.0  # Any increase
    major_institutions:  # Weight these more heavily
      - "Vanguard Group Inc"
      - "BlackRock Inc."
      - "State Street Corporation"
      - "Berkshire Hathaway Inc"

  obv_divergence:
    lookback_days: 60  # 2-3 months for divergence detection
    trend_period: 20  # Simple trend detection window
```

### Step 3: Integrate into Calculator

**Modify `scoring/calculator.py`:**

**For Insider + Institutional (Advanced category):**
```python
# In calculate_all_advanced_indicators() function (around line 529)
from indicators.insider_activity import calculate_insider_buying
from indicators.institutional_flow import calculate_institutional_changes

insider_result = calculate_insider_buying(ticker)
institutional_result = calculate_institutional_changes(ticker)

raw_score += insider_result['score'] + institutional_result['score']
```

**For OBV (Volume category):**
```python
# In indicators/volume.py, modify calculate_all_volume_indicators()
from indicators.obv_analysis import calculate_obv_divergence

obv_result = calculate_obv_divergence(df)
raw_score += obv_result['score']
```

### Step 4: Update Score Ranges in config.yaml

The max scores will change because we're adding new points:

```yaml
score_ranges:
  trend_max: 10.0  # No change from Phase 5a
  volume_max: 5.0  # Phase 5b: Was 3.0, now +2 from OBV divergence (-2 to +2)
  fundamental_max: 8.0  # No change from Phase 5a
  market_max: 7.0  # No change from Phase 5a
  advanced_max: 17.0  # Phase 5b: Was 13.0, now +4 from insider (+2) + institutional (+2)
```

**New total max: 47 points** (was 41 in Phase 5a)

### Step 5: Update Formatter

**Modify `utils/formatter.py` to display the new indicators:**

**Volume section (add OBV):**
```python
# After volume_price indicator (around line 114)
if 'obv_divergence' in vol:
    obv = vol['obv_divergence']
    print(f"  • OBV Divergence:    {obv['score']:+2d}  ({obv['signal']})")
```

**Advanced section (add insider + institutional):**
```python
# After relative_strength indicator (around line 217)
if 'insider_buying' in adv:
    insider = adv['insider_buying']
    print(f"  • Insider Buying:    {insider.get('score', 0):+2d}  ({insider.get('explanation', 'N/A')})")

if 'institutional_flow' in adv:
    inst = adv['institutional_flow']
    print(f"  • Institutional Flow: {inst.get('score', 0):+2d}  ({inst.get('explanation', 'N/A')})")
```

### Step 6: Test

```bash
# Test on a single stock first (one with known insider buying)
python main.py NVDA

# Should see new indicators in output:
# [VOLUME & INSTITUTIONS]: +X/5
#   • Volume Trend: +X
#   • Volume-Price: +X
#   • OBV Divergence: +X (Bullish divergence detected)

# [ADVANCED FEATURES]: +X/17
#   • ...existing indicators...
#   • Insider Buying: +2 (3 C-suite purchases, $2.5M total)
#   • Institutional Flow: +1 (Ownership increased 2.3%)

# Run backtest to verify improvement
python main.py --backtest
# Target: Win rate should increase from 63.5% to 65-67%

# Run optimization (IMPORTANT after Phase 5b!)
python optimization.py --walk-forward
```

## Important Constraints

1. **Use existing patterns**: Copy Phase 5a indicator structure from `technical.py`, `fundamental.py`, `advanced.py`
2. **Cache everything**: Use `fetcher.get_stock_data()` and `fetcher.get_stock_info()` which have built-in caching
3. **Fail gracefully**: If insider/institutional data is missing (common for smaller caps), return `score=0` with `explanation='Data unavailable'`. Don't crash.
4. **Keep it simple**: If SEC parsing is too complex, use yfinance simplified data or mark as TODO
5. **Test incrementally**: Add one indicator at a time, test it works, then move to next
6. **Document everything**: Add clear docstrings explaining the smart money logic

## Data Availability Concerns

**✅ Likely Available:**
- OBV calculation (price/volume already fetched)
- yfinance `institutional_holders` (top 10 institutions)
- yfinance `major_holders` (% institutional ownership)

**⚠️ May Be Limited:**
- Insider transactions (yfinance has `insider_transactions`, but may be incomplete)
- Detailed 13F filings (quarterly, 45-day lag)
- Form 4 real-time data (requires SEC EDGAR API parsing)

**Fallback Strategy:**
If SEC data is unavailable/too complex:
- Use yfinance `insider_transactions` (simplified)
- Use yfinance `institutional_holders` (top 10 only)
- Mark indicators as "Beta - Limited Data" in output
- Still valuable signal even if incomplete

## Expected Outcome

After implementing Phase 5b, you should see:
- ✅ 3 new smart money indicators integrated
- ✅ Config.yaml updated with Phase 5b thresholds
- ✅ Backtest win rate improves by 1.5-3.5% (from 63.5% to ~65-67%)
- ✅ NVDA/MSFT-type stocks with insider buying score higher
- ✅ Stocks with institutional accumulation flagged as higher conviction
- ✅ OBV divergence catches early accumulation/distribution

## Files You'll Modify/Create

**New files (create):**
- `indicators/insider_activity.py`
- `indicators/institutional_flow.py`
- `indicators/obv_analysis.py`

**Modified files:**
- `scoring/calculator.py` (import and integrate insider + institutional into advanced)
- `indicators/volume.py` (integrate OBV into volume category)
- `config.yaml` (add Phase 5b config, update score ranges: volume 5, advanced 17)
- `utils/formatter.py` (display new indicators in output)
- `phase5.md` (mark Phase 5b complete after implementation)
- `README.md` (document Phase 5b features)

**Files to read for context (don't modify yet):**
- `phase5.md` (your implementation guide)
- `indicators/advanced.py` (see Phase 5a relative strength pattern)
- `indicators/technical.py` (see Phase 5a 52-week breakout pattern)
- `data/fetcher.py` (understand what yfinance data is available)

## Questions to Ask If Stuck

1. **"How do I access insider data?"** → Try `yfinance.Ticker(ticker).insider_transactions` or `.insider_purchases`, check if available
2. **"How do I detect OBV divergence?"** → Compare price peaks/troughs to OBV peaks/troughs over 60-day window, simple is fine
3. **"Where do I add institutional flow?"** → Add to `indicators/advanced.py` similar to relative strength (Phase 5a example)
4. **"Why isn't my indicator showing up?"** → Check if it's added to `formatter.py` and calculator integration

## Success Criteria

Phase 5b is complete when:
1. ✅ All 3 indicators implemented and tested (insider, institutional, OBV)
2. ✅ Backtest shows improvement (win rate up 1.5-3.5% from 63.5%)
3. ✅ No errors when running `python main.py NVDA`
4. ✅ Output shows new indicators in formatted report
5. ✅ Config.yaml properly updated (score ranges: volume 5, advanced 17)
6. ✅ `python optimization.py` completes successfully with Phase 5b indicators

---

**START HERE**: Read README.md and phase5.md first, then begin implementing the 3 indicators one at a time. Test each one before moving to the next. Ask clarifying questions if needed.

**Prioritize**: If insider/institutional data is too hard to get, implement OBV first (guaranteed to work), then tackle the others.
