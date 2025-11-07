"""
File-based cache manager for API responses.
Reduces API calls and respects rate limits.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timedelta


class CacheManager:
    """Manages file-based caching of API responses."""

    def __init__(self, cache_dir: str = "cache", default_duration_hours: int = 24):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory to store cache files
            default_duration_hours: Default cache duration in hours
        """
        self.cache_dir = Path(cache_dir)
        self.default_duration = default_duration_hours * 3600  # Convert to seconds

        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        """
        Get cache file path for a given key.

        Args:
            key: Cache key (e.g., ticker symbol or data type)

        Returns:
            Path to cache file
        """
        # Sanitize key to be filesystem-safe
        safe_key = key.replace('/', '_').replace('\\', '_').replace('^', '_')
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str, max_age_hours: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve data from cache if it exists and is not expired.

        Args:
            key: Cache key
            max_age_hours: Maximum age in hours (overrides default if provided)

        Returns:
            Cached data or None if not found or expired
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        # Check if cache is expired
        file_mtime = cache_path.stat().st_mtime
        current_time = time.time()
        max_age = (max_age_hours * 3600) if max_age_hours is not None else self.default_duration

        if current_time - file_mtime > max_age:
            # Cache expired, remove it
            cache_path.unlink()
            return None

        # Read and return cached data
        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, IOError) as e:
            # Corrupted cache file, remove it
            cache_path.unlink()
            return None

    def set(self, key: str, data: Dict[str, Any]) -> None:
        """
        Store data in cache.

        Args:
            key: Cache key
            data: Data to cache (must be JSON serializable)
        """
        cache_path = self._get_cache_path(key)

        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except (IOError, TypeError) as e:
            # If caching fails, log but don't crash
            print(f"Warning: Failed to cache data for {key}: {e}")

    def invalidate(self, key: str) -> None:
        """
        Invalidate (delete) a cache entry.

        Args:
            key: Cache key to invalidate
        """
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()

    def clear_all(self) -> None:
        """Clear all cache files."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()

    def get_cache_info(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a cache entry.

        Args:
            key: Cache key

        Returns:
            Dictionary with cache info or None if not found
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        file_mtime = cache_path.stat().st_mtime
        age_hours = (time.time() - file_mtime) / 3600

        return {
            'key': key,
            'path': str(cache_path),
            'age_hours': age_hours,
            'modified': datetime.fromtimestamp(file_mtime).isoformat(),
            'size_bytes': cache_path.stat().st_size
        }


# Global cache instance
cache = CacheManager()
