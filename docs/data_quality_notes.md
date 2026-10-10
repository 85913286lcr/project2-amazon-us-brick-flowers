# Data quality notes

Things that went wrong while I built this, and problems in the source data that I decided to keep visible
instead of hiding.

## Failures I hit and fixed

| What failed | How I found it | Fix |
|---|---|---|
| Negative `helpful_vote` values (-1, -2, -3) | dbt test `helpful_vote >= 0` failed on the first run | Set to NULL in staging. Raw is unchanged. NULL means "unknown"; 0 would claim "no votes". |
| Star schema was built on a 100,000-row sample | Row counts in `project2_analytics` did not match the slides. `sources.yml` still pointed at an old sample dataset. | Pointed the sources at `project2_raw` and added two tests that compare warehouse rows with raw rows. |
| An earlier build had 174,037 fewer reviews than raw | Same row-count comparison | That build removed duplicate reviews without saying so. I now keep every row and flag duplicates. |
| Flower products were missing after the first classification | A spot check: 242 titles contain "flower garden" but only 63 were found | Products with an empty description produced a NULL when the text fields were concatenated. Wrapped each field in `coalesce`. Recall went from 21,944 to 37,441 candidates. |
| Meltano load failed on the second run | `Cannot replace a table with a different partitioning spec` | The BigQuery target cannot overwrite a partitioned table. Raw is now append-only and staging keeps the newest load. |
| Monthly counts differed between my laptop and BigQuery | Brick flowers: 2,002 reviews locally, 1,988 in BigQuery | Time zone. DuckDB used my local zone, BigQuery uses UTC. The zone is now a dbt variable. |
| The 2026 verdict for two groups changed between two runs on the same data | I compared the outputs of both runs | Two causes. The sort before de-duplication was not stable, so ties were broken differently each run; I added the ASIN as a second sort key. And the Keepa title search had pulled in garden solar lights and book-nook kits, which are not toys; I added an exclusion list for those. |
| Fresh Meltano install could not start the tap | `No module named pkg_resources` | New setuptools dropped it. Pinned `setuptools<82` for the tap. |

## Problems in the source that stay (reported as warnings on every build)

These are `tests/known_issue_*.sql`. They warn with the current count and turn into an error if the count
grows past a limit.

| Issue | Rows | Error above | What I do about it |
|---|---|---|---|
| Duplicate review rows (same customer, item, millisecond) | 174,053 (1.07 %) | 325,000 (2 %) | Kept and flagged with `is_duplicate_review` |
| Reviews without text | 25,394 | 160,000 | Counted as reviews; cannot get a theme |
| Metadata rating more than 1 star from the review average (30+ reviews) | about 5,260 products | 20,000 | Marts use the rating computed from reviews |
| Metadata rating count lower than the number of review rows | 3,458 products | 20,000 | Marts count reviews themselves |
| Products with no reviews | 207 | 10,000 | Kept by the left join, review count 0 |
| Flower products without a brand | 40 | 200 | Cannot count towards "appears across brands" |
| Products without a title | 37 | 1,000 | Cannot be classified |

Also worth knowing, not a test: 52 % of products have no price, and the dataset is incomplete after
March 2023 (reviews written shortly before collection are only partly captured).

## Do the duplicates change the answer?

No. `mart_flower_duplicate_sensitivity` computes growth both ways:

| Play pattern | Growth vs market, all rows | Duplicates removed |
|---|---|---|
| Brick flower bouquets & bonsai | 2.76 | 2.77 |
| Toddler flower-garden stacking sets | 1.01 | 1.01 |
| Craft bouquets & paper flowers | 0.89 | 0.86 |
| Planting & science kits | 0.60 | 0.60 |

The ranking of play patterns is the same and average ratings move by less than 0.01.

## What the labels can and cannot claim

The flower classifier is a set of rules, not a trained model. I read random samples to check it:
12 to 15 correct out of 15 for each main play pattern, about 75 % for the first "is this a flower toy" step.
Two unmet-need categories were too noisy (3 to 4 correct out of 10) and I do not use them as evidence.

The 2026 numbers have their own limits. Keepa's "monthly sold" is Amazon's rounded "bought in past month" badge
(50+, 100+, ...), so sums are lower bounds. Rating counts are shared by all variations of a product, which is why I
keep one row per product family. And a top-seller list favours recent winners, so I also follow the 2023 top
products into 2026 and read both views together.
