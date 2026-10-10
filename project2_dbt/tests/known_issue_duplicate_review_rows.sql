{{ config(severity='error', warn_if='>0', error_if='>325000') }}

-- Known source issue: repeated review rows (same customer, item and millisecond). They are flagged, not dropped.
-- WARN while they stay under 2 % of all reviews (about 325,000); ERROR above that.
select asin, user_id, review_datetime
from {{ ref('fact_reviews') }}
where is_duplicate_review
