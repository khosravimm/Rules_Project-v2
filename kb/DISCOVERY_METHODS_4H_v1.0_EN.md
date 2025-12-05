فایل رسمی ۲ (نسخه انگلیسی)
kb/DISCOVERY_METHODS_4H_v1.0_EN.md

Version: v1.0
Date: 2024-12-06
Time: 22:45 IRST
Project: PrisonBreaker – BTCUSDT Behavioral Pattern Discovery
Status: Stable – Approved

Comprehensive Report on Pattern Discovery Techniques in PrisonBreaker (BTCUSDT – 4H/5M)

This document formally describes the methodology, architecture, techniques and current progress of the Pattern Discovery Engine used in the PrisonBreaker project.
All concepts are categorized into:

Implemented

In-progress

Planned

to maintain scientific clarity and technical traceability.

------------------------------------
1. Implemented Components
------------------------------------
1.1. Standard OHLCV Loader

src/data/ohlcv_loader.py

Full timezone normalization

Removal of incomplete candles

Smart stitching of CoinEx ↔ Binance futures

Stable Parquet outputs

Official loader: load_ohlcv()
Legacy loaders removed.

1.2. Feature Engineering Engine

src/features/enrich_4h_pattern_features.py

Candle Geometry

BODY_PCT_LAST, WICK_PCT, DIR_4H, RET_4H_LAST

Next-Candle Targets

DIR_4H_NEXT, RET_4H_NEXT

Behavioral Features

DIR_SEQ_4H, DIR_SEQ_4H_CONF_SCORE

Rolling Metrics

RET_SUM_LAST4/5, BODY/WICK means, UP_COUNT_LAST5

Volume Buckets

VOL_BUCKET_4H_LAST, VOL_BUCKET_4H_LAST5_MAX

1.3. Pattern Specification Layer

kb/rules_4h_patterns.yaml

Patterns contain:

conditions[]

target

expected_direction (UP/DOWN/NONE)

metadata

1.4. Pattern Evaluation Engine

src/patterns/eval_4h_patterns.py

Outputs:

Parquet numerical results

YAML performance summaries

Metrics:

support

win_rate (direction-aware)

baseline_win_rate

avg_ret

status_hint

------------------------------------
2. In-Progress Components
------------------------------------
Multi-goal patterns
Confidence Intervals
4H → 5M Multi-Timeframe Conditioning
------------------------------------
3. Planned Components
------------------------------------
Sequence Mining (PrefixSpan/GSP)
Markov Behavioral Modeling
Pattern-Based Backtesting
Neural Generators for Pattern Proposal (TCN/LSTM)
------------------------------------
4. Why This Document Is Required
------------------------------------

Ensures reproducibility

Maintains system memory

Prevents Codex from reintroducing deprecated modules

Defines long-term A/B research structure

Prevents architectural drift

Enables stable knowledge accumulation