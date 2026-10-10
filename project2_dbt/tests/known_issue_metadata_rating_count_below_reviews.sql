{{ config(severity='error', warn_if='>0', error_if='>20000') }}

-- Known source inconsistency: the metadata says a product has fewer ratings than the review file has rows for it.
-- This is why the marts count reviews themselves instead of trusting rating_number.
select product.parent_asin, product.rating_number, reviews.review_rows
from {{ ref('dim_product') }} as product
inner join (
    select parent_asin, count(*) as review_rows from {{ ref('fact_reviews') }} group by parent_asin
) as reviews
    on product.parent_asin = reviews.parent_asin
where product.rating_number < reviews.review_rows
