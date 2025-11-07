"""
Stock Scoring System - Phase 2
CLI entry point for analyzing stocks, backtesting, and optimization.

Usage:
  python main.py TICKER                    # Analyze a stock
  python main.py --backtest                # Run backtest on default portfolio
  python main.py --optimize-weights        # Optimize category weights
Example: python main.py AAPL
"""

import sys
import argparse

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
        nargs='?',
        help='Stock ticker symbol to analyze (e.g., AAPL, MSFT, TSLA)'
    )

    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable caching and fetch fresh data'
    )

    parser.add_argument(
        '--backtest',
        action='store_true',
        help='Run backtesting on default portfolio (Phase 2)'
    )

    parser.add_argument(
        '--optimize-weights',
        action='store_true',
        help='Run weight optimization using grid search (Phase 2)'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='Stock Scoring System v2.0.0 (Phase 2)'
    )

    # Parse arguments
    args = parser.parse_args()

    # Phase 2: Handle backtesting mode
    if args.backtest:
        from backtesting.engine import BacktestEngine
        from backtesting.metrics import PerformanceMetrics
        from utils.config import config

        print("\n" + "=" * 70)
        print("STOCK SCORING SYSTEM - BACKTESTING MODE (PHASE 2)")
        print("=" * 70)

        try:
            # Get backtest config
            backtest_config = config.get('backtesting', {})
            tickers = backtest_config.get('default_tickers', ['AAPL', 'MSFT', 'TSLA', 'NVDA'])
            start_date = backtest_config.get('start_date', '2022-01-01')
            end_date = backtest_config.get('end_date', '2025-01-01')
            holding_period = backtest_config.get('holding_period_days', 60)

            # Run backtest
            engine = BacktestEngine(start_date, end_date, holding_period)
            trades = engine.run_backtest(tickers)

            # Generate metrics and report
            metrics = PerformanceMetrics(trades)
            metrics.print_summary_report()

            # Export results
            engine.export_trades_csv("backtest_results.csv")

            sys.exit(0)

        except Exception as e:
            print(f"\nBacktesting Error: {str(e)}")
            sys.exit(1)

    # Phase 2: Handle weight optimization mode
    if args.optimize_weights:
        from backtesting.engine import BacktestEngine
        from backtesting.optimizer import WeightOptimizer
        from utils.config import config

        print("\n" + "=" * 70)
        print("STOCK SCORING SYSTEM - WEIGHT OPTIMIZATION MODE (PHASE 2)")
        print("=" * 70)

        try:
            # Get backtest config
            backtest_config = config.get('backtesting', {})
            tickers = backtest_config.get('default_tickers', ['AAPL', 'MSFT', 'TSLA', 'NVDA'])
            start_date = backtest_config.get('start_date', '2022-01-01')
            end_date = backtest_config.get('end_date', '2024-01-01')  # Train on first 2 years

            # Create backtest engine
            engine = BacktestEngine(start_date, end_date)

            # Run optimizer
            optimizer = WeightOptimizer(engine)
            best_weights, best_score = optimizer.optimize_weights(tickers)

            # Export optimal weights
            optimizer.export_optimal_weights(best_weights, "optimized_weights.yaml")

            print(f"\nOptimization complete! Best win rate: {best_score:.2f}%")
            print("Optimal weights exported to optimized_weights.yaml")

            sys.exit(0)

        except Exception as e:
            print(f"\nOptimization Error: {str(e)}")
            sys.exit(1)

    # Standard mode: Validate ticker
    if not args.ticker:
        print("Error: Ticker symbol required (or use --backtest/--optimize-weights)")
        parser.print_help()
        sys.exit(1)

    ticker = args.ticker.strip().upper()
    if not ticker:
        print("Error: Ticker symbol cannot be empty")
        sys.exit(1)

    # Display welcome message
    print("\n" + "=" * 64)
    print("STOCK SCORING SYSTEM - PHASE 2")
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
