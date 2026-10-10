-- Grain: 1 row = 1 product form among launches since 2024. What is new in flower toys?
with launches as (

    select *
    from {{ ref('fact_keepa_snapshot') }}
    where new_form is not null

),

medians as (

    select distinct
        new_form,
        percentile_cont(rating_now, 0.5) over (partition by new_form) as rating_median,
        percentile_cont(price_now, 0.5) over (partition by new_form) as price_median
    from launches

)

select
    launches.new_form,
    count(*) as products,
    countif(launches.monthly_sold_now >= 50) as selling_50_plus,
    coalesce(sum(launches.monthly_sold_now), 0) as monthly_sold_sum,
    count(distinct launches.brand) as brands,
    any_value(medians.rating_median) as rating_median,
    any_value(medians.price_median) as price_median

from launches
inner join medians using (new_form)
group by launches.new_form
