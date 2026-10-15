-- Grain: 1 row = DIY or not. Is "make it yourself" where the 2026 flower-toy market is?
select
    is_diy,
    sum(reviews_added_2025) as reviews_added_2025,
    sum(reviews_added_2026) as reviews_added_2026,
    sum(s3_new_since_2024_selling_50_plus) as new_since_2024_selling_50_plus,
    (safe_divide(sum(reviews_added_2026), sum(reviews_added_2025)) - 1) * 100 as reviews_2026_vs_2025_pct

from {{ ref('mart_keepa_group_verdict') }}
group by is_diy
