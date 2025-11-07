"""
Backtesting module for validating stock scoring system performance.

This module provides:
- Historical performance analysis
- Win rate calculation by score ranges
- Weight optimization framework
- Walk-forward validation
"""

from .engine import BacktestEngine
from .metrics import PerformanceMetrics
from .optimizer import WeightOptimizer

__all__ = ['BacktestEngine', 'PerformanceMetrics', 'WeightOptimizer']
