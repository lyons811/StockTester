"""
Output formatter for stock scoring results.
Formats results in a readable console-friendly format.
"""

from datetime import datetime
from typing import Any
from scoring.calculator import StockScore


def format_currency(value: float) -> str:
    """Format large numbers as currency."""
    if value >= 1e12:
        return f"${value/1e12:.2f}T"
    elif value >= 1e9:
        return f"${value/1e9:.2f}B"
    elif value >= 1e6:
        return f"${value/1e6:.2f}M"
    else:
        return f"${value:,.0f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format value as percentage."""
    return f"{value:.{decimals}f}%"


def format_score_bar(normalized_score: float, max_score: float) -> str:
    """Create a visual score bar."""
    percentage = (normalized_score / max_score) * 100
    if percentage >= 75:
        return "BULLISH"
    elif percentage >= 50:
        return "POSITIVE"
    elif percentage >= -50:
        return "NEUTRAL"
    elif percentage >= -75:
        return "NEGATIVE"
    else:
        return "BEARISH"


def print_header(score: StockScore) -> None:
    """Print analysis header."""
    print("=" * 64)
    print(f"STOCK ANALYSIS: {score.ticker} ({score.company_name})")
    print(f"DATE: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"SECTOR: {score.sector} | MARKET CAP: {format_currency(score.market_cap)}")
    print("=" * 64)
    print()


def print_veto_message(score: StockScore) -> None:
    """Print veto message."""
    print("=" * 64)
    print("AUTOMATIC VETO - STOCK DISQUALIFIED")
    print("=" * 64)
    print()
    print("This stock has been automatically disqualified due to:")
    print()
    for i, reason in enumerate(score.veto_reasons, 1):
        print(f"{i}. {reason}")
    print()
    print("RECOMMENDATION: DO NOT TRADE")
    print("=" * 64)


def print_overall_score(score: StockScore) -> None:
    """Print overall score and signal."""
    print(f"OVERALL SIGNAL: {score.signal}")
    print(f"SCORE: {score.final_score:+.1f} / 10")
    confidence_pct = min(score.confidence * 100, 100)
    print(f"CONFIDENCE: {confidence_pct:.0f}%")
    print(f"RECOMMENDED POSITION: {score.position_size_pct:.1f}% of portfolio")
    print()
    print(f"PROBABILITY ESTIMATES (1-3 month timeframe):")
    print(f"  ^ Higher:   {score.probability_higher}")
    print(f"  v Lower:    {score.probability_lower}")
    print(f"  - Sideways: {score.probability_sideways}")
    print()


def print_category_breakdown(score: StockScore) -> None:
    """Print detailed category breakdown."""
    print("=" * 64)
    print("CATEGORY BREAKDOWN")
    print("=" * 64)
    print()

    # Technical indicators
    tech = score.technical
    tech_pct = (tech['normalized_score'] / 100) * 100
    tech_status = format_score_bar(tech['normalized_score'], 100)

    print(f"[TREND & MOMENTUM]: {tech['raw_score']:+.1f}/10 ({tech_pct:+.0f}%) - {tech_status}")  # Phase 5a: updated max from 6 to 10
    print(f"  • MA Position:       {tech['ma_position']['score']:+2d}  ({tech['ma_position']['signal']})")
    print(f"  • 12-month Momentum: {tech['momentum']['score']:+2d}  ({format_percentage(tech['momentum']['momentum_percent'], 1)} - {tech['momentum']['signal']})")
    print(f"  • RSI (14):          {tech['rsi']['score']:+2d}  ({tech['rsi']['rsi']:.0f} - {tech['rsi']['signal']})")
    print(f"  • MACD:              {tech['macd']['score']:+2d}  ({tech['macd']['signal']})")

    # Phase 5a: 52-week breakout
    if 'breakout_52week' in tech:
        breakout = tech['breakout_52week']
        print(f"  • 52-Week Breakout:  {breakout['score']:+2d}  ({breakout['signal']})")
    print()

    # Volume indicators
    vol = score.volume
    vol_pct = (vol['normalized_score'] / 100) * 100
    vol_status = format_score_bar(vol['normalized_score'], 100)

    print(f"[VOLUME & INSTITUTIONS]: {vol['raw_score']:+.1f}/3 ({vol_pct:+.0f}%) - {vol_status}")
    print(f"  • Volume Trend:      {vol['volume_trend']['score']:+2d}  ({vol['volume_trend']['signal']})")
    print(f"  • Volume-Price:      {vol['volume_price']['score']:+2d}  ({vol['volume_price']['signal']})")
    print()

    # Fundamental indicators
    fund = score.fundamental
    fund_pct = (fund['normalized_score'] / 100) * 100
    fund_status = format_score_bar(fund['normalized_score'], 100)

    print(f"[FUNDAMENTALS]: {fund['raw_score']:+.1f}/8 ({fund_pct:+.0f}%) - {fund_status}")  # Phase 5a: updated max from 5 to 8

    # P/E
    pe_val = fund['pe']['pe_ratio']
    pe_str = f"{pe_val:.1f}" if pe_val is not None else "N/A"
    print(f"  • P/E Ratio:         {fund['pe']['score']:+2d}  ({pe_str} - {fund['pe']['signal']})")

    # PEG
    peg_val = fund['peg']['peg_ratio']
    peg_str = f"{peg_val:.2f}" if peg_val is not None else "N/A"
    print(f"  • PEG Ratio:         {fund['peg']['score']:+2d}  ({peg_str} - {fund['peg']['signal']})")

    # ROE
    roe_val = fund['roe']['roe_percent']
    roe_str = f"{roe_val:.1f}%" if roe_val is not None else "N/A"
    print(f"  • ROE:               {fund['roe']['score']:+2d}  ({roe_str} - {fund['roe']['signal']})")

    # Debt/Equity
    debt_val = fund['debt_equity']['debt_to_equity']
    debt_str = f"{debt_val:.2f}" if debt_val is not None else "N/A"
    print(f"  • Debt/Equity:       {fund['debt_equity']['score']:+2d}  ({debt_str} - {fund['debt_equity']['signal']})")

    # Cash Flow
    cf_val = fund['cash_flow_quality']['cash_flow_quality']
    cf_str = f"{cf_val:.2f}" if cf_val is not None else "N/A"
    print(f"  • Cash Flow Quality: {fund['cash_flow_quality']['score']:+2d}  ({cf_str} - {fund['cash_flow_quality']['signal']})")

    # Phase 5a: Revenue Acceleration
    if 'revenue_acceleration' in fund:
        revenue = fund['revenue_acceleration']
        print(f"  • Revenue Growth:    {revenue['score']:+2d}  ({revenue['signal']})")
    print()

    # Market context
    mkt = score.market
    mkt_pct = (mkt['normalized_score'] / 100) * 100
    mkt_status = format_score_bar(mkt['normalized_score'], 100)

    print(f"[MARKET CONTEXT]: {mkt['raw_score']:+.1f}/7 ({mkt_pct:+.0f}%) - {mkt_status}")  # Phase 5a: updated max from 4 to 7

    # VIX
    vix_val = mkt['vix']['vix_value']
    vix_str = f"{vix_val:.1f}" if vix_val is not None else "N/A"
    print(f"  • VIX Level:         {mkt['vix']['score']:+2d}  ({vix_str} - {mkt['vix']['signal']})")

    # Sector Relative
    sector_val = mkt['sector_relative']['relative_strength']
    sector_str = f"{sector_val:+.1f}%" if sector_val != 0 else "N/A"
    print(f"  • Sector Relative:   {mkt['sector_relative']['score']:+2d}  ({sector_str} vs {mkt.get('sector_etf', 'SPY')})")

    # Market Regime
    regime = mkt['market_regime']['regime']
    print(f"  • Market Regime:     {mkt['market_regime']['score']:+2d}  ({regime} market)")

    # Phase 5a: Earnings Timing
    if 'earnings_timing' in mkt:
        earnings_timing = mkt['earnings_timing']
        print(f"  • Earnings Timing:   {earnings_timing['score']:+2d}  ({earnings_timing['signal']})")
    print()

    # Phase 3: Advanced indicators (Phase 5a: updated to include relative strength)
    if score.advanced:
        adv = score.advanced
        adv_pct = (adv['normalized_score'] / 100) * 100
        adv_status = format_score_bar(adv['normalized_score'], 100)

        print(f"[ADVANCED FEATURES]: {adv['raw_score']:+.1f}/13 ({adv_pct:+.0f}%) - {adv_status}")  # Phase 5a: updated max from 10 to 13

        # Earnings Quality
        earnings = adv.get('earnings_quality', {})
        if earnings:
            earnings_exp = earnings.get('explanation', 'N/A')
            print(f"  • Earnings Quality:  {earnings.get('score', 0):+2d}  ({earnings_exp})")

        # Analyst Revisions
        analyst = adv.get('analyst_revisions', {})
        if analyst:
            analyst_exp = analyst.get('explanation', 'N/A')
            print(f"  • Analyst Revisions: {analyst.get('score', 0):+2d}  ({analyst_exp})")

        # Short Interest
        short = adv.get('short_interest', {})
        if short:
            short_exp = short.get('explanation', 'N/A')
            print(f"  • Short Interest:    {short.get('score', 0):+2d}  ({short_exp})")

        # Options Flow
        options = adv.get('options_flow', {})
        if options:
            options_exp = options.get('explanation', 'N/A')
            print(f"  • Options Flow:      {options.get('score', 0):+2d}  ({options_exp})")

        # Phase 5a: Relative Strength vs S&P 500
        if 'relative_strength' in adv:
            rs = adv['relative_strength']
            print(f"  • Relative Strength: {rs.get('score', 0):+2d}  ({rs.get('explanation', 'N/A')})")

        print()


def print_key_factors(score: StockScore) -> None:
    """Print key bullish and bearish factors."""
    print("=" * 64)
    print("KEY BULLISH FACTORS")
    print("=" * 64)

    bullish_factors = []

    # Technical factors
    tech = score.technical
    if tech['ma_position']['score'] > 0:
        bullish_factors.append(f"+ {tech['ma_position']['signal']}")
    if tech['momentum']['score'] > 0:
        bullish_factors.append(f"+ Strong momentum: {tech['momentum']['momentum_percent']:+.1f}%")
    if tech['rsi']['score'] > 0:
        bullish_factors.append(f"+ RSI oversold: {tech['rsi']['rsi']:.0f}")
    if tech['macd']['score'] > 0:
        bullish_factors.append(f"+ MACD: {tech['macd']['signal']}")

    # Volume factors
    vol = score.volume
    if vol['volume_trend']['score'] > 0:
        bullish_factors.append(f"+ {vol['volume_trend']['signal']}")
    if vol['volume_price']['score'] > 0:
        bullish_factors.append(f"+ {vol['volume_price']['signal']}")

    # Fundamental factors
    fund = score.fundamental
    if fund['pe']['score'] > 0:
        bullish_factors.append(f"+ Attractive valuation: P/E {fund['pe']['pe_ratio']:.1f}")
    if fund['peg']['score'] > 0:
        bullish_factors.append(f"+ Good growth value: PEG {fund['peg']['peg_ratio']:.2f}")
    if fund['roe']['score'] > 0:
        bullish_factors.append(f"+ Excellent ROE: {fund['roe']['roe_percent']:.1f}%")
    if fund['debt_equity']['score'] > 0:
        bullish_factors.append(f"+ Healthy balance sheet: D/E {fund['debt_equity']['debt_to_equity']:.2f}")
    if fund['cash_flow_quality']['score'] > 0:
        bullish_factors.append(f"+ Strong cash flow quality: {fund['cash_flow_quality']['cash_flow_quality']:.2f}")

    # Market factors
    mkt = score.market
    if mkt['vix']['score'] > 0:
        bullish_factors.append(f"+ {mkt['vix']['signal']}")
    if mkt['sector_relative']['score'] > 0:
        bullish_factors.append(f"+ Outperforming sector by {mkt['sector_relative']['relative_strength']:+.1f}%")
    if mkt['market_regime']['score'] > 0:
        bullish_factors.append(f"+ {mkt['market_regime']['regime']} market regime")

    # Phase 3: Advanced factors
    if score.advanced:
        adv = score.advanced
        if adv.get('earnings_quality', {}).get('score', 0) > 0:
            bullish_factors.append(f"+ {adv['earnings_quality']['explanation']}")
        if adv.get('analyst_revisions', {}).get('score', 0) > 0:
            bullish_factors.append(f"+ {adv['analyst_revisions']['explanation']}")
        if adv.get('short_interest', {}).get('score', 0) > 0:
            bullish_factors.append(f"+ {adv['short_interest']['explanation']}")
        if adv.get('options_flow', {}).get('score', 0) > 0:
            bullish_factors.append(f"+ {adv['options_flow']['explanation']}")

    if bullish_factors:
        for factor in bullish_factors:
            print(factor)
    else:
        print("None identified")
    print()

    # Bearish factors
    print("=" * 64)
    print("KEY RISK FACTORS")
    print("=" * 64)

    risk_factors = []

    # Technical risks
    if tech['ma_position']['score'] < 0:
        risk_factors.append(f"- {tech['ma_position']['signal']}")
    if tech['momentum']['score'] < 0:
        risk_factors.append(f"- Weak momentum: {tech['momentum']['momentum_percent']:+.1f}%")
    if tech['rsi']['score'] < 0:
        risk_factors.append(f"- RSI overbought: {tech['rsi']['rsi']:.0f}")
    if tech['macd']['score'] < 0:
        risk_factors.append(f"- MACD: {tech['macd']['signal']}")

    # Volume risks
    if vol['volume_trend']['score'] < 0:
        risk_factors.append(f"- {vol['volume_trend']['signal']}")
    if vol['volume_price']['score'] < 0:
        risk_factors.append(f"- {vol['volume_price']['signal']}")

    # Fundamental risks
    if fund['pe']['score'] < 0:
        risk_factors.append(f"- {fund['pe']['signal']}: P/E {fund['pe']['pe_ratio']:.1f}" if fund['pe']['pe_ratio'] else f"- {fund['pe']['signal']}")
    if fund['peg']['score'] < 0:
        risk_factors.append(f"- {fund['peg']['signal']}")
    if fund['debt_equity']['debt_to_equity'] and fund['debt_equity']['debt_to_equity'] > 1.5:
        risk_factors.append(f"- Elevated debt: D/E {fund['debt_equity']['debt_to_equity']:.2f}")

    # Market risks
    if mkt['vix']['score'] < 0:
        risk_factors.append(f"- {mkt['vix']['signal']}")
    if mkt['sector_relative']['score'] < 0:
        risk_factors.append(f"- Underperforming sector by {abs(mkt['sector_relative']['relative_strength']):.1f}%")
    if mkt['market_regime']['score'] < 0:
        risk_factors.append(f"- {mkt['market_regime']['regime']} market regime (headwinds)")

    # Beta risk
    if score.beta > 1.5:
        risk_factors.append(f"- High volatility: Beta {score.beta:.2f}")

    # Phase 3: Advanced risk factors
    if score.advanced:
        adv = score.advanced
        if adv.get('earnings_quality', {}).get('score', 0) < 0:
            risk_factors.append(f"- {adv['earnings_quality']['explanation']}")
        if adv.get('analyst_revisions', {}).get('score', 0) < 0:
            risk_factors.append(f"- {adv['analyst_revisions']['explanation']}")
        if adv.get('short_interest', {}).get('score', 0) < 0:
            risk_factors.append(f"- {adv['short_interest']['explanation']}")
        if adv.get('options_flow', {}).get('score', 0) < 0:
            risk_factors.append(f"- {adv['options_flow']['explanation']}")

    if risk_factors:
        for factor in risk_factors:
            print(factor)
    else:
        print("Minimal risks identified")
    print()


def format_stock_score(score: StockScore) -> None:
    """
    Format and print complete stock score.

    Args:
        score: StockScore object
    """
    print("\n")
    print_header(score)

    if score.is_vetoed:
        print_veto_message(score)
        return

    print_overall_score(score)
    print_category_breakdown(score)
    print_key_factors(score)

    print("=" * 64)
    print()
