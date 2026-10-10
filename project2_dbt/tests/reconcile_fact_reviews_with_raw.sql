-- Business logic: the review fact must contain every raw review.
with raw as (select count(*) as n from {{ source('raw', 'main_amazon_reviews_raw') }}),
fact as (select count(*) as n from {{ ref('fact_reviews') }})

select raw.n as raw_rows, fact.n as fact_rows
from raw cross join fact
where raw.n != fact.n
