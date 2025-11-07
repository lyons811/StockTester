"""
Stock Scoring System - Phase 1 MVP
CLI entry point for analyzing stocks.

Usage: python main.py TICKER
Example: python main.py AAPL
"""

import sys
import argparse
from typing import Optional

from scoring.calculator import calculate_stock_score
from utils.formatter import format_stock_score


def main():
    """Main CLI entry point."""
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Stock Scoring System - Analyze stocks using professional hedge fund methodologies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py AAPL          # Analyze Apple
  python main.py MSFT          # Analyze Microsoft
  python main.py TSLA          # Analyze Tesla

Output:
  - Overall score (-10 to +10) and signal (Buy/Sell/Hold)
  - Detailed breakdown of technical, volume, fundamental, and market indicators
  - Position sizing recommendation
  - Key bullish factors and risk factors

Data Sources:
  - Yahoo Finance (via yfinance library)
  - Cached for 24 hours to respect rate limits
        """
    )

    parser.add_argument(
        'ticker',
        type=str,
        help='Stock ticker symbol to analyze (e.g., AAPL, MSFT, TSLA)'
    )

    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable caching and fetch fresh data'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='Stock Scoring System v1.0.0 (Phase 1 MVP)'
    )

    # Parse arguments
    args = parser.parse_args()

    # Validate ticker
    ticker = args.ticker.strip().upper()
    if not ticker:
        print("Error: Ticker symbol cannot be empty")
        sys.exit(1)

    # Display welcome message
    print("\n" + "=" * 64)
    print("STOCK SCORING SYSTEM - PHASE 1 MVP")
    print("Based on Professional Hedge Fund Methodologies")
    print("=" * 64)
    print(f"\nAnalyzing: {ticker}")
    print()

    try:
        # Calculate score
        score = calculate_stock_score(ticker)

        # Format and display results
        format_stock_score(score)

        # Exit with appropriate code
        if score.is_vetoed:
            sys.exit(2)  # Vetoed stock
        elif score.final_score >= 3:
            sys.exit(0)  # Buy signal
        elif score.final_score <= -3:
            sys.exit(3)  # Sell signal
        else:
            sys.exit(0)  # Neutral

    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user.")
        sys.exit(130)

    except Exception as e:
        print(f"\nError: {str(e)}")
        print("\nPlease check:")
        print("1. Ticker symbol is valid")
        print("2. Internet connection is active")
        print("3. All dependencies are installed (run: pip install -r requirements.txt)")
        sys.exit(1)


if __name__ == "__main__":
    main()
