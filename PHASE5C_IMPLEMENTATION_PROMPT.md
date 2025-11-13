# Implementation Prompt: Phase 5c Sector Intelligence

## Context
I have a stock analysis system (StockTester) that scores stocks across 5 categories using technical, volume, fundamental, market context, and advanced indicators. **Phase 5b is complete** with 72.4% win rate (up from 63.5% in Phase 5a) after adding:
- ✅ Bollinger Band squeeze detection (volatility compression)
- ✅ ATR consolidation patterns ("coiling spring" setups)
- ✅ Multi-timeframe trend alignment (daily/weekly)
- ✅ Short-term support/resistance levels (60-day)
- ✅ OBV divergence analysis (accumulation/distribution)

**Performance Metrics (Phase 5b):**
- ✅ Win Rate: **72.4%** (+8.9% improvement!)
- ✅ Avg Return: **+6.14%** (+58% improvement)
- ✅ Sharpe Ratio: **1.160**
- ✅ Annualized Return: **+37.32%**
- ✅ Total Test Trades: 105

However, **sector-specific performance varies significantly**:
- Technology (NVDA, AAPL, MSFT): 75%+ win rate ✅ *Excellent*
- Retail/Consumer (WMT): 70%+ win rate ✅ *Good*
- Healthcare/Pharma (PFE): ~51% win rate ❌ *Needs work*
- Energy (XOM): ~60% win rate ⚠️ *Could improve*

Now I want to implement **Phase 5c: Sector Intelligence** to optimize sector-specific scoring adjustments, targeting **75%+ win rate across ALL sectors**.

## Pre-Implementation Reading
**CRITICAL: Read these files first to understand the system:**
1. `README.md` - Understand Phase 5b results, current architecture, and usage
2. `phase5.md` - Read Phase 5c section (lines ~359-365):
   - Sector Intelligence description
   - Expected impact (+1-3% win rate for weak sectors)
3. `config.yaml` - See current sector adjustments (lines ~167-299):
   - Weight multipliers per sector (e.g., Technology: trend_momentum 1.2x, fundamental 0.9x)
   - Threshold overrides (e.g., Healthcare: pe_fair 30 vs default 25)
4. `scoring/calculator.py` - Understand `get_sector_adjusted_weights()` function (lines ~253-303)
5. `backtesting/engine.py` - See how backtest tracks per-sector performance
6. `phase4_validation_report.md` - Review sector-specific win rates from recent backtest

## Your Task: Implement Phase 5c Sector Intelligence

Optimize per-sector scoring to address underperforming sectors (Healthcare, Energy) and maximize strong sectors (Technology, Retail).

### **Approach: Data-Driven Sector Optimization**

1. **Analyze Current Sector Performance**
   - Run backtest with detailed sector breakdown: `python main.py --backtest --sector-analysis`
   - Identify which sectors underperform and why
   - Example findings:
     - Healthcare (PFE): Low momentum stocks penalized too heavily by technical indicators
     - Energy (XOM): Cyclical nature not captured by revenue growth acceleration
     - Technology (NVDA): Already optimized well, but could emphasize momentum more

2. **Implement Sector-Specific Indicator Adjustments**
   - **File to modify**: `config.yaml` (expand `sector_adjustments` section, lines 167-299)
   - Add new sector-specific rules:

```yaml
sector_adjustments:
  # Technology: Momentum-heavy sector
  Technology:
    weight_multipliers:
      trend_momentum: 1.3  # Emphasize momentum (was 1.2)
      fundamental: 0.85    # De-emphasize traditional valuation (was 0.9)
      advanced: 1.2        # Emphasize relative strength, options flow
    threshold_overrides:
      pe_fair: 40          # Higher P/E acceptable (was 35)
      peg_attractive: 1.8  # More lenient PEG (was 1.5)
      momentum_strong_threshold: 20  # Lower bar for "strong" momentum (was 25)
    indicator_overrides:
      # NEW: Sector-specific indicator behavior
      bollinger_squeeze_weight: 1.5  # 1.5x weight for BB squeeze in tech
      obv_divergence_weight: 1.3     # 1.3x weight for OBV in tech

  # Healthcare: Defensive, low-momentum sector
  Healthcare:
    weight_multipliers:
      trend_momentum: 0.7   # De-emphasize momentum (was 0.9)
      fundamental: 1.4      # Emphasize fundamentals (was 1.2)
      market_context: 0.8   # Less sensitive to market regime (was 0.9)
    threshold_overrides:
      pe_fair: 25           # Lower P/E expectations (was 30)
      roe_quality: 15.0     # Higher ROE requirement (was 12.0)
      momentum_strong_threshold: 15  # Easier to qualify as "strong" (was 25)
    indicator_overrides:
      # NEW: Adjust momentum indicators for low-vol sector
      rsi_overbought: 75    # Higher overbought threshold (was 70)
      rsi_oversold: 25      # Lower oversold threshold (was 30)
      consolidation_weight: 0.5  # 0.5x weight for consolidation patterns

  # Energy: Cyclical, commodity-driven sector
  Energy:
    weight_multipliers:
      market_context: 1.5   # Emphasize macro/commodity trends (was 1.3)
      volume: 1.3           # Institutional flow important (was 1.2)
      fundamental: 0.7      # Less weight on growth metrics (was 0.9)
    threshold_overrides:
      debt_equity_healthy: 2.0  # Higher debt acceptable (was 1.5)
      revenue_growth_required: -5.0  # Allow revenue declines in downturns (was 0)
    indicator_overrides:
      # NEW: Adjust for cyclical nature
      revenue_acceleration_weight: 0.3  # Don't penalize for cyclical revenue (was 1.0)
      relative_strength_weight: 1.5     # S&P 500 relative strength more important (was 1.0)

  # Financials: Leverage-sensitive, interest rate driven
  Financial Services:
    weight_multipliers:
      fundamental: 1.4      # Balance sheet quality critical (was 1.3)
      market_context: 1.3   # Sensitive to Fed policy/rates (was 0.9)
      trend_momentum: 0.8   # Less momentum-driven (was 0.9)
    threshold_overrides:
      debt_equity_healthy: 5.0  # Banks have high leverage (was 3.0)
      roe_quality: 10.0     # Lower ROE acceptable (was 12.0)
    indicator_overrides:
      # NEW: Adjust for leverage/rates sensitivity
      vix_bearish_threshold: 25  # More cautious in volatility (was 30)
      earnings_timing_weight: 1.5  # Banks sensitive to earnings (was 1.0)
```

3. **Add Indicator Override Logic**
   - **File to modify**: `scoring/calculator.py`
   - Update score calculation to apply sector-specific indicator weights
   - Example:
```python
def apply_sector_overrides(indicator_scores: Dict, sector: str) -> Dict:
    """
    Apply sector-specific indicator weight adjustments (Phase 5c).

    Args:
        indicator_scores: Raw indicator scores
        sector: Stock sector

    Returns:
        Adjusted indicator scores
    """
    overrides = config.get(f'sector_adjustments.{sector}.indicator_overrides', {})

    if not overrides:
        return indicator_scores

    adjusted = indicator_scores.copy()

    # Technical indicators
    if 'bollinger_squeeze_weight' in overrides:
        adjusted['technical']['bollinger_bands']['score'] *= overrides['bollinger_squeeze_weight']

    if 'consolidation_weight' in overrides:
        adjusted['technical']['consolidation']['score'] *= overrides['consolidation_weight']

    # Volume indicators
    if 'obv_divergence_weight' in overrides:
        adjusted['volume']['obv_divergence']['score'] *= overrides['obv_divergence_weight']

    # Advanced indicators
    if 'relative_strength_weight' in overrides:
        adjusted['advanced']['relative_strength']['score'] *= overrides['relative_strength_weight']

    if 'revenue_acceleration_weight' in overrides:
        adjusted['fundamental']['revenue_growth']['score'] *= overrides['revenue_acceleration_weight']

    return adjusted
```

4. **Add Sector-Specific Backtesting Analysis**
   - **File to modify**: `backtesting/engine.py`
   - Add `--sector-analysis` flag to generate per-sector performance report
   - Output format:
```
SECTOR PERFORMANCE BREAKDOWN
================================================================

Technology (NVDA, AAPL, MSFT):
  Trades: 35
  Win Rate: 77.1% (+4.7% vs Phase 5b)
  Avg Return: +7.82% (+27% improvement)
  Best Indicator: Bollinger Squeeze (1.5x weight applied)

Healthcare (PFE):
  Trades: 18
  Win Rate: 61.1% (+10.1% vs Phase 5b!)
  Avg Return: +2.34% (+5.7x improvement)
  Impact: Momentum de-weighting (0.7x), fundamental emphasis (1.4x)

Energy (XOM):
  Trades: 15
  Win Rate: 66.7% (+6.7% vs Phase 5b)
  Avg Return: +4.12% (+39% improvement)
  Impact: Relative strength emphasis (1.5x), revenue flexibility

OVERALL: 75.3% win rate (+2.9% vs Phase 5b)
```

5. **Implement Smart Sector Detection Enhancements**
   - **File to modify**: `data/fetcher.py`
   - Add fallback sector mapping for edge cases (e.g., "Finance" → "Financial Services")
   - Validate sector mapping on stock fetch

## Implementation Steps

### Step 1: Add Sector-Specific Backtesting Analysis

**Modify `backtesting/engine.py`:**

Add sector breakdown tracking:
```python
# Track performance by sector
sector_performance = {}
for trade in trades:
    sector = trade.get('sector', 'Unknown')
    if sector not in sector_performance:
        sector_performance[sector] = {
            'trades': [],
            'wins': 0,
            'losses': 0,
            'total_return': 0
        }

    sector_performance[sector]['trades'].append(trade)
    if trade['return'] > 0:
        sector_performance[sector]['wins'] += 1
    else:
        sector_performance[sector]['losses'] += 1
    sector_performance[sector]['total_return'] += trade['return']

# Print sector breakdown
if sector_analysis:
    print("\n" + "="*80)
    print("SECTOR PERFORMANCE BREAKDOWN")
    print("="*80)

    for sector, data in sorted(sector_performance.items(), key=lambda x: len(x[1]['trades']), reverse=True):
        trades_count = len(data['trades'])
        win_rate = (data['wins'] / trades_count * 100) if trades_count > 0 else 0
        avg_return = (data['total_return'] / trades_count) if trades_count > 0 else 0

        print(f"\n{sector}:")
        print(f"  Trades: {trades_count}")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Avg Return: {avg_return:+.2f}%")
```

### Step 2: Expand Sector Adjustments in config.yaml

Add `indicator_overrides` subsection to each sector in `sector_adjustments` (lines 167-299).

### Step 3: Implement Indicator Override Logic in calculator.py

Add `apply_sector_overrides()` function and call it after calculating raw indicator scores.

### Step 4: Test on Individual Sectors

```bash
# Test Healthcare improvements
python main.py PFE

# Expected: Higher fundamental weight, lower momentum penalties
# Should see: Better score than Phase 5b (was likely NEUTRAL, now targeting BUY)

# Test Technology
python main.py NVDA

# Expected: Bollinger squeeze 1.5x weight, momentum 1.3x weight
# Should see: Even stronger STRONG BUY signal

# Test Energy
python main.py XOM

# Expected: Relative strength emphasis, revenue flexibility
```

### Step 5: Run Sector-Aware Backtest

```bash
python main.py --backtest --sector-analysis

# Target results:
# - Overall win rate: 74-76% (up from 72.4%)
# - Healthcare win rate: 60%+ (up from ~51%)
# - Energy win rate: 65%+ (up from ~60%)
# - Technology maintained: 75%+ (from 75%+)
```

### Step 6: Re-optimize Weights with Sector Intelligence

```bash
python optimization.py

# This will optimize category weights WITH sector adjustments applied
# Expected: Slight weight shifts to accommodate sector-specific behaviors
```

## Important Constraints

1. **Preserve Phase 5b gains**: Don't break what's working in Technology sector
2. **Data-driven**: Base adjustments on actual backtest performance, not assumptions
3. **Graceful degradation**: If sector unknown, use default weights (no crash)
4. **Document rationale**: Each sector adjustment should have comment explaining why
5. **Test incrementally**: Add one sector adjustment at a time, validate improvement

## Expected Outcome

After implementing Phase 5c, you should see:
- ✅ Overall win rate: **74-76%** (up from 72.4%)
- ✅ Healthcare win rate: **60%+** (up from ~51%)
- ✅ Energy win rate: **65%+** (up from ~60%)
- ✅ Technology maintained: **75%+**
- ✅ Sector-specific indicator weights applied automatically
- ✅ Backtesting shows per-sector breakdown
- ✅ Config.yaml has comprehensive sector adjustments

## Files You'll Modify

**Modified files:**
- `config.yaml` - Add `indicator_overrides` to each sector (lines 167-299)
- `scoring/calculator.py` - Add `apply_sector_overrides()` function
- `backtesting/engine.py` - Add `--sector-analysis` flag and reporting
- `data/fetcher.py` (optional) - Enhance sector mapping validation

**Files to read for context:**
- `phase5.md` (Phase 5c specification, lines 359-365)
- `config.yaml` (current sector adjustments, lines 167-299)
- `scoring/calculator.py` (existing sector weight logic, lines 253-303)
- `phase4_validation_report.md` (sector performance baseline)

## Success Criteria

Phase 5c is complete when:
1. ✅ Sector-specific indicator overrides implemented and tested
2. ✅ Backtesting shows per-sector breakdown with `--sector-analysis` flag
3. ✅ Healthcare win rate improves to 60%+ (from ~51%)
4. ✅ Overall win rate reaches 74-76% (from 72.4%)
5. ✅ No regression in Technology sector performance
6. ✅ Config.yaml has documented rationale for each sector adjustment
7. ✅ `python optimization.py` completes successfully with Phase 5c adjustments

---

**START HERE**: Read phase5.md (lines 359-365) and phase4_validation_report.md for sector performance baseline, then implement sector-specific backtesting first to identify exact areas for improvement.

**Prioritize**: If time-constrained, focus on:
1. Healthcare sector (biggest opportunity: +10% win rate potential)
2. Energy sector (cyclical adjustments needed)
3. Technology sector (fine-tuning for perfection)
