{{ config(cluster_by=['play_pattern']) }}

-- Grain: 1 row = 1 review of a flower product. A narrow copy of fact_reviews with the play pattern attached
-- and the review time expressed in the analysis time zone; every flower mart reads from here.
select
    review.parent_asin,
    review.user_id,
    review.rating,
    review.review_datetime,
    {{ local_date('review.review_datetime') }} as review_date_local,
    {{ local_year('review.review_datetime') }} as review_year,
    {{ local_month('review.review_datetime') }} as review_month,
    review.helpful_vote,
    review.verified_purchase,
    review.is_duplicate_review,
    flower.play_pattern,
    flower.brand

from {{ ref('fact_reviews') }} as review
inner join {{ ref('dim_flower_product') }} as flower
    on review.parent_asin = flower.parent_asin
