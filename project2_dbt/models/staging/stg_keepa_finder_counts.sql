with latest as (
    {{ latest_load(source('raw', 'main_keepa_finder_counts')) }}
)

select
    json_value(data, '$.keepa_group') as keepa_group,
    safe_cast(json_value(data, '$.products_selling_100_plus') as int64) as products_selling_100_plus

from latest
