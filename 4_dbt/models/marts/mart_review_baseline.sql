-- All Toys & Games reviews written January-September of each year. The dataset itself thins out in 2023,
-- so flower growth is always read relative to this baseline.
select
    {{ local_year('review_datetime') }} as review_year,
    count(*) as jan_sep_reviews

from {{ ref('fact_reviews') }}
where {{ local_month('review_datetime') }} <= 9
group by 1
