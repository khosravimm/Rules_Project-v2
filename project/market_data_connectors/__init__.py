"""
Unified datafeed package for PrisonBreaker.
"""

from .router import MarketKind, load_market_series
from .crypto_ccxt import load_crypto_ohlcv
from .traditional_yfinance import load_traditional_ohlcv
from .traditional_alpha_vantage import load_alpha_series
from .macro_fred import load_macro_series
from .crypto_aggregate_coingecko import load_crypto_aggregate

__all__ = [
    "MarketKind",
    "load_market_series",
    "load_crypto_ohlcv",
    "load_traditional_ohlcv",
    "load_alpha_series",
    "load_macro_series",
    "load_crypto_aggregate",
]
