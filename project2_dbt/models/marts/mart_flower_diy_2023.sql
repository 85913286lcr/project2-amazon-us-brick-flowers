-- Grain: 1 row = 1 DIY family. Is "do it yourself" a trend, or only one kind of DIY?
with baseline as (

    select
        max(case when review_year = 2023 then jan_sep_reviews end)
            / max(case when review_year = 2022 then jan_sep_reviews end) as market_ratio_2023_vs_2022
    from {{ ref('mart_review_baseline') }}

),

per_family as (

    select
        pattern.diy_family,
        count(*) as products,
        count(distinct stats.brand) as brands,
        sum(stats.reviews_2022_jan_sep) as reviews_2022_jan_sep,
        sum(stats.reviews_2023_jan_sep) as reviews_2023_jan_sep

    from {{ ref('mart_flower_product_stats') }} as stats
    inner join {{ ref('dim_play_pattern') }} as pattern
        on stats.play_pattern = pattern.play_pattern
    group by 1

)

select
    diy_family,
    products,
    brands,
    reviews_2022_jan_sep,
    reviews_2023_jan_sep,
    (safe_divide(reviews_2023_jan_sep, reviews_2022_jan_sep) - 1) * 100 as yoy_pct,
    safe_divide(safe_divide(reviews_2023_jan_sep, reviews_2022_jan_sep), market_ratio_2023_vs_2022)
        as relative_growth_index

from per_family
cross join baseline
