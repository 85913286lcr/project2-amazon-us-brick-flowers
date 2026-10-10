-- Grain: 1 row = 1 customer who reviewed at least one flower toy. Segments by purchase (review) behaviour:
-- how many flower toys, which kinds, and how active the customer is across all toys.
with flower as (

    select
        review.user_id,
        count(*) as flower_reviews,
        count(distinct review.parent_asin) as flower_products,
        count(distinct review.play_pattern) as flower_patterns,
        countif(pattern.diy_family = 'DIY: adult brick building') as brick_flower_reviews,
        countif(pattern.is_diy) as diy_reviews,
        avg(review.rating) as flower_avg_rating,
        min(review.review_date_local) as first_flower_review,
        max(review.review_date_local) as last_flower_review

    from {{ ref('fact_flower_reviews') }} as review
    inner join {{ ref('dim_play_pattern') }} as pattern
        on review.play_pattern = pattern.play_pattern
    where review.user_id is not null
    group by 1

)

select
    flower.user_id,
    flower.flower_reviews,
    flower.flower_products,
    flower.flower_patterns,
    flower.brick_flower_reviews,
    flower.diy_reviews,
    flower.flower_avg_rating,
    flower.first_flower_review,
    flower.last_flower_review,
    customer.lifetime_review_count,
    customer.activity_segment,
    safe_divide(flower.flower_reviews, customer.lifetime_review_count) as flower_share_of_reviews,
    case
        when flower.flower_products >= 3 then '3 flower collector (3+ products)'
        when flower.flower_products = 2 then '2 repeat flower buyer (2 products)'
        else '1 single flower purchase'
    end as flower_loyalty_segment,
    case
        when flower.brick_flower_reviews > 0 and flower.brick_flower_reviews = flower.flower_reviews then 'brick flowers only'
        when flower.brick_flower_reviews > 0 then 'brick flowers + other flower toys'
        when flower.diy_reviews > 0 then 'other DIY flower toys'
        else 'non-DIY flower toys'
    end as flower_interest_segment

from flower
left join {{ ref('dim_customer') }} as customer
    on flower.user_id = customer.user_id
