-- Grain: 1 row = 1 reviewer (Amazon user_id). Derived columns describe review behaviour, the only
-- purchase-related behaviour this dataset records.
with per_customer as (

    select
        user_id,
        count(*) as lifetime_review_count,
        count(distinct parent_asin) as products_reviewed,
        min(date_key) as first_review_date,
        max(date_key) as last_review_date,
        avg(rating) as mean_rating_given,
        avg(case when verified_purchase is null then null when verified_purchase then 1.0 else 0.0 end)
            as verified_purchase_share

    from {{ ref('fact_reviews') }}
    where user_id is not null
    group by user_id

)

select
    user_id,
    lifetime_review_count,
    products_reviewed,
    first_review_date,
    last_review_date,
    date_diff(last_review_date, first_review_date, day) as active_days,
    mean_rating_given,
    verified_purchase_share,
    case
        when lifetime_review_count = 1 then '1 one-time reviewer'
        when lifetime_review_count between 2 and 4 then '2 occasional (2-4)'
        when lifetime_review_count between 5 and 19 then '3 regular (5-19)'
        else '4 heavy (20+)'
    end as activity_segment

from per_customer
