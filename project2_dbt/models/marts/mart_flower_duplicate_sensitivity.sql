-- Grain: 1 row = 1 play pattern. Does the conclusion depend on the repeated review rows in the source?
-- Growth relative to the toy market and average rating, computed with all rows and with duplicates removed.
with market as (

    select
        countif({{ local_year('review_datetime') }} = 2022) as all_2022,
        countif({{ local_year('review_datetime') }} = 2023) as all_2023,
        countif({{ local_year('review_datetime') }} = 2022 and not is_duplicate_review) as dedup_2022,
        countif({{ local_year('review_datetime') }} = 2023 and not is_duplicate_review) as dedup_2023
    from {{ ref('fact_reviews') }}
    where {{ local_month('review_datetime') }} <= 9

),

flower as (

    select
        play_pattern,
        count(*) as reviews_all,
        countif(not is_duplicate_review) as reviews_dedup,
        countif(review_year = 2022 and review_month <= 9) as all_2022,
        countif(review_year = 2023 and review_month <= 9) as all_2023,
        countif(review_year = 2022 and review_month <= 9 and not is_duplicate_review) as dedup_2022,
        countif(review_year = 2023 and review_month <= 9 and not is_duplicate_review) as dedup_2023,
        avg(rating) as avg_rating_all,
        avg(if(is_duplicate_review, null, rating)) as avg_rating_dedup
    from {{ ref('fact_flower_reviews') }}
    group by play_pattern

)

select
    flower.play_pattern,
    flower.reviews_all,
    flower.reviews_dedup,
    flower.reviews_all - flower.reviews_dedup as duplicate_rows,
    safe_divide(safe_divide(flower.all_2023, flower.all_2022), safe_divide(market.all_2023, market.all_2022))
        as relative_growth_all,
    safe_divide(safe_divide(flower.dedup_2023, flower.dedup_2022), safe_divide(market.dedup_2023, market.dedup_2022))
        as relative_growth_dedup,
    flower.avg_rating_all,
    flower.avg_rating_dedup

from flower
cross join market
