select distinct
    date(review_datetime) as date_key,
    extract(year from review_datetime) as year,
    extract(quarter from review_datetime) as quarter,
    extract(month from review_datetime) as month,
    format_date('%B', date(review_datetime)) as month_name,
    extract(day from review_datetime) as day,
    extract(dayofweek from review_datetime) as day_of_week

from {{ ref('stg_reviews') }}

where review_datetime is not null