# گزارش خانواده‌های الگو (Top Pattern Families) – نسخه v1.0.0
تاریخ: 2025-12-05T20:41:12.459307
ماژول: Codex Report Engine
منبع: الگوهای سطح ۱ و خانواده‌ها (Parquet/YAML)

## خلاصهٔ اجرایی

- ۴ ساعته: strong=1, medium=1, weak=23
- ۵ دقیقه: strong=0, medium=0, weak=28
- تعداد خانواده‌های انتخاب‌شده برای بررسی: ۴h=20, ۵m=20

## روش امتیازدهی

- فرمول امتیاز: family_score = 0.5*max(lift-1,0) + 0.3*log(support+1) + 0.2*max(stability,0) و برای خانواده‌های strong، امتیاز ۱۰٪ تقویت شده است.


## جدول خانواده‌های برتر ۴ ساعته

|family_id|window_sizes|pattern_types|support|lift|stability|strength|score|
|---|---|---|---|---|---|---|---|
|fam_4h_feature_rule_001|[5 4]|['feature_rule']|24502.0|0.9790944299106746|0.9696709493668738|weak|3.2258994412782185|
|fam_4h_sequence_004|[7 6]|['sequence']|10136.0|0.9895031535324358|0.9660937887202332|weak|2.9604029703587664|
|fam_4h_feature_rule_002|[10 11]|['feature_rule']|4859.0|1.014656379943713|0.9682629866709003|weak|2.747618902374398|
|fam_4h_sequence_007|[7 6]|['sequence']|4965.0|0.9968460548830271|0.957240179732308|weak|2.744559025766895|
|fam_4h_candle_shape_001|[2 3]|['candle_shape']|4265.0|1.012695549950193|0.9519939265958872|weak|2.704276130003662|
|fam_4h_feature_rule_005|[8 7]|['feature_rule']|3855.0|1.028879373432213|0.967079632764538|weak|2.685071309988145|
|fam_4h_feature_rule_000|[4 6]|['feature_rule']|2931.0|1.026063623717726|0.9610731930114884|weak|2.6002784693631233|
|fam_4h_sequence_005|[7 6]|['sequence']|2660.0|1.025009266976014|0.9543082617465869|weak|2.5693034671306316|
|fam_4h_feature_rule_004|[5 9]|['feature_rule']|2282.0|1.0275229302131739|0.9685074834271568|weak|2.5274366557509564|
|fam_4h_feature_rule_006|[10  2]|['feature_rule']|2134.0|1.0244922207240017|0.9572741384639357|weak|2.503567515753605|
|fam_4h_sequence_001|[7 6]|['sequence']|2195.0|0.949174914601503|0.9531864094980365|weak|2.4989551226884337|
|fam_4h_feature_rule_003|[8 7]|['feature_rule']|1945.0|1.0412484410912717|0.9671157590385747|weak|2.4861067511771355|
|fam_4h_sequence_003|[7 6]|['sequence']|1774.0|1.0271461443338032|0.9435301591113692|weak|2.4467458145620307|
|fam_4h_sequence_006|[7 6]|['sequence']|1638.0|1.0315705681748428|0.9575407074100181|weak|2.4278458991925738|
|fam_4h_candle_shape_003|[3 4]|['candle_shape']|1529.0|0.9708052263237963|0.9250493099344171|weak|2.384916766302828|
|fam_4h_candle_shape_004|[3 2]|['candle_shape']|1513.0|0.9914115922735149|0.9384042772772211|weak|2.3844339856546624|
|fam_4h_feature_rule_007|[9 5]|['feature_rule']|1282.0|1.0279094810808886|0.972544059051166|weak|2.355550461735368|
|fam_4h_sequence_009|[7 6]|['sequence']|1172.0|1.037465745567921|0.9559216474570418|weak|2.3301131568714113|
|fam_4h_sequence_002|[7 6]|['sequence']|1250.0|0.9870584347368926|0.9326140696441032|weak|2.326032367068894|
|fam_4h_sequence_008|[7 6]|['sequence']|722.0|0.9989543163316837|0.9491083503315338|weak|2.164844436713936|

## جدول خانواده‌های برتر ۵ دقیقه

|family_id|window_sizes|pattern_types|support|lift|stability|strength|score|
|---|---|---|---|---|---|---|---|
|fam_5m_feature_rule_007|[2 4]|['feature_rule']|1266644.0|1.000882152375947|0.9981470402008517|weak|4.4156351534138585|
|fam_5m_sequence_009|[11 10]|['sequence']|706213.0|1.0009307853182992|0.9888685488705119|weak|4.238541178440933|
|fam_5m_sequence_000|[11 10]|['sequence']|371411.0|0.9992652929866722|0.9814515062744535|weak|4.0438104725218365|
|fam_5m_candle_shape_007|[5 6]|['candle_shape']|300938.0|1.0009210814088993|0.9679091189766295|weak|3.978441224115526|
|fam_5m_sequence_004|[10  9]|['sequence']|294898.0|0.9983238958208682|0.9805073051899573|weak|3.9744179221832785|
|fam_5m_feature_rule_006|[9 3]|['feature_rule']|242444.0|0.9993121816372372|0.995758826395158|weak|3.918710813132637|
|fam_5m_candle_shape_002|[6 5]|['candle_shape']|242251.0|0.9955247606693907|0.975675433798586|weak|3.9144552224555826|
|fam_5m_feature_rule_005|[11 10]|['feature_rule']|222255.0|0.9978424309273616|0.9958208054061191|weak|3.8926397059723747|
|fam_5m_sequence_008|[11  9]|['sequence']|182880.0|0.9992688892918153|0.9783296663649423|weak|3.8306432173970424|
|fam_5m_feature_rule_002|[6 7]|['feature_rule']|173914.0|0.9962584311138081|0.9951652332566082|weak|3.8189296325788415|
|fam_5m_feature_rule_001|[4 8]|['feature_rule']|173250.0|0.9985865753439767|0.9952138497343137|weak|3.817791776659242|
|fam_5m_sequence_002|[11  9]|['sequence']|160047.0|1.004600313097579|0.9771912103244311|weak|3.792707113381164|
|fam_5m_sequence_007|[11 10]|['sequence']|146667.0|0.9951616602077046|0.9733489934823929|weak|3.763447841124709|
|fam_5m_sequence_003|[11 10]|['sequence']|106194.0|0.9986619051192823|0.9751907710118987|weak|3.6669478459130835|
|fam_5m_candle_shape_003|[6 5]|['candle_shape']|100152.0|0.9988010556848328|0.9453817383864204|weak|3.6434126363910995|
|fam_5m_sequence_005|[11 10]|['sequence']|86056.0|1.0001944238087623|0.9700489786587362|weak|3.6029365515514993|
|fam_5m_candle_shape_000|[6 5]|['candle_shape']|67489.0|1.0052275441081298|0.9442461850053427|weak|3.527383424376369|
|fam_5m_candle_shape_001|[6 5]|['candle_shape']|65825.0|1.0068187639312893|0.9420219268539657|weak|3.5202448201501015|
|fam_5m_candle_shape_008|[5 6]|['candle_shape']|46183.0|1.0026980142701236|0.940746001999626|weak|3.4116148165572175|
|fam_5m_candle_shape_006|[6 5]|['candle_shape']|37937.0|0.9998856036827872|0.9278526907522855|weak|3.3486830963364573|

## توضیحات کیفی کوتاه

- خانواده fam_4h_feature_rule_001 با نوع الگو feature_rule و طول‌های پنجره 5,4، قدرت (lift) حدود 0.98 و پشتیبانی 24502 دارد.
- خانواده fam_4h_sequence_004 با نوع الگو sequence و طول‌های پنجره 7,6، قدرت (lift) حدود 0.99 و پشتیبانی 10136 دارد.
- خانواده fam_4h_feature_rule_002 با نوع الگو feature_rule و طول‌های پنجره 10,11، قدرت (lift) حدود 1.01 و پشتیبانی 4859 دارد.
- خانواده fam_5m_feature_rule_007 با نوع الگو feature_rule و طول‌های پنجره 2,4، قدرت (lift) حدود 1.00 و پشتیبانی 1266644 دارد.
- خانواده fam_5m_sequence_009 با نوع الگو sequence و طول‌های پنجره 11,10، قدرت (lift) حدود 1.00 و پشتیبانی 706213 دارد.
- خانواده fam_5m_sequence_000 با نوع الگو sequence و طول‌های پنجره 11,10، قدرت (lift) حدود 1.00 و پشتیبانی 371411 دارد.


---


# Pattern Families Report – v1.0.0 (EN)
Date: 2025-12-05T20:41:12.459307
Module: Codex Report Engine
Source: Level-1 patterns & families (Parquet/YAML)

## Executive Summary

- 4h: strong=1, medium=1, weak=23
- 5m: strong=0, medium=0, weak=28
- Selected families for review: 4h=20, 5m=20

## Scoring Method

- Score formula: family_score = 0.5*max(lift-1,0) + 0.3*log(support+1) + 0.2*max(stability,0); strong families get a 10% boost.


## Top 4h Families

|family_id|window_sizes|pattern_types|support|lift|stability|strength|score|
|---|---|---|---|---|---|---|---|
|fam_4h_feature_rule_001|[5 4]|['feature_rule']|24502.0|0.9790944299106746|0.9696709493668738|weak|3.2258994412782185|
|fam_4h_sequence_004|[7 6]|['sequence']|10136.0|0.9895031535324358|0.9660937887202332|weak|2.9604029703587664|
|fam_4h_feature_rule_002|[10 11]|['feature_rule']|4859.0|1.014656379943713|0.9682629866709003|weak|2.747618902374398|
|fam_4h_sequence_007|[7 6]|['sequence']|4965.0|0.9968460548830271|0.957240179732308|weak|2.744559025766895|
|fam_4h_candle_shape_001|[2 3]|['candle_shape']|4265.0|1.012695549950193|0.9519939265958872|weak|2.704276130003662|
|fam_4h_feature_rule_005|[8 7]|['feature_rule']|3855.0|1.028879373432213|0.967079632764538|weak|2.685071309988145|
|fam_4h_feature_rule_000|[4 6]|['feature_rule']|2931.0|1.026063623717726|0.9610731930114884|weak|2.6002784693631233|
|fam_4h_sequence_005|[7 6]|['sequence']|2660.0|1.025009266976014|0.9543082617465869|weak|2.5693034671306316|
|fam_4h_feature_rule_004|[5 9]|['feature_rule']|2282.0|1.0275229302131739|0.9685074834271568|weak|2.5274366557509564|
|fam_4h_feature_rule_006|[10  2]|['feature_rule']|2134.0|1.0244922207240017|0.9572741384639357|weak|2.503567515753605|
|fam_4h_sequence_001|[7 6]|['sequence']|2195.0|0.949174914601503|0.9531864094980365|weak|2.4989551226884337|
|fam_4h_feature_rule_003|[8 7]|['feature_rule']|1945.0|1.0412484410912717|0.9671157590385747|weak|2.4861067511771355|
|fam_4h_sequence_003|[7 6]|['sequence']|1774.0|1.0271461443338032|0.9435301591113692|weak|2.4467458145620307|
|fam_4h_sequence_006|[7 6]|['sequence']|1638.0|1.0315705681748428|0.9575407074100181|weak|2.4278458991925738|
|fam_4h_candle_shape_003|[3 4]|['candle_shape']|1529.0|0.9708052263237963|0.9250493099344171|weak|2.384916766302828|
|fam_4h_candle_shape_004|[3 2]|['candle_shape']|1513.0|0.9914115922735149|0.9384042772772211|weak|2.3844339856546624|
|fam_4h_feature_rule_007|[9 5]|['feature_rule']|1282.0|1.0279094810808886|0.972544059051166|weak|2.355550461735368|
|fam_4h_sequence_009|[7 6]|['sequence']|1172.0|1.037465745567921|0.9559216474570418|weak|2.3301131568714113|
|fam_4h_sequence_002|[7 6]|['sequence']|1250.0|0.9870584347368926|0.9326140696441032|weak|2.326032367068894|
|fam_4h_sequence_008|[7 6]|['sequence']|722.0|0.9989543163316837|0.9491083503315338|weak|2.164844436713936|

## Top 5m Families

|family_id|window_sizes|pattern_types|support|lift|stability|strength|score|
|---|---|---|---|---|---|---|---|
|fam_5m_feature_rule_007|[2 4]|['feature_rule']|1266644.0|1.000882152375947|0.9981470402008517|weak|4.4156351534138585|
|fam_5m_sequence_009|[11 10]|['sequence']|706213.0|1.0009307853182992|0.9888685488705119|weak|4.238541178440933|
|fam_5m_sequence_000|[11 10]|['sequence']|371411.0|0.9992652929866722|0.9814515062744535|weak|4.0438104725218365|
|fam_5m_candle_shape_007|[5 6]|['candle_shape']|300938.0|1.0009210814088993|0.9679091189766295|weak|3.978441224115526|
|fam_5m_sequence_004|[10  9]|['sequence']|294898.0|0.9983238958208682|0.9805073051899573|weak|3.9744179221832785|
|fam_5m_feature_rule_006|[9 3]|['feature_rule']|242444.0|0.9993121816372372|0.995758826395158|weak|3.918710813132637|
|fam_5m_candle_shape_002|[6 5]|['candle_shape']|242251.0|0.9955247606693907|0.975675433798586|weak|3.9144552224555826|
|fam_5m_feature_rule_005|[11 10]|['feature_rule']|222255.0|0.9978424309273616|0.9958208054061191|weak|3.8926397059723747|
|fam_5m_sequence_008|[11  9]|['sequence']|182880.0|0.9992688892918153|0.9783296663649423|weak|3.8306432173970424|
|fam_5m_feature_rule_002|[6 7]|['feature_rule']|173914.0|0.9962584311138081|0.9951652332566082|weak|3.8189296325788415|
|fam_5m_feature_rule_001|[4 8]|['feature_rule']|173250.0|0.9985865753439767|0.9952138497343137|weak|3.817791776659242|
|fam_5m_sequence_002|[11  9]|['sequence']|160047.0|1.004600313097579|0.9771912103244311|weak|3.792707113381164|
|fam_5m_sequence_007|[11 10]|['sequence']|146667.0|0.9951616602077046|0.9733489934823929|weak|3.763447841124709|
|fam_5m_sequence_003|[11 10]|['sequence']|106194.0|0.9986619051192823|0.9751907710118987|weak|3.6669478459130835|
|fam_5m_candle_shape_003|[6 5]|['candle_shape']|100152.0|0.9988010556848328|0.9453817383864204|weak|3.6434126363910995|
|fam_5m_sequence_005|[11 10]|['sequence']|86056.0|1.0001944238087623|0.9700489786587362|weak|3.6029365515514993|
|fam_5m_candle_shape_000|[6 5]|['candle_shape']|67489.0|1.0052275441081298|0.9442461850053427|weak|3.527383424376369|
|fam_5m_candle_shape_001|[6 5]|['candle_shape']|65825.0|1.0068187639312893|0.9420219268539657|weak|3.5202448201501015|
|fam_5m_candle_shape_008|[5 6]|['candle_shape']|46183.0|1.0026980142701236|0.940746001999626|weak|3.4116148165572175|
|fam_5m_candle_shape_006|[6 5]|['candle_shape']|37937.0|0.9998856036827872|0.9278526907522855|weak|3.3486830963364573|

## Qualitative Notes

- Family fam_4h_feature_rule_001 (feature_rule, windows 5,4) shows lift≈0.98 with support 24502.
- Family fam_4h_sequence_004 (sequence, windows 7,6) shows lift≈0.99 with support 10136.
- Family fam_4h_feature_rule_002 (feature_rule, windows 10,11) shows lift≈1.01 with support 4859.
- Family fam_5m_feature_rule_007 (feature_rule, windows 2,4) shows lift≈1.00 with support 1266644.
- Family fam_5m_sequence_009 (sequence, windows 11,10) shows lift≈1.00 with support 706213.
- Family fam_5m_sequence_000 (sequence, windows 11,10) shows lift≈1.00 with support 371411.

## Recommendations
- Promote strong families to Rulebook candidates; run targeted backtests.
- Revisit medium families with more regime-aware filters.
- Monitor weak families for drift; archive if stability declines further.
