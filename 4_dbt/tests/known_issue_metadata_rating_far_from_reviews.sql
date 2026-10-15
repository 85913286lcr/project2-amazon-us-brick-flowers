{{ config(severity='error', warn_if='>0', error_if='>20000') }}

-- Known source inconsistency: metadata average rating more than one star away from the average of the product's
-- own reviews (products with 30+ reviews). The marts therefore use the rating computed from reviews.
select product.parent_asin, product.average_rating, reviews.review_avg
from {{ ref('dim_product') }} as product
inner join (
    select parent_asin, count(*) as review_rows, avg(rating) as review_avg from {{ ref('fact_reviews') }} group by parent_asin
) as reviews
    on product.parent_asin = reviews.parent_asin
where reviews.review_rows >= 30
    and abs(product.average_rating - reviews.review_avg) > 1
