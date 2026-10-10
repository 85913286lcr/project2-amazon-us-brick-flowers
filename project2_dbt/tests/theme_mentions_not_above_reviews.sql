-- Business logic: a theme cannot be mentioned in more reviews than exist, and low-rated mentions cannot
-- exceed all mentions.
select *
from {{ ref('mart_flower_theme_evidence') }}
where mentions > total_reviews
   or low_mentions > mentions
