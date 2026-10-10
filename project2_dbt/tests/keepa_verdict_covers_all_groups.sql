-- Business logic: every group that was searched must get a verdict, and no group may be analysed on
-- more than its top 50 products.
select keepa_group, products_analyzed
from {{ ref('mart_keepa_group_verdict') }}
where products_analyzed = 0 or products_analyzed > 50
