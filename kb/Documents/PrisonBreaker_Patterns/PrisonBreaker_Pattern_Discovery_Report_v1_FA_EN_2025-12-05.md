-------------------------------------------------------------
🇮🇷 نسخه فارسی – FA Version
گزارش رسمی علمی کشف الگوها و روابط در پروژه PrisonBreaker
Version 1.0 — ۱۴۰۴/۰۹/۱۴ (2025-12-05)
-------------------------------------------------------------
عنوان

تحلیل علمی، چندلایه و داده‌محور برای کشف الگوهای معنادار در تایم‌فریم‌های ۵ دقیقه و ۴ ساعت BTCUSDT
(برای توسعه قواعد معاملاتی با ارزش پیش‌بینی بالا)

۱. مقدمه

این سند چارچوب علمی پروژه PrisonBreaker را تعریف می‌کند:
معماری چندلایه تحلیل، روش‌های کشف الگو، ساختار روابط قوی/متوسط/ضعیف و چرخه یادگیری پویا.

هدف، استخراج قواعد معاملاتی پایدار، قطعی و تکرارپذیر از رفتار واقعی کندل‌ها است.

۲. معماری سه‌لایه تحلیل
لایه ۱ — کشف الگو در ۵ دقیقه (L1 – Micro Patterns)

این لایه منبع اصلی حقیقت است.
الگوهای ۵m رفتار خام، طبیعی و بدون فیلتر قیمت را نمایش می‌دهند.

خروجی L1 شامل:

الگوهای ترتیبی جهت

الگوهای آماری (mean, std, skew, tails)

الگوهای مبتنی بر نوسان

روابط شرطی کوتاه‌مدت

لایه ۲ — نگاشت ۵m → ۴h (L2 – Mapped Patterns)

در L2 هر کندل ۴ ساعته به ۴۸ کندل ۵ دقیقه تبدیل می‌شود.
ویژگی‌های این ۴۸ کندل فشرده‌سازی شده و رابطه آنها با جهت ۴ ساعته تحلیل می‌شود.

اینجا مهم‌ترین اصل گزارش ثبت شده است:

الگوهای ۴ ساعته فقط باید بر اساس دانش L1 استخراج شوند، نه پردازش مستقیم OHLC خام.

لایه ۳ — روابط رژیمی و استنتاجی (L3 – Regime Logic)

این لایه شرایط تقویت یا تضعیف الگوها را بررسی می‌کند:

رژیم‌های بازار

زنجیره‌های شرطی

اثرات غیرمستقیم

وابستگی‌های چندمرحله‌ای

۳. تکنیک‌های پردازش داده
۳.۱ پاک‌سازی و تنظیم

حذف کندل بسته‌نشده

هم‌ترازسازی زمان‌ها

ترکیب CoinEx + Binance برای تاریخچه کامل

استخراج ویژگی‌های مشتق‌شده

۳.۲ فشرده‌سازی ابعادی

PCA

AutoEncoder

Aggregated Block Stats

۴. تکنیک‌های علمی کشف الگو
۴.۱ استخراج ترتیبی (Sequence Mining)

Apriori-like

Markov transitions

Directional chain probabilities

۴.۲ تحلیل بیزین (Bayesian Dependencies)

Posterior lift

Bayesian surprise

Conditional likelihood

۴.۳ الگوهای مشابهت (Feature Similarity)

KNN feature neighborhoods

Cosine similarity

DTW shape-matching

۴.۴ روابط غیرمستقیم

Cross-pattern spillover

Cascading effects

Multi-level conditionality

۵. دسته‌بندی روابط: قوی / متوسط / ضعیف
روابط قوی (Strong)

Lift ≥ 1.35

Support ≥ 30

Stability ≥ 0.25

Cross-TF agreement

روابط متوسط (Medium)

قابل‌قبول، اما نیازمند تحلیل موج دوم.

روابط ضعیف (Weak)

غیرپایدار، وارد چرخه بازکشف می‌شوند.

۶. چرخه یادگیری پویا (Dynamic Discovery Loop)
Wave 1:
    Extract → Classify → Strong/Medium/Weak

Wave 2:
    Re-mine Medium + Weak
    Re-evaluate
    Promote or Discard

Wave 3:
    Cross-timeframe alignment
    Regime-aware conditionalization

Repeat until:
    No new strong patterns appear.

۷. اصلاح مهم نسخه جدید

در نسخه‌های قدیمی پروژه یک خطا وجود داشت:

❌ فیلتر کردن روابط ۴ ساعته بدون کشف روابط ۵ دقیقه
✔️ اکنون اصلاح شد:
تمام روابط ۴ ساعته باید از نگاشت و تحلیل L1 به‌وجود بیایند.

۸. ادغام با KB پروژه (Integration)

فایل باید در GitHub در مسیر زیر ارجاع شود:

project/DOCUMENTS/PrisonBreaker_Patterns/PrisonBreaker_Pattern_Discovery_Report_v1_FA_EN_2025-12-05.md


و مراجع آن در MASTER_KNOWLEDGE.yaml ثبت شوند.

۹. جمع‌بندی

این سند پایهٔ علمی PrisonBreaker است و تمامی پایپلاین‌ها، الگوریتم‌ها، مدل‌ها و Codex Agents باید مطابق آن عمل کنند.

-------------------------------------------------------------
🇬🇧 English Version — EN
PrisonBreaker Pattern Discovery Report (Scientific Edition)
Version 1.0 — 2025-12-05
-------------------------------------------------------------
Title

Scientific multi-layer framework for discovering meaningful candle patterns in BTCUSDT (5m & 4h)

1. Introduction

This report establishes the scientific backbone of PrisonBreaker:
pattern discovery, multi-layer architecture, dynamic learning loops, and rule extraction.

2. Three-Layer Analysis Architecture
Layer 1 – Micro Patterns (5m)

Primary truth source; extracts raw behavior of price.

Layer 2 – 5m→4h Mapping

4h logic must come from L1-derived knowledge, not direct OHLC filters.

Layer 3 – Regime Logic

Defines:

conditional dependencies

cascading effects

pattern reinforcement

3. Data Processing Techniques

timestamp normalization

coinex+binance merged history

feature engineering

dimensionality reduction (PCA, AE)

4. Pattern Discovery Methods
4.1 Sequence Mining

Markov chains, directional frequencies, apriori-like mining.

4.2 Bayesian Patterns

Posterior lift, probabilistic dependency.

4.3 Feature Similarity Patterns

Cosine, KNN, DTW.

4.4 Indirect Patterns

Cross-pattern interactions.

5. Pattern Strength Classification
Strength	Conditions
Strong	lift≥1.35, support≥30, stability≥0.25
Medium	requires deeper mining
Weak	recycled into loop
6. Dynamic Discovery Loop
Wave1 → extract + classify
Wave2 → refine medium/weak
Wave3 → regime-aware cross-TF validation
Repeat.

7. Key Correction

4h patterns must come exclusively from L1 (5m-derived) knowledge.

8. KB Integration

This document must be stored and referenced in repo structure.

9. Conclusion

This establishes the scientific standard used in the entire PrisonBreaker system.

پایان فایل سند