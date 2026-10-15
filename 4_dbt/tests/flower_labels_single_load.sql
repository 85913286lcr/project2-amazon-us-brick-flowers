-- Duplicates: after keeping the newest load, a flower product must be labelled once only.
select parent_asin, count(*) as n
from {{ ref('stg_flower_product_labels') }}
group by parent_asin
having count(*) > 1
