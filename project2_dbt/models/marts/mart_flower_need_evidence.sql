-- Grain: 1 row = 1 play pattern x unmet need (plus an "all flower toys" total per need).
-- Needs come from sentences where buyers say what they wish the product had.
with wishes as (

    select
        need.sentence_id,
        need.parent_asin,
        need.rating,
        need.need,
        {{ local_year('need.review_datetime') }} as review_year,
        flower.play_pattern,
        flower.brand

    from {{ ref('stg_flower_wish_needs') }} as need
    inner join {{ ref('dim_flower_product') }} as flower
        on need.parent_asin = flower.parent_asin

),

by_pattern as (

    select
        play_pattern,
        need,
        count(*) as sentences,
        count(distinct parent_asin) as products,
        count(distinct brand) as brands,
        avg(rating) as avg_rating,
        min(review_year) as first_year,
        max(review_year) as last_year,
        cast(null as int64) as patterns
    from wishes
    group by 1, 2

),

overall as (

    select
        'All flower toys' as play_pattern,
        need,
        count(*) as sentences,
        count(distinct parent_asin) as products,
        count(distinct brand) as brands,
        avg(rating) as avg_rating,
        min(review_year) as first_year,
        max(review_year) as last_year,
        count(distinct play_pattern) as patterns
    from wishes
    group by 2

),

unioned as (
    select * from by_pattern
    union all
    select * from overall
)

select
    *,
    {{ evidence_tier('sentences', 'products', 'brands') }} as evidence

from unioned
