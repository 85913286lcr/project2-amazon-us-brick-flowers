with latest as (
    {{ latest_load(source('raw', 'main_flower_product_labels')) }}
)

select
    json_value(data, '$.parent_asin') as parent_asin,
    json_value(data, '$.relevance_tier') as relevance_tier,
    json_value(data, '$.relevance') as relevance,
    json_value(data, '$.primary_pattern') as play_pattern,
    json_value(data, '$.patterns') as all_patterns,
    json_value(data, '$.brand') as brand

from latest
