{{ config(severity='error', warn_if='>0', error_if='>10000') }}

-- Known source issue: products present in the metadata file with no row in the review file.
select product.parent_asin
from {{ ref('dim_product') }} as product
left join (select distinct parent_asin from {{ ref('fact_reviews') }}) as reviewed
    on product.parent_asin = reviewed.parent_asin
where reviewed.parent_asin is null
