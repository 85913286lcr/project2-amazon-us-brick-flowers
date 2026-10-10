select
    json_value(data, '$.parent_asin') as parent_asin,
    json_value(data, '$.title') as title,
    json_value(data, '$.main_category') as main_category,

    safe_cast(json_value(data, '$.average_rating') as float64)
        as average_rating,

    safe_cast(json_value(data, '$.rating_number') as int64)
        as rating_number,

    safe_cast(json_value(data, '$.price') as numeric)
        as price,

    json_value(data, '$.store') as store,

    json_query(data, '$.categories') as categories,
    json_query(data, '$.features') as features,
    json_query(data, '$.description') as description

from {{ source('raw', 'main_amazon_products_raw') }}