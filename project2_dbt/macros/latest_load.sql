{# Raw is append-only. Keep only the rows of the newest Meltano sync of a source table. #}
{% macro latest_load(source_relation) -%}
    select *
    from {{ source_relation }}
    qualify safe_cast(json_value(data, '$._sdc_sync_started_at') as int64)
        = max(safe_cast(json_value(data, '$._sdc_sync_started_at') as int64)) over ()
{%- endmacro %}
