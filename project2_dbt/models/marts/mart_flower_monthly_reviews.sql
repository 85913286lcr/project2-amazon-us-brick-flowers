-- Grain: 1 row = 1 play pattern x calendar month. Monthly review volume is the dataset's stand-in for a
-- monthly sales trend; it shows seasonality (Valentine's Day, Mother's Day, Christmas).
select
    play_pattern,
    date_trunc(review_date_local, month) as review_month,
    review_year,
    review_month as month_of_year,
    count(*) as reviews,
    avg(rating) as avg_rating,
    countif(rating <= 2) as low_rating_reviews,
    count(distinct parent_asin) as products_reviewed,
    count(distinct user_id) as customers

from {{ ref('fact_flower_reviews') }}
group by 1, 2, 3, 4
