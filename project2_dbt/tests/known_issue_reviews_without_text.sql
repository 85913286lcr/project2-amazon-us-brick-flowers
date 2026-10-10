{{ config(severity='error', warn_if='>0', error_if='>160000') }}

-- Known source issue: reviews with a rating but no text. They count as reviews but cannot be tagged with a theme.
-- WARN under 1 % of all reviews; ERROR above.
select asin, user_id, review_datetime
from {{ ref('fact_reviews') }}
where review_text is null or trim(review_text) = ''
