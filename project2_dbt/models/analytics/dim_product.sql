select
    parent_asin,
    title,
    main_category,
    average_rating,
    rating_number,
    price,
    store,
    categories,
    features,
    description

from {{ ref('stg_products') }}