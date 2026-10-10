-- Business logic: the product dimension must contain every raw product exactly once.
-- Guards against building the star schema on a sample or dropping rows on the way.
with raw as (select count(*) as n from {{ source('raw', 'main_amazon_products_raw') }}),
dim as (select count(*) as n from {{ ref('dim_product') }})

select raw.n as raw_rows, dim.n as dim_rows
from raw cross join dim
where raw.n != dim.n
