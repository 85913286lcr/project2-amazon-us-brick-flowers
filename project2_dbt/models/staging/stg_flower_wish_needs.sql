with latest as (
    {{ latest_load(source('raw', 'main_flower_wish_needs')) }}
)

select
    safe_cast(json_value(data, '$.sentence_id') as int64) as sentence_id,
    json_value(data, '$.parent_asin') as parent_asin,
    safe_cast(json_value(data, '$.rating') as float64) as rating,
    timestamp_millis(safe_cast(json_value(data, '$.review_ts_ms') as int64)) as review_datetime,
    json_value(data, '$.need') as need,
    json_value(data, '$.sentence') as sentence

from latest
