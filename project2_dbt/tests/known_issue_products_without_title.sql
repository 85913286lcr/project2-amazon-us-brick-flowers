{{ config(severity='error', warn_if='>0', error_if='>1000') }}

-- Known source issue: products without a title cannot be classified by the flower rules.
select parent_asin
from {{ ref('dim_product') }}
where title is null or trim(title) = ''
