-- Grain: 1 row = 1 play pattern (how a flower toy is used). Maintained as a seed written by the enrichment step.
select
    play_pattern,
    diy_family,
    is_diy

from {{ ref('flower_play_patterns') }}
