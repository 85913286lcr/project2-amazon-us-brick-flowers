-- Grain: 1 row = 1 flower product. Review evidence per product; no minimum review count is applied,
-- instead each product carries an evidence level.
with reviews as (

    select
        parent_asin,
        count(rating) as review_count,
        avg(rating) as review_avg,
        100.0 * avg(case when rating <= 2 then 1 else 0 end) as low_rating_pct,
        countif(review_year = 2021 and review_month <= 9) as reviews_2021_jan_sep,
        countif(review_year = 2022 and review_month <= 9) as reviews_2022_jan_sep,
        countif(review_year = 2023 and review_month <= 9) as reviews_2023_jan_sep,
        min(review_datetime) as first_review_at,
        max(review_datetime) as last_review_at

    from {{ ref('fact_flower_reviews') }}
    group by parent_asin

)

select
    flower.parent_asin,
    flower.title,
    flower.brand,
    flower.is_lego_brand,
    flower.play_pattern,
    flower.relevance,
    flower.price,
    flower.metadata_average_rating,
    flower.metadata_rating_count,
    coalesce(reviews.review_count, 0) as review_count,
    reviews.review_avg,
    reviews.low_rating_pct,
    coalesce(reviews.reviews_2021_jan_sep, 0) as reviews_2021_jan_sep,
    coalesce(reviews.reviews_2022_jan_sep, 0) as reviews_2022_jan_sep,
    coalesce(reviews.reviews_2023_jan_sep, 0) as reviews_2023_jan_sep,
    reviews.first_review_at,
    {{ local_year('reviews.first_review_at') }} as first_review_year,
    case
        when coalesce(reviews.review_count, 0) >= 30 then 'strong (30+ reviews)'
        when reviews.review_count >= 5 then 'medium (5-29 reviews)'
        when reviews.review_count >= 1 then 'weak (1-4 reviews)'
        else 'no reviews (metadata only)'
    end as evidence_level

from {{ ref('dim_flower_product') }} as flower
left join reviews
    on flower.parent_asin = reviews.parent_asin
