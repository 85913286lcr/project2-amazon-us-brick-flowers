-- Duplicates: variations share one rating count, so a product family may appear once per source only.
select source, parent_asin, count(*) as n
from {{ ref('fact_keepa_snapshot') }}
group by source, parent_asin
having count(*) > 1
