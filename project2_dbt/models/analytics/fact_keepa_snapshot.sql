-- Grain: 1 row = 1 product family per source, as seen on Amazon on the snapshot day (2026-10-07).
-- source = group  : current top sellers of a group
--          new    : listed since 2024 and selling 50+ a month
--          cohort : the 2023 top products of a group, followed into 2026
select
    source,
    parent_asin,
    asin,
    title,
    brand,
    play_pattern,
    keepa_group,
    starts_with(keepa_group, 'G') as is_target_group,
    substr(keepa_group, 1, 2) in ('G1', 'G2', 'G3', 'G4', 'G5') as is_diy,
    listed_since,
    monthly_sold_now,
    monthly_sold_1y_ago,
    rating_now,
    rating_count_now,
    price_now,
    sales_rank_now,
    sales_rank_2023,
    sales_rank_2025,
    sales_rank_2026,
    reviews_added_2023,
    reviews_added_2024,
    reviews_added_2025,
    reviews_added_2026,
    new_form,
    row_order,
    -- rank inside the group by current sales, used for "top 50 per group"
    row_number() over (partition by source, keepa_group order by row_order) as rank_in_group

from {{ ref('stg_keepa_products') }}
