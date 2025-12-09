# راهنمای توسعه PrisonBreaker / Pattern Lab (FA/EN)

این پروژه برای ساخت نسخه‌ی Enterprise از سیستم «PrisonBreaker / Pattern Lab» است؛ هدف یک MVP نیست، بلکه محصول پایدار، قابل نگه‌داری و توسعه‌پذیر است. هر تغییر باید در چارچوب معماری تعریف‌شده انجام شود و مسیر آینده (تایم‌فریم‌ها، سیمبل‌های جدید، داده‌های real-time) را باز نگه دارد.

## معماری و لایه‌ها
- Backend: FastAPI (لایه‌های api / services / core / infra) با ساختار ماژولار. لایه api صرفا ورودی/خروجی را هندل می‌کند و منطق در services/core قرار می‌گیرد. داده‌ها از infra/config و infra/logging تنظیم می‌شوند.
- Frontend: React + Vite + TypeScript + Tailwind + Zustand. تم روشن پیش‌فرض، آماده‌سازی برای تم‌های آتی. ساختار صفحات شامل Pattern Lab (اصلی)، Dashboard، Reports/Analytics، Settings.
- Data/KB: پارکت‌ها در `data/` و دانش در `project/KNOWLEDGE_BASE/patterns/patterns.yaml` و `project/MASTER_KNOWLEDGE.yaml`. لایه دسترسی داده باید قابل جایگزینی با منبع API باشد.

## اصول توسعه
- هدف: نسخه‌ی کمال‌یافته و پایدار، نه دمو. تغییرات باید backward-compatible با APIهای موجود باشند مگر صراحتاً توافق شود.
- Logging و Observability: از `infra/logging.py` و middleware ثبت درخواست‌ها استفاده کنید؛ endpoint `/metrics` برای مانیتورینگ آماده است.
- Error Handling: خطاها باید در لایه api با HTTPException مناسب مدیریت شوند؛ در services/core استثناهای شفاف raise شوند.
- تست: pytest با `pythonpath=src` و `testpaths=tests`. برای هسته (candidate search، KB I/O) تست واحد اضافه کنید.
- Frontend: از Zustand برای state، API base URL از `VITE_API_BASE_URL`. مدیریت خطا/بارگذاری در hooks رعایت شود.

## English Summary
- Build an enterprise-grade, modular stack: FastAPI (api/services/core/infra), React + Vite + TS + Tailwind + Zustand.
- Data sources live in `data/` (parquet) and KB YAML under `project/KNOWLEDGE_BASE`. Keep a clean abstraction for swapping sources later.
- Logging/observability are first-class (`infra/logging.py`, `/metrics`). Errors surface via HTTPException at the edge.
- Preserve existing APIs while evolving; add unit tests for core logic and KB I/O. UI defaults to light theme, ready for future themes.
