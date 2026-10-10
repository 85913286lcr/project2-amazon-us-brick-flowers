# Frozen conclusion contract (flower-v1.0, English edition)

I built my store on these tables before the pipeline was finished, so the pipeline has to reproduce them.
If a number differs, I fix the pipeline, not the conclusion.

| File | Content | Reproduced by |
|---|---|---|
| `golden/g01_flower_products_labels.csv` | 3,650 flower toys with relevance tier, play pattern, brand | `dim_flower_product` |
| `golden/g02_pattern_overview_2023.csv` | 22 play patterns: demand, growth vs the toy market, satisfaction, quadrant | `mart_flower_pattern_trend` |
| `golden/g03_need_evidence_2023.csv` | unmet needs by play pattern with evidence tier | `mart_flower_need_evidence` |
| `golden/g04_theme_evidence_2023.csv` | buying motives and experience themes by play pattern | `mart_flower_theme_evidence` |
| `golden/g05_diy_2023.csv` | DIY families, 2022 vs 2023 | `mart_flower_diy_2023` |
| `golden/g06_keepa2026_group_verdicts.csv` | Amazon 2026: three trend signals and a verdict for each of 7 product groups | `mart_keepa_group_verdict` |
| `golden/g07_keepa2026_products.csv` | the 724 product families behind the 2026 numbers | `fact_keepa_snapshot` |
| `golden/g08_diy_2026.csv` | DIY against non-DIY groups in 2026 | `mart_keepa_diy_2026` |
| `golden/g09`, `g10` | products launched since 2024 and the product forms they fall into | `fact_keepa_snapshot`, `mart_keepa_new_forms` |

`manifest.json` lists the row count, the join keys and a SHA-256 fingerprint of every file.

Check: `python scripts/export_marts_for_contract.py` then `python scripts/verify_against_contract.py docs/evidence/contract/export`.
The result must be `RESULT PASS`. Numbers are compared within 6e-4 because the golden tables are stored to three decimals.

The tables come from my earlier exploratory analysis. For this repository I translated the labels to English and
left every number as it was. The 2026 tables are tied to the Keepa snapshot of 7 October 2026, so the pipeline reads
that snapshot from a local cache and does not call the API again.
