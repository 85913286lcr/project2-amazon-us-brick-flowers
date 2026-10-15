with expanded_categories as (

    select
        trim(json_value(category_json, '$')) as category

    from {{ ref('dim_product') }} as product
    cross join unnest(json_query_array(product.categories, '$')) as category_json

),

unique_categories as (

    select distinct category
    from expanded_categories
    where category is not null
        and category != ''

)

select
    to_hex(sha256(category)) as category_key,
    category

from unique_categories
