{# Year / month / date of a timestamp in the analysis time zone (see var analysis_timezone). #}
{% macro local_year(ts) -%} extract(year from {{ ts }} at time zone '{{ var("analysis_timezone") }}') {%- endmacro %}
{% macro local_month(ts) -%} extract(month from {{ ts }} at time zone '{{ var("analysis_timezone") }}') {%- endmacro %}
{% macro local_date(ts) -%} date({{ ts }}, '{{ var("analysis_timezone") }}') {%- endmacro %}
