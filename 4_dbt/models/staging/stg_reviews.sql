select
    json_value(data, '$.asin') as asin,
    json_value(data, '$.parent_asin') as parent_asin,
    json_value(data, '$.user_id') as user_id,

    safe_cast(json_value(data, '$.rating') as float64)
        as rating,

    json_value(data, '$.title') as title,
    json_value(data, '$.text') as review_text,

    timestamp_millis(
        safe_cast(json_value(data, '$.timestamp') as int64)
    ) as review_datetime,

    case
        when safe_cast(json_value(data, '$.helpful_vote') as int64) >= 0
            then safe_cast(json_value(data, '$.helpful_vote') as int64)
        else null
    end as helpful_vote,

    safe_cast(json_value(data, '$.verified_purchase') as bool)
        as verified_purchase

from {{ source('raw', 'main_amazon_reviews_raw') }}
