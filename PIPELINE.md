## Pipeline Execution Guide (PrisonBreaker / BTC Futures)

این راهنما مراحل اجرایی پایپلاین‌ها را مطابق MASTER_KNOWLEDGE و KB_SCHEMA بیان می‌کند. همهٔ خروجی‌ها باید در `kb/btcusdt_4h_knowledge.yaml` (یا فایل‌های شکسته‌شدهٔ هم‌سو با Schema) ثبت و سپس با `rules-kb validate` تأیید شوند.

### 1) پیش‌نیازها
- Python ≥ 3.11، پکیج‌ها مطابق `pyproject.toml` (`pydantic`, `pyyaml`, `pytest` برای dev).
- دادهٔ خام 4h و 5m (2 ساله) و در صورت اجرای Cross-Market، دادهٔ multi_market_4h.
- حذف کندل ناقص، همگن‌سازی timezone (مثلاً UTC یا Asia/Tehran) و ذخیره در مسیرهای زیر:
  - `data/btcusdt_4h_features.parquet`
  - `data/btcusdt_5m_raw.parquet`
  - `data/multi_market_4h.parquet` (برای Lead-Lag/Cross-Market)

### 2) اجرای پایپلاین‌ها (ترتیب پیشنهادی)
1. **data_prep_4h5m**
   - ورودی: دادهٔ خام 4h/5m.
   - خروجی: `data/btcusdt_4h_features.parquet`, `data/btcusdt_5m_raw.parquet`.
   - اقدام بعدی: به‌روزرسانی بخش `datasets` اگر نسخهٔ جدیدی تولید شده است.

2. **discover_patterns_btc**
   - ورودی: `data/btcusdt_4h_features.parquet`, `data/btcusdt_5m_raw.parquet`.
   - خروجی: به‌روزرسانی `kb/btcusdt_4h_knowledge.yaml` (بخش‌های `patterns`, `clusters`).
   - یادداشت: الگوهای forward/backward/meta روی پنجره‌های 2..11؛ نتیجه باید با دقت دسته‌بندی شود (very_strong…very_weak).

3. **evaluate_trading_rules_btc**
   - ورودی: `kb/btcusdt_4h_knowledge.yaml`, `data/btcusdt_4h_features.parquet`.
   - خروجی: به‌روزرسانی `trading_rules`, `backtests`, `performance_over_time`, `status_history`.
   - یادداشت: استفاده از الگوها + شروط اضافی؛ خروجی باید شامل متریک‌ها و تاریخچهٔ وضعیت باشد.

4. **cross_market_analysis**
   - ورودی: `data/multi_market_4h.parquet`, `kb/btcusdt_4h_knowledge.yaml`.
   - خروجی: به‌روزرسانی `market_relations` (lead-lag, granger, corr) و `cross_market_patterns`.
   - یادداشت: مشخص کنید کدام مارکت جلوتر است (best_lag_other_leads_base, corr_at_best_lag, granger_p_value).

5. **continuous_rebacktest_and_refresh** (دوره‌ای: ماهانه یا بر اساس N کندل 4h)
   - ورودی: KB فعلی + خروجی‌های دادهٔ آماده + دادهٔ multi_market.
   - خروجی: به‌روزرسانی جامع همهٔ بخش‌ها (patterns, trading_rules, backtests, performance_over_time, status_history, cross_market_patterns, market_relations) و افزایش `kb_version`.
   - یادداشت: پایش drift، ارتقای الگوهای متوسط/ضعیف در صورت بهبود، و حذف/تنزل الگوهای ناکارآمد.

### 3) ولیدیشن و مستندسازی
- پس از هر مرحله، `rules-kb validate` را اجرا کنید:
  ```bash
  rules-kb validate --master-path project/MASTER_KNOWLEDGE.yaml --knowledge-dir kb
  ```
- KB باید با `KB_SCHEMA.yaml` سازگار باشد؛ ID یکتا و ارجاع‌های معتبر الزامی است.
- در هر به‌روزرسانی مهم، `kb_version` افزایش یابد و `notes` در KB، SPEC و SUMMARY_FA به‌روزرسانی شود.

### 4) آزمون و کنترل کیفیت
- تست‌ها را اجرا کنید:
  ```bash
  pytest
  ```
- برای روش‌های جدید (الگوریتم/مدل)، آزمون‌های آماری و کنترل چندآزمونی (White’s RC/SPA، permutation/surrogate) انجام دهید؛ نتایج باید در بخش‌های متناسب (patterns/trading_rules/backtests/performance_over_time) ثبت شود.

### 5) ابزار
- انتخاب ادیتور/IDE آزاد است (VS Code/Codex یا هر ابزار دیگر)؛ خروجی باید با Schema و ولیدیشن هم‌خوان باشد.
- از تولید خودکار مستندات غافل نشوید؛ هر تغییر در KB یا پایپلاین باید در `SUMMARY_FA.md` و `SPEC.md` منعکس شود.
