# SEPABacktester Bug - Timezone Mismatch (NEEDS FIX)

## Problem
The backtester runs but finds **0 SEPA-qualified stocks** despite processing 4,670 stocks over 79 weeks.

## Debug Output
```
FILTERING SUMMARY (across all weeks):
  Passed Finviz filter: 124,771  ← WORKS
  Had valid RS scores: 0         ← ALL FAIL HERE
  RS >= 70: 0
  Passed Stage 2: 0
  Passed Fundamentals: 0
```

## Root Cause: Timezone Mismatch
The `calculate_ibd_rs_historical()` function (and similar functions) compare dates incorrectly:

```python
df = price_df[price_df.index <= as_of_date]  # THIS FAILS SILENTLY
```

**Why it fails:**
- `as_of_date` is a **naive datetime** (no timezone info)
- `price_df.index` is **timezone-aware** (yfinance returns US/Eastern timestamps)
- Pandas can't compare these, so the filter fails or returns empty

## The Fix
Add timezone conversion at the start of each historical analysis function:

```python
def calculate_ibd_rs_historical(ticker, spy_df, price_df, as_of_date):
    # FIX: Make as_of_date timezone-aware to match price data
    if price_df.index.tz is not None:
        as_of_date = pd.Timestamp(as_of_date).tz_localize(price_df.index.tz)

    # Now this comparison works correctly
    df = price_df[price_df.index <= as_of_date]
    ...
```

## Functions That Need This Fix
1. `calculate_ibd_rs_historical()` - line ~495
2. `passes_finviz_filter_historical()` - line ~435
3. `analyze_stage_historical()` - line ~530
4. `calculate_atr_percent_historical()` - line ~590
5. `track_performance()` - line ~640

## Alternative Fix (Simpler)
Create a helper function and use it everywhere:

```python
def normalize_date_for_comparison(as_of_date, df_index):
    """Ensure as_of_date matches the timezone of the dataframe index"""
    if hasattr(df_index, 'tz') and df_index.tz is not None:
        return pd.Timestamp(as_of_date).tz_localize(df_index.tz)
    return pd.Timestamp(as_of_date)
```

Then at the start of each function:
```python
as_of_date = normalize_date_for_comparison(as_of_date, price_df.index)
```

## To Test After Fix
Run the backtester again - you should see non-zero values for RS scores and subsequent stages:
```bash
python SEPABacktester.py
```

Expected output should show stocks progressing through all filters, with some reaching SEPA qualified status.
