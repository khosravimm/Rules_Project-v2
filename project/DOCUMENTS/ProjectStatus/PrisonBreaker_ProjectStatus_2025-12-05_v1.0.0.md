# PrisonBreaker Project Status Report

meta:
  version: "v1.0.0"
  date: "2025-12-05"
  generator: "Codex Agent"
  source: "PrisonBreaker/Rules_Project-v2"

## Executive Summary
- پایپ‌لاین داده (لودر OHLCV، غنی‌سازی فیچر ۴ساعته) پایدار و عملیاتی است؛ ارزیاب الگوها جهت‌محور شده و از expected_direction استفاده می‌کند.
- دانش پایه ۴h (rules_4h_patterns.yaml v1.0) و عملکرد آن مستند است، اما پشتیبانی فعلی صفر است که نیاز به بازبینی شروط یا بازهٔ داده دارد.
- ساختار KB تقویت شده: ایندکس در MASTER_KNOWLEDGE، سندهای روش‌شناسی (FA/EN)، و مخزن الگوهای ساختاری (project/KNOWLEDGE_BASE/patterns/patterns.yaml) ایجاد شده است.
- ریسک‌ها: عدم یکپارچگی 5m در ارزیاب، عدم همترازی الگوی ثبت‌شده در patterns.yaml با منبع اصلی، و نبود فایل‌های لایه/سیستم.
- اقدام فوری: بازبینی شروط الگوهای ۴h، تعیین منبع کاننیکال برای الگوها، تکمیل اسکلت لایه/سیستم، و تعریف/ارزیابی مسیر 5m.

## Data Pipeline Status
- لودر داده: `src/data/ohlcv_loader.py::load_ohlcv` (کاننیکال، جهت بازار BTCUSDT_PERP، استفاده از CoinEx+Binance، تایم‌زون Asia/Tehran، حذف کندل ناقص).
- منابع داده: پارکت‌های تولیدشده در `data/` شامل `btcusdt_4h_raw.parquet`, `btcusdt_4h_features.parquet` (پس از غنی‌سازی)، و خروجی ارزیابی الگوها.
- اتصال ثانویه: بارگیری جهت‌محور با expected_direction در ارزیاب، بدون خطا پس از غنی‌سازی کامل.

## Feature Engineering Status
- اسکریپت: `src/features/enrich_4h_pattern_features.py`.
- خروجی‌ها: اضافه شدن BODY_PCT_LAST، WICK نسبت‌ها، DIR_4H/DIR_4H_NEXT، RET_4H_LAST/RET_4H_NEXT، آمار رولینگ (RET_SUM_LAST4/5، میانگین بدنه/سایه)، شمارنده‌های UP/DOWN، بکت حجم (VOL_BUCKET_4H_LAST و MAX پنجره ۵)، توالی جهت DIR_SEQ_4H و CONF_SCORE.
- وضعیت: اجرا شده و `data/btcusdt_4h_features.parquet` درجا به‌روز شده است.
- شکاف: مسیر غنی‌سازی 5m تعریف نشده؛ CLOSE_POSITION_LAST مورد استفاده در برخی شرایط YAML در غنی‌سازی فعلی محاسبه نمی‌شود.

## Pattern Mining Progress (L1/L2/4h)
- تعریف الگوهای ۴h: `kb/rules_4h_patterns.yaml` (v1.0، expected_direction افزوده شده).
- الگوی ثبت‌شده ساختاری: `project/KNOWLEDGE_BASE/patterns/patterns.yaml` شامل یک الگوی L2 4h (pbk_4h_abcd1234) با بدنه قوی و سه کندل UP؛ نیاز به هم‌ترازی با منبع اصلی.
- ارزیابی: `data/btcusdt_4h_patterns_stats.parquet` تولید شده اما support همه الگوهای ۴h برابر ۰ است.
- L1/5m: هیچ الگوی رسمی در KB ثبت نشده؛ ارزیابی 5m پیاده‌سازی نشده.

## Evaluator Performance Analysis
- ماژول: `src/patterns/eval_4h_patterns.py` (CLI: `python -m src.patterns.eval_4h_patterns`).
- منطق: ماسک شرایط، جهت موفقیت بر اساس expected_direction، win_rate و baseline_win_rate جهت‌محور، avg_ret از RET_4H_NEXT.
- نتایج فعلی: `kb/rules_4h_patterns_performance.yaml` نشان می‌دهد support=0 برای الگوهای ۴h، status_hint=too_rare؛ علت احتمالی سختی شروط یا ناسازگاری فیچرها (مثلاً نبود CLOSE_POSITION_LAST).
- ریسک: بدون پشتیبانی، هیچ ارزیابی معناداری انجام نمی‌شود؛ نیاز به بازبینی شروط یا بازهٔ زمانی.

## Knowledge Base (KB) Structure & Versioning
- MASTER_KNOWLEDGE: ایندکس پایپ‌لاین ۴h، DOCS، و KNOWLEDGE_BASE_INDEX (patterns فایل جدید). نسخه تاریخچه به‌روز (v0.1.2 با ثبت 2025-12-05T21:15:00Z).
- فایل‌های الگو:
  - `kb/rules_4h_patterns.yaml` v1.0 (با expected_direction و meta به‌روز).
  - `kb/rules_4h_patterns_performance.yaml` v1.0 (متادیتا شامل فایل stats، docs).
  - `project/KNOWLEDGE_BASE/patterns/patterns.yaml` v1.0.0 (ساختاری).
- فایل‌های لایه/سیستم: وجود ندارند؛ اسکلت نیاز است.

## Documentation Status
- اسناد روش‌شناسی: `kb/DISCOVERY_METHODS_4H_v1.0_FA.md`, `kb/DISCOVERY_METHODS_4H_v1.0_EN.md` (وضعیت stable).
- گزارش‌های دیگر: `kb/Documents/PrisonBreaker_Patterns/...` موجود.
- نیاز: هم‌ترازی محتوای الگوهای ساختاری با اسناد روش‌شناسی و افزودن مسیر 5m.

## Gaps & Risks
- پشتیبانی صفر الگوهای ۴h → خروجی ارزیابی بی‌معنا تا زمانی که شروط/فیچرها بازبینی شوند.
- فیچرهای مورد اشاره در YAML (مثلاً CLOSE_POSITION_LAST) در غنی‌سازی فعلی محاسبه نمی‌شود.
- عدم وجود ارزیاب و الگوهای 5m.
- دوگانگی بالقوه بین `kb/rules_4h_patterns.yaml` و `project/KNOWLEDGE_BASE/patterns/patterns.yaml` (نیاز به تعیین منبع کاننیکال و هم‌ترازی IDها).
- لایه/سیستم KB بدون فایل؛ ریسک نبود ساختار برای توسعه بعدی.

## Required Actions
- بازبینی شرایط الگوهای ۴h (آستانه‌ها، فیچرهای استفاده‌شده) و همگن‌سازی با فیچرهای موجود؛ در صورت نیاز محاسبه فیچرهای مفقود مانند CLOSE_POSITION_LAST.
- تصمیم‌گیری درباره منبع کاننیکال الگوها؛ همگام‌سازی `patterns.yaml` با `kb/rules_4h_patterns.yaml` و جلوگیری از تکرار/تعارض ID.
- ایجاد اسکلت `project/KNOWLEDGE_BASE/layers/` و `project/KNOWLEDGE_BASE/system/` با متادیتای پایه.
- تعریف و پیاده‌سازی مسیر 5m (غنی‌سازی و ارزیاب) و ثبت الگوهای 5m در KB.

## Recommended Next Steps
- **تحلیل پشتیبانی صفر**: اجرای مجدد `enrich_4h_pattern_features` و `eval_4h_patterns` پس از بازبینی شروط/فیچرها؛ در صورت لزوم گسترش بازهٔ داده یا تعدیل آستانه‌ها.
- **هم‌ترازسازی KB**: یکی کردن تعریف الگوها (کاننیکال: `kb/rules_4h_patterns.yaml`) و انتقال/تطبیق ورودی `patterns.yaml` با همان ID/ساختار؛ افزودن changelog در متادیتا.
- **گسترش فیچرها**: افزودن محاسبه فیچرهای مورد نیاز شرایط (مثلاً CLOSE_POSITION_LAST) یا حذف/تغییر شروط ناسازگار.
- **مسیر 5m**: طراحی غنی‌سازی فیچر 5m، تعریف الگوها، و افزودن ارزیاب برای 5m؛ به‌روزرسانی اسناد و MASTER_KNOWLEDGE.
- **مستندسازی و نسخه‌دهی**: افزودن نسخه جدید در MASTER_KNOWLEDGE پس از هر تغییر، به‌روزرسانی DOCS در صورت تغییر روش‌ها، و نگهداری تایم‌استمپ ISO در متادیتا.
