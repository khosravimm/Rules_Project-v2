from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from data.ohlcv_loader import load_ohlcv


def main() -> None:
    df = load_ohlcv(
        market="BTCUSDT_PERP",
        timeframe="4h",
        n_candles=200,
        primary_exchange="coinex_futures",
        secondary_exchange="binance_futures",
    )
    print(df.head())
    print(f"Total rows: {len(df)}")


if __name__ == "__main__":
    main()
