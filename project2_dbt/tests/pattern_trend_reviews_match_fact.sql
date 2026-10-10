-- Business logic: the reviews summed over play patterns must equal the flower review fact.
with mart as (select sum(reviews) as n from {{ ref('mart_flower_pattern_trend') }}),
fact as (select count(*) as n from {{ ref('fact_flower_reviews') }})

select mart.n as mart_reviews, fact.n as fact_reviews
from mart cross join fact
where mart.n != fact.n
