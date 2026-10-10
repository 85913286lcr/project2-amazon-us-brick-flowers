{# How widely a statement is supported: it must recur across reviews, products AND brands. #}
{% macro evidence_tier(reviews, products, brands) -%}
    case
        when {{ reviews }} >= {{ var('evidence_strong')['reviews'] }}
            and {{ products }} >= {{ var('evidence_strong')['products'] }}
            and {{ brands }} >= {{ var('evidence_strong')['brands'] }} then 'strong'
        when {{ reviews }} >= {{ var('evidence_medium')['reviews'] }}
            and {{ products }} >= {{ var('evidence_medium')['products'] }}
            and {{ brands }} >= {{ var('evidence_medium')['brands'] }} then 'medium'
        else 'weak'
    end
{%- endmacro %}
