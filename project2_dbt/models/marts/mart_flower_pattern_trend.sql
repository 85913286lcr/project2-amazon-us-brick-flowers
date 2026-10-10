-- Grain: 1 row = 1 play pattern. Demand (review volume as a proxy), growth relative to the whole toy
-- market, satisfaction, and the interest x satisfaction quadrant. This table answers "which kind of
-- flower toy should the store sell".
with baseline as (

    select
        max(case when review_year = 2023 then jan_sep_reviews end)
            / max(case when review_year = 2022 then jan_sep_reviews end) as market_ratio_2023_vs_2022
    from {{ ref('mart_review_baseline') }}

),

per_pattern as (

    select
        play_pattern,
        count(*) as products,
        count(distinct brand) as brands,
        sum(review_count) as reviews,
        countif(evidence_level like 'strong%') as products_strong_evidence,
        countif(evidence_level like 'medium%') as products_medium_evidence,
        countif(evidence_level like 'weak%') as products_weak_evidence,
        sum(reviews_2021_jan_sep) as reviews_2021_jan_sep,
        sum(reviews_2022_jan_sep) as reviews_2022_jan_sep,
        sum(reviews_2023_jan_sep) as reviews_2023_jan_sep,
        sum(review_avg * review_count) / sum(review_count) as avg_rating,
        sum(low_rating_pct * review_count) / sum(review_count) as low_rating_pct,
        countif(first_review_year >= 2022) as new_products_2022_23,
        sum(metadata_rating_count) as metadata_ratings

    from {{ ref('mart_flower_product_stats') }}
    group by play_pattern

),

median_price as (

    select distinct
        play_pattern,
        percentile_cont(price, 0.5) over (partition by play_pattern) as median_price
    from {{ ref('mart_flower_product_stats') }}

),

cutoffs as (

    -- Quadrant cut-offs are the medians of the patterns that have enough reviews to be compared.
    select distinct
        percentile_cont(reviews_2023_jan_sep, 0.5) over () as interest_cutoff,
        percentile_cont(avg_rating, 0.5) over () as satisfaction_cutoff
    from per_pattern
    where reviews >= {{ var('quadrant_min_reviews') }}

)

select
    p.play_pattern,
    p.products,
    p.brands,
    p.reviews,
    p.products_strong_evidence,
    p.products_medium_evidence,
    p.products_weak_evidence,
    p.reviews_2021_jan_sep,
    p.reviews_2022_jan_sep,
    p.reviews_2023_jan_sep,
    p.avg_rating,
    p.low_rating_pct,
    m.median_price,
    p.new_products_2022_23,
    p.metadata_ratings,
    (safe_divide(p.reviews_2023_jan_sep, p.reviews_2022_jan_sep) - 1) * 100 as yoy_pct,
    safe_divide(safe_divide(p.reviews_2023_jan_sep, p.reviews_2022_jan_sep), b.market_ratio_2023_vs_2022)
        as relative_growth_index,
    case
        when p.reviews < {{ var('quadrant_min_reviews') }} then 'Not enough evidence (under 300 reviews)'
        when p.reviews_2023_jan_sep >= c.interest_cutoff and p.avg_rating >= c.satisfaction_cutoff then 'A high interest, high satisfaction'
        when p.reviews_2023_jan_sep >= c.interest_cutoff then 'B high interest, low satisfaction (improve)'
        when p.avg_rating >= c.satisfaction_cutoff then 'C low interest, high satisfaction (niche)'
        else 'D low interest, low satisfaction'
    end as quadrant

from per_pattern as p
left join median_price as m using (play_pattern)
cross join baseline as b
cross join cutoffs as c
