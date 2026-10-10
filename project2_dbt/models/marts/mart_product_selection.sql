with review_metrics as (

    select
        parent_asin,
        -- Historical review evidence, not sales.
        count(*) as review_count,
        -- Engagement evidence, not demand or sales.
        coalesce(sum(helpful_vote), 0) as total_helpful_votes,
        avg(rating) as mean_review_rating,
        -- Unknown ratings are excluded from the share denominator.
        avg(
            case
                when rating is null then null
                when rating <= 2 then 1.0
                else 0.0
            end
        ) as low_rating_share,
        -- Unknown purchase status is excluded from the share denominator.
        avg(
            case
                when verified_purchase is null then null
                when verified_purchase then 1.0
                else 0.0
            end
        ) as verified_purchase_share

    from {{ ref('fact_reviews') }}
    group by parent_asin

)

select
    product.parent_asin,
    product.title,
    product.main_category,
    product.price,
    product.average_rating as metadata_average_rating,
    product.rating_number as metadata_rating_count,
    coalesce(reviews.review_count, 0) as review_count,
    coalesce(reviews.total_helpful_votes, 0) as total_helpful_votes,
    reviews.mean_review_rating,
    reviews.low_rating_share,
    reviews.verified_purchase_share

from {{ ref('dim_product') }} as product
left join review_metrics as reviews
    on product.parent_asin = reviews.parent_asin
