with latest as (
    {{ latest_load(source('raw', 'main_keepa_products')) }}
)

select
    safe_cast(json_value(data, '$.row_order') as int64) as row_order,
    json_value(data, '$.source') as source,
    json_value(data, '$.asin') as asin,
    json_value(data, '$.parent_asin') as parent_asin,
    json_value(data, '$.title') as title,
    json_value(data, '$.brand') as brand,
    json_value(data, '$.primary_pattern') as play_pattern,
    json_value(data, '$.keepa_group') as keepa_group,
    safe_cast(json_value(data, '$.listed_since') as date) as listed_since,
    safe_cast(json_value(data, '$.monthly_sold_now') as float64) as monthly_sold_now,
    safe_cast(json_value(data, '$.monthly_sold_1y_ago') as float64) as monthly_sold_1y_ago,
    safe_cast(json_value(data, '$.rating_now') as float64) as rating_now,
    safe_cast(json_value(data, '$.rating_count_now') as float64) as rating_count_now,
    safe_cast(json_value(data, '$.price_now') as float64) as price_now,
    safe_cast(json_value(data, '$.sales_rank_now') as float64) as sales_rank_now,
    safe_cast(json_value(data, '$.reviews_added_2023') as float64) as reviews_added_2023,
    safe_cast(json_value(data, '$.reviews_added_2024') as float64) as reviews_added_2024,
    safe_cast(json_value(data, '$.reviews_added_2025') as float64) as reviews_added_2025,
    safe_cast(json_value(data, '$.reviews_added_2026') as float64) as reviews_added_2026,
    safe_cast(json_value(data, '$.rank_2023') as float64) as sales_rank_2023,
    safe_cast(json_value(data, '$.rank_2025') as float64) as sales_rank_2025,
    safe_cast(json_value(data, '$.rank_2026') as float64) as sales_rank_2026,
    json_value(data, '$.new_form') as new_form

from latest
