# Great Expectations business gate

GX 1.23.2 · 2026-10-10T07:25:13+00:00 · 24 expectations · **PASS**

| Table | Business rule | Result |
|---|---|---|
| mart_flower_pattern_trend | Every play pattern of the taxonomy has a row (22) | PASS |
| mart_flower_pattern_trend | Play pattern is unique | PASS |
| mart_flower_pattern_trend | Average rating is between 1 and 5 | PASS |
| mart_flower_pattern_trend | Low-rating share is between 0 and 100 % | PASS |
| mart_flower_pattern_trend | Growth relative to the toy market is positive | PASS |
| mart_flower_pattern_trend | Quadrant is one of the five defined labels | PASS |
| mart_flower_pattern_trend | Every product is counted in exactly one evidence level | PASS |
| mart_flower_theme_evidence | Mention share is between 0 and 100 % | PASS |
| mart_flower_theme_evidence | Share of low-rated reviews is between 0 and 100 % | PASS |
| mart_flower_theme_evidence | Rating when mentioned is between 1 and 5 | PASS |
| mart_flower_theme_evidence | Evidence tier is strong / medium / weak | PASS |
| mart_flower_theme_evidence | Mentions never exceed the reviews of the pattern | PASS |
| mart_flower_need_evidence | A need is backed by at least one wish sentence | PASS |
| mart_flower_need_evidence | Products never exceed wish sentences | PASS |
| mart_flower_need_evidence | Evidence tier is strong / medium / weak | PASS |
| mart_keepa_group_verdict | All seven product groups have a 2026 verdict | PASS |
| mart_keepa_group_verdict | Verdict is trending / stable / not trending | PASS |
| mart_keepa_group_verdict | A group is judged on 1 to 50 products | PASS |
| mart_keepa_group_verdict | Signals up is between 0 and 3 | PASS |
| mart_keepa_group_verdict | Median rating is between 1 and 5 | PASS |
| mart_keepa_group_verdict | Median price is positive | PASS |
| mart_keepa_new_forms | A product form has at least one product | PASS |
| mart_keepa_new_forms | Products selling 50+ never exceed products | PASS |
| mart_keepa_new_forms | Monthly units are not negative | PASS |
