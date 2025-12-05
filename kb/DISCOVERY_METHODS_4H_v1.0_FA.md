فایل رسمی ۱ (نسخه فارسی)
kb/DISCOVERY_METHODS_4H_v1.0_FA.md

نسخه: v1.0
تاریخ: 1403/09/16
ساعت: 22:45
پروژه: PrisonBreaker – BTCUSDT Behavioral Pattern Discovery
وضعیت سند: Stable – Approved

🎯 عنوان
گزارش رسمی تکنیک‌های کشف الگو و روابط در پروژه PrisonBreaker (BTCUSDT – 4H/5M)

این سند معماری، روش‌شناسی، تکنیک‌ها و وضعیت فعلی سیستم کشف الگو (Pattern Discovery Engine) در پروژه PrisonBreaker را توضیح می‌دهد. این سند برای استفادهٔ تیم، Codex و موتورهای هوش مصنوعی، و همچنین برای تضمین پایداری فازهای آینده توسعه تهیه شده است.

------------------------------------
۱. بخش‌های کاملاً پیاده‌سازی‌شده (Implemented)
------------------------------------
۱.۱. لودر استاندارد داده (OHLCV Loader)

مسیر: src/data/ohlcv_loader.py

نرمال‌سازی زمان (UTC → Asia/Tehran)

حذف کندل‌های ناقص

ترکیب هوشمند داده‌های CoinEx و Binance

تضمین یکپارچگی داده

خروجی پایدار Parquet:

data/btcusdt_4h_raw.parquet

data/btcusdt_4h_features.parquet

لودر رسمی فقط load_ohlcv() است.
تمام لودرهای قدیمی حذف شده‌اند.

۱.۲. مهندسی ویژگی (Feature Engineering – Core)

مسیر: src/features/enrich_4h_pattern_features.py

فیچرهای کندلی:

BODY_PCT_LAST

UPPER_WICK_PCT_LAST / LOWER_WICK_PCT_LAST

RANGE_PCT

DIR_4H

RET_4H_LAST

فیچرهای آینده‌نگر:

DIR_4H_NEXT

RET_4H_NEXT

توالی‌ها / رفتارها:

DIR_SEQ_4H

DIR_SEQ_4H_CONF_SCORE

رولینگ آمارها:

RET_SUM_LAST4 / RET_SUM_LAST5

BODY_PCT_MEAN_LAST3

UP_COUNT_LAST5 / DOWN_COUNT_LAST5

ویژگی‌های حجمی:

VOL_BUCKET_4H_LAST (LOW/MID/HIGH)

VOL_BUCKET_4H_LAST5_MAX

۱.۳. لایه تعریف الگوها (Pattern Specification Layer)

مسیر: kb/rules_4h_patterns.yaml

هر الگو شامل:

id

window_length

conditions[]

target

expected_direction (UP / DOWN / NONE)

tags

description

هدف اصلی: پیش‌بینی جهت کندل بعدی (DIR_4H_NEXT).

۱.۴. موتور ارزیابی الگوها (Pattern Evaluation Engine)

مسیر: src/patterns/eval_4h_patterns.py

خروجی‌ها:

data/btcusdt_4h_patterns_stats.parquet

kb/rules_4h_patterns_performance.yaml

محاسبات:

support

win_rate (بر اساس expected_direction)

baseline_win_rate

avg_ret

status_hint (strong / medium / weak / too_rare / no_signal)

قابلیت مهم:

win_rate کاملاً direction-aware است.
یعنی اگر expected_direction = DOWN باشد، موفقیت = DOWN است.

------------------------------------
۲. بخش‌های در حال توسعه (In-Progress)
------------------------------------
۲.۱. گسترش الگوهای Multi-Goal

Reversal

Volatility-Shift

Momentum / Anti-Momentum

۲.۲. Confidence Intervals و Robustness

Wilson interval

Bootstrap resampling

Significance metrics

۲.۳. اتصال لایه ۴h → ۵m

Pattern conditioning

Microstructure detection

Multi-timeframe alignment

------------------------------------
۳. برنامه‌های آینده (Planned Roadmap)
------------------------------------
۳.۱. توالی‌کاوی واقعی (Sequence Mining Engine)

PrefixSpan

GSP

SPADE

۳.۲. مدل‌های مارکوف رفتاری

Transition Matrix

Regime Probability Estimation

۳.۳. Backtesting الگومحور

Entry/Exit based on patterns

Position sizing rules

No-overlap signal testing

۳.۴. مدل‌های یادگیری عمیق برای پیشنهاد الگو

TCN

LSTM

Hybrid-AI → Pattern-to-YAML translation

------------------------------------
۴. چرایی وجود این سند (Design Rationale)
------------------------------------

تضمین تکرارپذیری (Reproducibility)

جلوگیری از تضاد نسخه‌ها

جلوگیری از اشتباه Codex در بازتولید ماژول‌ها

شفاف‌سازی مسیر تحقیق

ایجاد رفرنس رسمی برای evolution پروژه

جلوگیری از فراموشی logicهای حساس زمان‌دار

ایجاد backbone برای A/B Testing بلندمدت