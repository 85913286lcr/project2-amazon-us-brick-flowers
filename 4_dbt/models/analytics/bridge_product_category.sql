with expanded_categories as (

    select
        product.parent_asin,
        trim(json_value(category_json, '$')) as category,
        category_offset + 1 as category_level

    from {{ ref('dim_product') }} as product
    cross join unnest(json_query_array(product.categories, '$')) as category_json
        with offset as category_offset

),

product_categories as (

    select
        parent_asin,
        category,
        -- Repeated categories retain their earliest original array position.
        min(category_level) as category_level

    from expanded_categories
    where category is not null
        and category != ''
    group by parent_asin, category

)

select
    product_category.parent_asin,
    category.category_key,
    product_category.category_level

from product_categories as product_category
inner join {{ ref('dim_category') }} as category
    on product_category.category = category.category
