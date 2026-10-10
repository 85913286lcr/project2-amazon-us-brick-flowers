{{ config(severity='error', warn_if='>0', error_if='>200') }}

-- Known source issue: flower products with no brand, store or manufacturer. They cannot count towards the
-- "appears across brands" evidence rule.
select parent_asin
from {{ ref('dim_flower_product') }}
where brand is null
