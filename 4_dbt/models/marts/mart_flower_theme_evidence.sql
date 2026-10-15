-- Grain: 1 row = 1 play pattern x theme. How often buyers mention a motive, a making/display experience
-- or a problem, how they rate when they do, and how widely the theme is supported.
with totals as (

    select
        play_pattern,
        count(*) as total_reviews,
        avg(rating) as pattern_avg_rating,
        countif(rating <= 2) as low_reviews
    from {{ ref('fact_flower_reviews') }}
    group by play_pattern

),

tagged as (

    select
        flower.play_pattern,
        theme.theme_group,
        theme.theme,
        count(*) as mentions,
        count(distinct theme.parent_asin) as products,
        count(distinct flower.brand) as brands,
        avg(theme.rating) as avg_rating_when_mentioned,
        countif(theme.rating <= 2) as low_mentions

    from {{ ref('stg_flower_review_themes') }} as theme
    inner join {{ ref('dim_flower_product') }} as flower
        on theme.parent_asin = flower.parent_asin
    group by 1, 2, 3

),

grid as (

    -- every theme for every pattern, so "never mentioned" is visible as zero
    select totals.*, codebook.theme_group, codebook.theme
    from totals
    cross join {{ ref('flower_theme_codebook') }} as codebook

)

select
    grid.theme_group,
    grid.theme,
    grid.play_pattern,
    coalesce(tagged.mentions, 0) as mentions,
    grid.total_reviews,
    coalesce(tagged.products, 0) as products,
    coalesce(tagged.brands, 0) as brands,
    tagged.avg_rating_when_mentioned,
    grid.pattern_avg_rating,
    coalesce(tagged.low_mentions, 0) as low_mentions,
    grid.low_reviews,
    100.0 * coalesce(tagged.mentions, 0) / grid.total_reviews as mention_pct,
    100.0 * safe_divide(coalesce(tagged.low_mentions, 0), grid.low_reviews) as share_of_low_reviews_pct,
    {{ evidence_tier('coalesce(tagged.mentions, 0)', 'coalesce(tagged.products, 0)', 'coalesce(tagged.brands, 0)') }} as evidence

from grid
left join tagged
    on grid.play_pattern = tagged.play_pattern
    and grid.theme_group = tagged.theme_group
    and grid.theme = tagged.theme
