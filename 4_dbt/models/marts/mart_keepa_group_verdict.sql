-- Grain: 1 row = 1 product group. Does the 2023 conclusion still hold on Amazon in 2026?
-- Three signals per group, each read from the current top 50 products:
--   S1  rating count added 1 Jan - 7 Oct 2026 vs the same window in 2025
--   S2  units sold per month now vs one year ago
--   S3  products first listed since 2024 that sell 50+ a month (compared with the median group)
-- Two or three signals up = trending, one = stable, none = not trending.
with top50 as (

    select *
    from {{ ref('fact_keepa_snapshot') }}
    where source = 'group' and is_target_group and rank_in_group <= 50

),

per_group as (

    select
        keepa_group,
        count(*) as products_analyzed,
        sum(reviews_added_2023) as reviews_added_2023,
        sum(reviews_added_2024) as reviews_added_2024,
        sum(reviews_added_2025) as reviews_added_2025,
        sum(reviews_added_2026) as reviews_added_2026,
        sum(monthly_sold_now) as monthly_sold_now_sum,
        sum(monthly_sold_1y_ago) as monthly_sold_1y_ago_sum,
        -- only products that have both values: the same products, a year apart
        sum(if(monthly_sold_now is not null and monthly_sold_1y_ago is not null, monthly_sold_now, null)) as same_now,
        sum(if(monthly_sold_now is not null and monthly_sold_1y_ago is not null, monthly_sold_1y_ago, null)) as same_ago
    from top50
    group by keepa_group

),

medians as (

    select distinct
        keepa_group,
        percentile_cont(sales_rank_2023, 0.5) over (partition by keepa_group) as median_rank_2023,
        percentile_cont(sales_rank_2025, 0.5) over (partition by keepa_group) as median_rank_2025,
        percentile_cont(sales_rank_2026, 0.5) over (partition by keepa_group) as median_rank_2026,
        percentile_cont(rating_now, 0.5) over (partition by keepa_group) as rating_now_median,
        percentile_cont(price_now, 0.5) over (partition by keepa_group) as price_now_median
    from top50

),

new_sellers as (

    select keepa_group, count(*) as new_since_2024_selling_50_plus
    from {{ ref('fact_keepa_snapshot') }}
    where source = 'new'
    group by keepa_group

),

signals as (

    select
        counts.keepa_group,
        substr(counts.keepa_group, 1, 2) in ('G1', 'G2', 'G3', 'G4', 'G5') as is_diy,
        coalesce(g.products_analyzed, 0) as products_analyzed,
        g.reviews_added_2023,
        g.reviews_added_2024,
        g.reviews_added_2025,
        g.reviews_added_2026,
        (safe_divide(g.reviews_added_2026, nullif(g.reviews_added_2025, 0)) - 1) * 100 as s1_reviews_2026_vs_2025_pct,
        (safe_divide(g.reviews_added_2025, nullif(g.reviews_added_2023, 0)) - 1) * 100 as s1_reviews_2025_vs_2023_pct,
        g.monthly_sold_now_sum,
        g.monthly_sold_1y_ago_sum,
        (safe_divide(g.monthly_sold_now_sum, nullif(g.monthly_sold_1y_ago_sum, 0)) - 1) * 100 as s2_monthly_sold_yoy_pct,
        (safe_divide(g.same_now, nullif(g.same_ago, 0)) - 1) * 100 as same_products_monthly_sold_yoy_pct,
        counts.products_selling_100_plus,
        coalesce(n.new_since_2024_selling_50_plus, 0) as s3_new_since_2024_selling_50_plus,
        m.median_rank_2023,
        m.median_rank_2025,
        m.median_rank_2026,
        m.rating_now_median,
        m.price_now_median

    from {{ ref('stg_keepa_finder_counts') }} as counts
    left join per_group as g using (keepa_group)
    left join medians as m using (keepa_group)
    left join new_sellers as n using (keepa_group)

),

flagged as (

    select
        *,
        coalesce(s1_reviews_2026_vs_2025_pct > 0, false) as s1_up,
        coalesce(s2_monthly_sold_yoy_pct > 0, false) as s2_up,
        s3_new_since_2024_selling_50_plus > percentile_cont(s3_new_since_2024_selling_50_plus, 0.5) over () as s3_up
    from signals

)

select
    *,
    cast(s1_up as int64) + cast(s2_up as int64) + cast(s3_up as int64) as signals_up,
    case cast(s1_up as int64) + cast(s2_up as int64) + cast(s3_up as int64)
        when 0 then 'not trending'
        when 1 then 'stable'
        else 'trending'
    end as verdict

from flagged
