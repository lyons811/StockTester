"""
Configuration loader for stock scoring system.
Loads and provides access to config.yaml settings.
"""

import yaml
from pathlib import Path
from typing import Any, Dict, Optional


class Config:
    """Configuration manager for the stock scoring system."""

    _instance = None
    _config: Optional[Dict[str, Any]] = None

    def __new__(cls):
        """Singleton pattern to ensure one config instance."""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        """Load configuration from config.yaml file."""
        # Get the project root directory
        project_root = Path(__file__).parent.parent
        config_path = project_root / "config.yaml"

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, 'r') as file:
            self._config = yaml.safe_load(file)

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            key_path: Path to config value (e.g., 'weights.trend_momentum')
            default: Default value if key not found

        Returns:
            Configuration value or default

        Example:
            config.get('weights.trend_momentum')  # Returns 0.35
        """
        keys = key_path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_weights(self) -> Dict[str, float]:
        """Get category weights."""
        return self.get('weights', {})

    def get_technical_params(self) -> Dict[str, Any]:
        """Get technical indicator parameters."""
        return self.get('technical', {})

    def get_volume_params(self) -> Dict[str, Any]:
        """Get volume analysis parameters."""
        return self.get('volume', {})

    def get_fundamental_params(self) -> Dict[str, Any]:
        """Get fundamental analysis parameters."""
        return self.get('fundamental', {})

    def get_market_params(self) -> Dict[str, Any]:
        """Get market context parameters."""
        return self.get('market', {})

    def get_score_ranges(self) -> Dict[str, float]:
        """Get scoring ranges for normalization."""
        return self.get('score_ranges', {})

    def get_signal_thresholds(self) -> Dict[str, float]:
        """Get signal generation thresholds."""
        return self.get('signals', {})

    def get_position_sizing_params(self) -> Dict[str, Any]:
        """Get position sizing parameters."""
        return self.get('position_sizing', {})

    def get_veto_rules(self) -> Dict[str, Any]:
        """Get automatic veto rules."""
        return self.get('vetoes', {})

    def get_confidence_params(self) -> Dict[str, Any]:
        """Get confidence adjustment parameters."""
        return self.get('confidence', {})

    def get_sector_etf(self, sector: str) -> str:
        """
        Get the appropriate sector ETF for a given sector.

        Args:
            sector: Sector name

        Returns:
            ETF ticker symbol
        """
        sector_etfs = self.get('sector_etfs', {})
        return sector_etfs.get(sector, sector_etfs.get('default', 'SPY'))

    def get_cache_params(self) -> Dict[str, Any]:
        """Get cache configuration."""
        return self.get('cache', {})

    def get_indices(self) -> Dict[str, str]:
        """Get market indices tickers."""
        return self.get('indices', {})


# Global config instance
config = Config()
