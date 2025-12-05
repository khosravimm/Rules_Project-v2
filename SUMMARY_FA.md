## خلاصهٔ فنی و جریان کار (پروژه PrisonBreaker / BTC Futures)

### هدف و دامنه
- ساخت بانک دانش YAML چندبازاره برای کشف/مدیریت الگوها و قوانین ترید در BTCUSDT (4h/5m) با امکان گسترش.
- منبع حقیقت: فایل‌های YAML در `kb/` (مطابق `kb/KB_SCHEMA.yaml`)، نه متن چت.

### فایل‌های مرجع
- راهبرد/مفهوم: `project/MASTER_KNOWLEDGE.yaml` (نسخه 0.1.1)
- Schema: `kb/KB_SCHEMA.yaml` (نسخه 0.1.0)
- نمونه دانش: `kb/btcusdt_4h_knowledge.yaml`
- خلاصه انگلیسی: `SPEC.md`

### لودر داده‌ها
- لودر رسمی دریافت داده‌های OHLCV (برای BTCUSDT و سایر بازارها) تابع `load_ohlcv` در فایل `src/data/ohlcv_loader.py` است.
- فایل قدیمی `src/data/btc_futures_loader.py` از مسیر `src/data` حذف شده و دیگر نباید در هیچ کدی استفاده شود.

### ساختار بانک دانش (طبق KB_SCHEMA)
- بخش‌ها: meta, datasets, features, clusters, patterns, trading_rules, rule_relations, cross_market_patterns, market_relations, backtests, performance_over_time, status_history.
- قیود: ID یکتا در هر بخش؛ ارجاع‌ها (`dataset_used`, `pattern_refs`, `rule_id`, …) باید معتبر باشد؛ ترجیح تک‌فایل `kb/*_knowledge.yaml`، اگر چندفایلی شد باید همچنان با Schema و ارجاعات معتبر بماند؛ مقدارهای مجاز: نوع الگو {forward, backward, meta}، وضعیت {exploratory, candidate, active, watchlist, deprecated}، جهت {long, short, filter_only}، نوع رابطه {conflict, confirm, complement}.

### سیاست فایل و الزام‌ها (MASTER_KNOWLEDGE)
- `knowledge_base.file_strategy.single_file_initial = true` با مسیر `kb/btcusdt_4h_knowledge.yaml`.
- `enforcement`: تک‌فایل پیش‌فرض، یکتایی ID، ولیدیشن ارجاع‌ها.  
- ولیدیشن ابزار `rules_kb` باید قبل از مصرف پاس شود؛ در صورت شکستن به چند فایل، انطباق با Schema و ارجاعات الزامی است.

### مدل‌ها و کد (src/rules_kb/)
- `models.py` (Pydantic v2): موجودیت‌های Schema + متادیتا (`KnowledgeBase`, `MasterKnowledge`)، اعتبارسنجی یکتایی/ارجاع‌ها.
- `loader.py`: `load_yaml`, `load_knowledge`, `load_master_knowledge` (خطا با `KnowledgeValidationError`).
- `query.py`: `get_patterns_by_market_timeframe`, `filter_patterns`, `list_markets`, `list_timeframes`.
- `cli.py` (entrypoint: `rules-kb`): `validate`, `list-markets`, `list-timeframes`, `list-patterns` با فیلترهای conf/tag/regime/direction/window/status.

### تست و وابستگی‌ها
- Pytest در `tests/`: لود موفق master/knowledge، خطای ارجاع دیتاست نامعتبر، فیلتر پرس‌وجو.  
- `pyproject.toml`: `pydantic>=2.7`, `pyyaml>=6.0`, dev=`pytest>=7.4`; اسکریپت `rules-kb`.

### راهنمای توسعه/گسترش
- افزودن بازار/تایم جدید: یک `*_knowledge.yaml` مطابق Schema؛ ارجاع‌ها resolve شود.
- جدا کردن فایل‌ها (مثلاً patterns/trading_rules): هر بخش باید Schema را پاس کند و ارجاع‌های بین فایل‌ها معتبر بماند.
- افزودن متادیتا: فیلد اختیاری + مستندسازی در Schema/مدل؛ سازگاری عقب‌رو حفظ شود.
- آینده: سخت‌گیری روی enumهای جهت/وضعیت/نوع؛ هم‌راستایی واژگان چرخه عمر با MASTER.

### ریسک‌ها و موارد باز
- Enumهای جهت/وضعیت/نوع هنوز آزادند؛ قبل از استفاده سخت باید نهایی شوند.
- Cross-Market/Market_Relations در دادهٔ نمونه خالی است؛ نیاز به داده و ولیدیشن واقعی.
- واژگان وضعیت (exploratory/candidate/active/watchlist/deprecated) باید در صورت مصرف برنامه‌ای، هم‌راستا بماند.

### الزامات کشف الگوهای کندلی (جزئیات کلیدی)
- دادهٔ پایه: دوساله 4h (~4380 کندل) و دوساله 5m (~210,240 کندل)؛ کندل ناقص حذف، تایم‌زون همگن.
- دنباله‌ها: بررسی طول‌های 2..11 در هر دو تایم‌فریم. الگوهای forward برای پیش‌بینی کندل بعدی؛ الگوهای backward/meta برای تأیید/رد و حذف پیش‌بینی‌های غلط.
- میکرو/ماکرو: تحلیل 5m مستقل (رفتار موضعی) و مشروط به والد 4h (نگاشت micro→macro و بهبود پیش‌بینی 4h).
- متدها: pattern mining (PrefixSpan/…)، مدل‌های Markov/TCN/LSTM/GBM، خوشه‌بندی (kmeans/GMM/…) روی فیچرها، آزمون‌های آماری و کنترل چندآزمونی (White’s RC/SPA, permutation/surrogate). تحقیق ادبیات و انتخاب روش به‌روز پیش‌نیاز است.
- ثبت الگوها: در بخش `patterns` با شرایط {feature, operator, value}، هدف (target)، dataset_used، وضعیت و تگ‌ها؛ امکان درج جهت/اعتماد/رژیم به‌صورت اختیاری.
- قوانین معاملاتی: در `trading_rules` با ارجاع به الگوها + شروط اضافی، خروج و ریسک؛ خوشه‌ها قابل استفاده به‌عنوان شرط.
- روابط بین الگو/قانون: در `rule_relations` (conflict/confirm/complement) برای کنترل خطا و ترکیب نتایج.
- طبقه‌بندی قدرت (دقت): خیلی قوی ≥80٪، قوی 60–80٪، متوسط 55–60٪، ضعیف 52–55٪، خیلی ضعیف <52٪. تمرکز ویژه بر بازکشف و بهبود الگوهای متوسط/ضعیف با متدهای دقیق‌تر.
- پایش و چرخه حیات: performance_over_time، status_history، وضعیت‌ها (exploratory/candidate/active/watchlist/deprecated) مطابق MASTER؛ drift و به‌روزرسانی دوره‌ای در پایپلاین‌ها.
- روابط Lead-Lag: در بخش `market_relations` باید مشخص شود کدام مارکت جلوتر است (best_lag_other_leads_base، corr_at_best_lag، granger_p_value). این برای پیش‌بینی و حتی معامله روی ابزارهای همسو/پیشرو حیاتی است.
- ادغام فازها: فاز کشف هسته و Cross-Market می‌تواند در یک اجرای ترکیبی پیش برود (صرفه‌جویی زمان) به‌شرط رعایت ولیدیشن و داده‌های کافی؛ پایپلاین جدید `continuous_rebacktest_and_refresh` این را پوشش می‌دهد.
- ابزار: استفاده از VS Code + Codex اختیاری است؛ الزامی نیست. مهم خروجی منطبق با Schema و ولیدیشن است؛ می‌توان از هر ویرایشگر/ابزار دلخواه استفاده کرد.
