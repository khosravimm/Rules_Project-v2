# گزارش کامل موجودی الگوها – نسخه v2
- تاریخ: 2025-12-05T22:35:56.909253
- ورودی‌ها: data/patterns_4h_raw_level1.parquet, data/patterns_5m_raw_level1.parquet

## الگوهای تایم‌فریم ۴ ساعته (4h)
- تعداد کل الگوها: 516
- بازه‌های زمانی (window_size): [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

الگوها به تفکیک window_size:
|count|count|
|---|---|
|count     2
count    41
Name: 0, dtype: int64|count     2
count    41
Name: 0, dtype: int64|
|count     3
count    81
Name: 1, dtype: int64|count     3
count    81
Name: 1, dtype: int64|
|count     4
count    52
Name: 2, dtype: int64|count     4
count    52
Name: 2, dtype: int64|
|count     5
count    48
Name: 3, dtype: int64|count     5
count    48
Name: 3, dtype: int64|
|count     6
count    80
Name: 4, dtype: int64|count     6
count    80
Name: 4, dtype: int64|
|count      7
count    129
Name: 5, dtype: int64|count      7
count    129
Name: 5, dtype: int64|
|count     8
count    33
Name: 6, dtype: int64|count     8
count    33
Name: 6, dtype: int64|
|count     9
count    17
Name: 7, dtype: int64|count     9
count    17
Name: 7, dtype: int64|
|count    10
count    17
Name: 8, dtype: int64|count    10
count    17
Name: 8, dtype: int64|
|count    11
count    18
Name: 9, dtype: int64|count    11
count    18
Name: 9, dtype: int64|

توزیع نوع الگو (کل):
|count|count|
|---|---|
|count    sequence
count         252
Name: 0, dtype: object|count    sequence
count         252
Name: 0, dtype: object|
|count    feature_rule
count             158
Name: 1, dtype: object|count    feature_rule
count             158
Name: 1, dtype: object|
|count    candle_shape
count             106
Name: 2, dtype: object|count    candle_shape
count             106
Name: 2, dtype: object|

توزیع نوع الگو بر حسب window_size:
|window_size|candle_shape|feature_rule|sequence|
|---|---|---|---|
|2|25|12|4|
|3|61|12|8|
|4|20|16|16|
|5|0|16|32|
|6|0|16|64|
|7|0|17|112|
|8|0|17|16|
|9|0|17|0|
|10|0|17|0|
|11|0|18|0|

خلاصه lift و stability بر حسب window_size:
|window_size|mean_lift|median_lift|mean_stability|median_stability|
|---|---|---|---|---|
|2.0|0.9860362194102145|0.9752673796791445|0.9561859574229656|0.96198350638782|
|3.0|1.0083671549380082|1.005514705882353|0.9264821814861727|0.9291802845334335|
|4.0|1.0109965235543241|1.0044238614659668|0.9426852654384263|0.9556903863475807|
|5.0|1.0107916553322454|0.9983279888879797|0.9636058608691761|0.9688887130650503|
|6.0|1.0110019009605407|1.0129983196999253|0.9536762641831811|0.9533757026679947|
|7.0|0.9994253024470544|0.9923303897091038|0.9001054821137732|0.8979267443376394|
|8.0|0.9714296647877414|0.9886857775931313|0.9390109883794313|0.9244930257856477|
|9.0|1.0160951837311758|1.0155561740913046|0.962563309277387|0.967340136762891|
|10.0|1.0195991392139754|1.0067483046941867|0.960497270525496|0.9736920037309276|
|11.0|0.9984354965665787|1.0155922038980512|0.960941635378211|0.9677480178851431|

۱۰ الگوی برتر بر اساس امتیاز (از میان ۲۰۰ برتر):
|window_size|pattern_type|support|lift|stability|score|short_definition|
|---|---|---|---|---|---|---|
|2|feature_rule|1428|0.9848288245779595|0.978552671104883|2.375129587599937|TREND_FLAT|VOL_NORMAL|RANGE_WIDE|
|2|feature_rule|1265|1.0084187609646806|0.9854443312840616|2.344383527550389|TREND_FLAT|VOL_NORMAL|RANGE_TIGHT|
|2|sequence|1164|1.0489989341566055|0.9743347164939551|2.3375093201770336|UP|DOWN|
|2|sequence|1163|0.9509485886123387|0.9727001856031073|2.3124253256080363|DOWN|UP|
|2|sequence|970|1.0818429902420201|0.9675582801312077|2.2979310916346494|DOWN|DOWN|
|2|sequence|1080|0.9265040106951872|0.9682203661079064|2.2893366185133437|UP|UP|
|3|feature_rule|975|0.9940454316924906|0.9684600986942068|2.258730795662769|TREND_FLAT|VOL_NORMAL|RANGE_WIDE|
|3|feature_rule|948|0.968873395157833|0.9637953537938175|2.249381710341742|TREND_FLAT|VOL_NORMAL|RANGE_TIGHT|
|4|feature_rule|757|0.9945811157094638|0.9643102180866877|2.182067059310049|TREND_FLAT|VOL_NORMAL|RANGE_WIDE|
|4|feature_rule|752|0.9622875186158355|0.9630532982555918|2.1798302279910864|TREND_FLAT|VOL_NORMAL|RANGE_TIGHT|

### خلاصه خانواده‌ها
- تعداد خانواده‌ها: 25
توزیع قدرت خانواده‌ها:
|count|count|
|---|---|
|count    weak
count      23
Name: 0, dtype: object|count    weak
count      23
Name: 0, dtype: object|
|count    strong
count         1
Name: 1, dtype: object|count    strong
count         1
Name: 1, dtype: object|
|count    medium
count         1
Name: 2, dtype: object|count    medium
count         1
Name: 2, dtype: object|

## الگوهای تایم‌فریم ۵ دقیقه‌ای (5m)
- تعداد کل الگوها: 10069
- بازه‌های زمانی (window_size): [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

الگوها به تفکیک window_size:
|count|count|
|---|---|
|count     2
count    45
Name: 0, dtype: int64|count     2
count    45
Name: 0, dtype: int64|
|count      3
count    159
Name: 1, dtype: int64|count      3
count    159
Name: 1, dtype: int64|
|count      4
count    684
Name: 2, dtype: int64|count      4
count    684
Name: 2, dtype: int64|
|count       5
count    2437
Name: 3, dtype: int64|count       5
count    2437
Name: 3, dtype: int64|
|count       6
count    2693
Name: 4, dtype: int64|count       6
count    2693
Name: 4, dtype: int64|
|count      7
count    147
Name: 5, dtype: int64|count      7
count    147
Name: 5, dtype: int64|
|count      8
count    272
Name: 6, dtype: int64|count      8
count    272
Name: 6, dtype: int64|
|count      9
count    528
Name: 7, dtype: int64|count      9
count    528
Name: 7, dtype: int64|
|count      10
count    1040
Name: 8, dtype: int64|count      10
count    1040
Name: 8, dtype: int64|
|count      11
count    2064
Name: 9, dtype: int64|count      11
count    2064
Name: 9, dtype: int64|

توزیع نوع الگو (کل):
|count|count|
|---|---|
|count    candle_shape
count            5772
Name: 0, dtype: object|count    candle_shape
count            5772
Name: 0, dtype: object|
|count    sequence
count        4141
Name: 1, dtype: object|count    sequence
count        4141
Name: 1, dtype: object|
|count    feature_rule
count             156
Name: 2, dtype: object|count    feature_rule
count             156
Name: 2, dtype: object|

توزیع نوع الگو بر حسب window_size:
|window_size|candle_shape|feature_rule|sequence|
|---|---|---|---|
|2|25|12|8|
|3|125|14|20|
|4|621|17|46|
|5|2385|17|35|
|6|2613|16|64|
|7|3|16|128|
|8|0|16|256|
|9|0|16|512|
|10|0|16|1024|
|11|0|16|2048|

خلاصه lift و stability بر حسب window_size:
|window_size|mean_lift|median_lift|mean_stability|median_stability|
|---|---|---|---|---|
|2.0|1.010601651444374|0.9999865737969057|0.9704722549461133|0.9897107061170948|
|3.0|0.9979045069618719|0.9969467488348298|0.9815264701471915|0.9872971931439662|
|4.0|0.9984428095937437|0.999076779578745|0.9682293721065681|0.9730210607746413|
|5.0|0.9986733810216093|0.9990815297051377|0.9442636349514989|0.9481936032974266|
|6.0|1.001373947412862|0.9990767707916929|0.910732158329057|0.9142900871289034|
|7.0|0.9991798416803706|0.9996452029349769|0.9823824777747444|0.9864938350356764|
|8.0|1.0011338381035741|0.9991067132876568|0.9861355938728911|0.9868457486809175|
|9.0|1.0014398735501298|1.0014566404280354|0.975235562868955|0.9760656887091387|
|10.0|1.0007870470910105|0.9990672440869937|0.9655966025993662|0.9681252935964454|
|11.0|1.0004715034616882|0.999062485128254|0.9482764609511813|0.9480241198296601|

۱۰ الگوی برتر بر اساس امتیاز (از میان ۲۰۰ برتر):
|window_size|pattern_type|support|lift|stability|score|short_definition|
|---|---|---|---|---|---|---|
|2|feature_rule|167812|0.9999865737969057|0.9983463333212137|3.8088509296232558|TREND_FLAT|VOL_NORMAL|RANGE_TIGHT|
|3|feature_rule|145527|1.0007108904738422|0.997286481680934|3.7662498776557234|TREND_FLAT|VOL_NORMAL|RANGE_TIGHT|
|4|feature_rule|136309|1.0012641317616124|0.9977684544846764|3.7469918515472083|TREND_FLAT|VOL_NORMAL|RANGE_TIGHT|
|5|feature_rule|127655|1.0026868509024545|0.9976170382796609|3.7279951606342383|TREND_FLAT|VOL_NORMAL|RANGE_TIGHT|
|6|feature_rule|122661|1.0013769491742284|0.9984102190178459|3.7155268836749915|TREND_FLAT|VOL_NORMAL|RANGE_TIGHT|
|7|feature_rule|117889|1.0019405185296373|0.9987930240997985|3.7039810436706304|TREND_FLAT|VOL_NORMAL|RANGE_TIGHT|
|8|feature_rule|114983|1.0003635791140089|0.9987047214421602|3.695687214014757|TREND_FLAT|VOL_NORMAL|RANGE_TIGHT|
|9|feature_rule|111329|0.9994224505792484|0.9988676806032805|3.685849748937482|TREND_FLAT|VOL_NORMAL|RANGE_TIGHT|
|10|feature_rule|109342|0.9996436554279661|0.9989244600560564|3.6804583948384035|TREND_FLAT|VOL_NORMAL|RANGE_TIGHT|
|11|feature_rule|106690|1.000084548732851|0.9986947794967201|3.6730888557931443|TREND_FLAT|VOL_NORMAL|RANGE_TIGHT|

### خلاصه خانواده‌ها
- تعداد خانواده‌ها: 28
توزیع قدرت خانواده‌ها:
|count|count|
|---|---|
|count    weak
count      28
Name: 0, dtype: object|count    weak
count      28
Name: 0, dtype: object|