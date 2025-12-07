from __future__ import annotations

from typing import Dict

import pandas as pd

from .schema import _standardize_df


def load_crypto_aggregate(metric: str) -> pd.DataFrame:
    """
    Load aggregated crypto metrics via CoinGecko (pycoingecko).
    Supported metrics examples: total_market_cap_usd, btc_dominance.
    """
    try:
        from pycoingecko import CoinGeckoAPI  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "pycoingecko is required for load_crypto_aggregate. Install with `pip install pycoingecko`."
        ) from exc

    cg = CoinGeckoAPI()
    data = cg.get_global().get("data", {})
    val = None
    if metric == "total_market_cap_usd":
        val = data.get("total_market_cap", {}).get("usd")
    elif metric == "btc_dominance":
        val = data.get("market_cap_percentage", {}).get("btc")
    else:
        val = data.get(metric)

    df = pd.DataFrame([val], columns=["value"])
    df.index = pd.to_datetime([pd.Timestamp.utcnow()], utc=True)
    meta: Dict = {"metric": metric}
    return _standardize_df(df, source="coingecko", metadata=meta)
