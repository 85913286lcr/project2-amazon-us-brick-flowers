{{ config(
    partition_by={'field': 'date_key', 'data_type': 'date', 'granularity': 'year'},
    cluster_by=['parent_asin', 'user_id']
) }}

-- Grain: 1 row = 1 customer review as delivered by the source. Partitioned by review year and clustered by
-- product and customer, so product-level and customer-level aggregations scan only the blocks they need.
--
-- The source contains repeated rows (same customer, same item, same millisecond). They are kept, because raw
-- is never silently reduced, and flagged so that any analysis can exclude them.
select
    asin,
    parent_asin,
    user_id,
    rating,
    review_datetime,
    date(review_datetime) as date_key,
    helpful_vote,
    verified_purchase,
    title as review_title,
    review_text,
    row_number() over (
        partition by user_id, asin, review_datetime
        order by rating, coalesce(helpful_vote, -1), coalesce(title, ''), coalesce(review_text, '')
    ) > 1 as is_duplicate_review

from {{ ref('stg_reviews') }}
