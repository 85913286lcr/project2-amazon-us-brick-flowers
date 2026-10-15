# Great Expectations business gate (2023)

GX 1.23.2 · 2026-10-15T02:18:17+00:00 · 15 expectations · **PASS**

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
