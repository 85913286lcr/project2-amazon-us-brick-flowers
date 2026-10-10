with latest as (
    {{ latest_load(source('raw', 'main_flower_review_themes')) }}
)

select
    safe_cast(json_value(data, '$.review_row_id') as int64) as review_row_id,
    json_value(data, '$.parent_asin') as parent_asin,
    safe_cast(json_value(data, '$.rating') as float64) as rating,
    json_value(data, '$.theme_group') as theme_group,
    json_value(data, '$.theme') as theme

from latest
