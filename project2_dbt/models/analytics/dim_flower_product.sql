-- Grain: 1 row = 1 flower product in the analysis scope. Extends dim_product with the enrichment labels.
select
    label.parent_asin,
    label.play_pattern,
    label.all_patterns,
    label.relevance_tier,
    label.relevance,
    label.brand,
    lower(coalesce(label.brand, '')) = 'lego' as is_lego_brand,
    product.title,
    product.price,
    product.average_rating as metadata_average_rating,
    product.rating_number as metadata_rating_count

from {{ ref('stg_flower_product_labels') }} as label
left join {{ ref('dim_product') }} as product
    on label.parent_asin = product.parent_asin
