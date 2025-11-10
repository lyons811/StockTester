#!/usr/bin/env python3
"""
S&P 500 Bulk Stock Analyzer
Analyzes all S&P 500 stocks and returns the best opportunities based on scoring thresholds.

Usage:
    python analyze_sp500.py                          # STRONG BUY only (score >= 6.0)
    python analyze_sp500.py --min-score 3.0          # Include BUY signals
    python analyze_sp500.py --limit 20               # Test on first 20 stocks
    python analyze_sp500.py --output my_results.csv  # Custom output file
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from io import StringIO
import pandas as pd
import requests
from tqdm import tqdm
from typing import Dict, Optional

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scoring.calculator import calculate_stock_score, StockScore


def fetch_sp500_tickers() -> pd.DataFrame:
    """
    Fetch the current S&P 500 constituent list from Wikipedia.

    Returns:
        DataFrame with columns: Symbol, Security (company name), GICS Sector
    """
    print("Fetching S&P 500 ticker list from Wikipedia...")

    try:
        # Read S&P 500 table from Wikipedia with proper User-Agent header
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'

        # Add User-Agent header to avoid 403 Forbidden error
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # Fetch HTML with requests
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Parse with pandas (wrap in StringIO to avoid FutureWarning)
        tables = pd.read_html(StringIO(response.text))
        sp500_table = tables[0]

        # Rename columns for consistency
        sp500_table = sp500_table.rename(columns={
            'Symbol': 'ticker',
            'Security': 'company',
            'GICS Sector': 'sector'
        })

        # Select relevant columns
        sp500_list = sp500_table[['ticker', 'company', 'sector']].copy()

        print(f"[OK] Found {len(sp500_list)} S&P 500 stocks\n")
        return sp500_list

    except Exception as e:
        print(f"Error fetching S&P 500 list: {e}")
        print("Please check your internet connection or try again later.")
        sys.exit(1)


def analyze_stock(ticker: str) -> Optional[Dict]:
    """
    Analyze a single stock and return results as a dictionary.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dictionary with analysis results, or None if analysis failed
    """
    try:
        score_data: StockScore = calculate_stock_score(ticker)

        # Extract key metrics
        return {
            'ticker': ticker,
            'company': score_data.company_name,
            'sector': score_data.sector,
            'market_cap': score_data.market_cap,
            'signal': score_data.signal,
            'score': score_data.final_score,
            'confidence': score_data.confidence,
            'position_size': score_data.position_size_pct,
            'probability_higher': score_data.probability_higher,
            'probability_lower': score_data.probability_lower,
            'probability_sideways': score_data.probability_sideways
        }

    except Exception:
        # Return None if analysis fails (will be filtered out)
        return None


def analyze_sp500(min_score: float = 6.0, limit: Optional[int] = None) -> pd.DataFrame:
    """
    Analyze all S&P 500 stocks and return those meeting the score threshold.

    Args:
        min_score: Minimum score threshold (default: 6.0 for STRONG BUY)
        limit: Optional limit on number of stocks to analyze (for testing)

    Returns:
        DataFrame with analysis results for qualifying stocks
    """
    # Fetch S&P 500 ticker list
    sp500_tickers = fetch_sp500_tickers()

    # Apply limit if specified (for testing)
    if limit:
        sp500_tickers = sp500_tickers.head(limit)
        print(f"[!] Test mode: analyzing first {limit} stocks only\n")

    # Initialize results storage
    results = []
    errors = []
    strong_buy_count = 0

    # Progress bar setup
    print(f"Analyzing {len(sp500_tickers)} stocks (min score: {min_score})...")
    print("This may take 15-30 minutes on first run (faster with cached data)\n")

    # Analyze each stock with progress bar
    for idx, row in tqdm(sp500_tickers.iterrows(),
                         total=len(sp500_tickers),
                         desc="Progress",
                         unit="stock",
                         ncols=100):

        ticker = row['ticker']

        # Analyze stock
        result = analyze_stock(ticker)

        if result is None:
            # Log error
            errors.append(ticker)
            tqdm.write(f"[X] {ticker}: Analysis failed")
            continue

        # Check if meets threshold
        if result['score'] >= min_score:
            results.append(result)
            strong_buy_count += 1
            tqdm.write(f"[+] {ticker}: {result['signal']} (Score: {result['score']:.1f}, Position: {result['position_size']:.1f}%)")

    print(f"\n{'='*80}")
    print(f"Analysis Complete!")
    print(f"{'='*80}")
    print(f"Total analyzed: {len(sp500_tickers)}")
    print(f"Qualified stocks (score >= {min_score}): {strong_buy_count}")
    print(f"Failed analyses: {len(errors)}")

    if errors:
        print(f"\nFailed tickers: {', '.join(errors[:10])}")
        if len(errors) > 10:
            print(f"... and {len(errors) - 10} more")

    # Convert to DataFrame
    if results:
        results_df = pd.DataFrame(results)
        # Sort by position size (highest first)
        results_df = results_df.sort_values('position_size', ascending=False)
        return results_df
    else:
        print(f"\n[!] No stocks found with score >= {min_score}")
        return pd.DataFrame()


def save_results_csv(results_df: pd.DataFrame, output_file: str):
    """
    Save analysis results to CSV file.

    Args:
        results_df: DataFrame with analysis results
        output_file: Output CSV filename
    """
    if results_df.empty:
        print("\nNo results to save.")
        return

    # Save to CSV
    results_df.to_csv(output_file, index=False)
    print(f"\n[OK] Results saved to: {output_file}")

    # Also save error log if needed
    # (can be implemented later)


def display_console_summary(results_df: pd.DataFrame, min_score: float):
    """
    Display a formatted summary of top stocks in the console.

    Args:
        results_df: DataFrame with analysis results
        min_score: Minimum score threshold used
    """
    if results_df.empty:
        return

    print(f"\n{'='*80}")
    print(f"TOP OPPORTUNITIES (Score >= {min_score})")
    print(f"{'='*80}\n")

    # Show top 20 stocks (or all if fewer)
    top_stocks = results_df.head(20)

    # Format table
    print(f"{'Rank':<5} {'Ticker':<8} {'Company':<25} {'Sector':<18} {'Score':<6} {'Pos%':<6} {'Signal'}")
    print(f"{'-'*80}")

    for idx, row in enumerate(top_stocks.itertuples(), start=1):
        company_str = str(row.company)
        sector_str = str(row.sector)
        company_short = company_str[:23] + '..' if len(company_str) > 25 else company_str
        sector_short = sector_str[:16] + '..' if len(sector_str) > 18 else sector_str

        print(f"{idx:<5} {row.ticker:<8} {company_short:<25} {sector_short:<18} "
              f"{row.score:<6.1f} {row.position_size:<6.1f} {row.signal}")

    # Sector breakdown
    print(f"\n{'='*80}")
    print("SECTOR BREAKDOWN")
    print(f"{'='*80}")
    sector_counts = results_df['sector'].value_counts()
    for sector, count in sector_counts.items():
        print(f"  {sector}: {count} stocks")

    print(f"\n{'='*80}\n")


def main():
    """Main entry point for S&P 500 bulk analyzer."""

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Analyze all S&P 500 stocks and find the best opportunities',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze_sp500.py                          # STRONG BUY only (score >= 6.0)
  python analyze_sp500.py --min-score 3.0          # Include BUY signals
  python analyze_sp500.py --limit 20               # Test on first 20 stocks
  python analyze_sp500.py --output my_results.csv  # Custom output file
        """
    )

    parser.add_argument(
        '--min-score',
        type=float,
        default=6.0,
        help='Minimum score threshold (default: 6.0 for STRONG BUY, 3.0 for BUY)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default='sp500_analysis_results.csv',
        help='Output CSV filename (default: sp500_analysis_results.csv)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit analysis to first N stocks (for testing)'
    )

    args = parser.parse_args()

    # Print header
    print(f"\n{'='*80}")
    print(f"S&P 500 BULK STOCK ANALYZER")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*80}\n")

    # Run analysis
    results_df = analyze_sp500(min_score=args.min_score, limit=args.limit)

    # Save results to CSV
    save_results_csv(results_df, args.output)

    # Display console summary
    display_console_summary(results_df, args.min_score)

    print(f"Analysis complete! Check {args.output} for full results.\n")


if __name__ == '__main__':
    main()
