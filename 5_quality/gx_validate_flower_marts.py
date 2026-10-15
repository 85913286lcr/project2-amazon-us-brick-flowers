"""Great Expectations: business rules on the marts that carry the product decision (2023 and 2026).

dbt tests guard structure (nulls, duplicates, keys, value ranges) on every model. This gate asks a different
question of the final answer tables: do the numbers a business reader will act on make sense?

Reads BigQuery with SELECT only (through SQLAlchemy) and validates in an ephemeral GX context.
Writes docs/evidence/great_expectations/{validation_results.json, validation_summary.md}; exits 1 on failure.

Usage: python 5_quality/gx_validate_flower_marts.py [2023|2026]
With a scope only the marts of that stage are checked and the files get the scope as a suffix.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import great_expectations as gx
import pandas as pd
from sqlalchemy import create_engine, text

REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / 'docs' / 'evidence' / 'great_expectations'
PROJECT = os.environ.get('PROJECT2_GCP_PROJECT', 'united-firefly-509307-h9')
E = gx.expectations

QUADRANTS = ['A high interest, high satisfaction', 'B high interest, low satisfaction (improve)', 'C low interest, high satisfaction (niche)', 'D low interest, low satisfaction', 'Not enough evidence (under 300 reviews)']
TIERS = ['strong', 'medium', 'weak']

SUITES = [
    {'table': 'project2_marts.mart_flower_pattern_trend',
     'query': """select play_pattern, products, reviews, reviews_2022_jan_sep, reviews_2023_jan_sep, avg_rating, low_rating_pct,
                        relative_growth_index, quadrant,
                        products_strong_evidence + products_medium_evidence + products_weak_evidence as products_with_evidence
                 from project2_marts.mart_flower_pattern_trend""",
     'rules': [
         ('Every play pattern of the taxonomy has a row (22)', E.ExpectTableRowCountToEqual(value=22)),
         ('Play pattern is unique', E.ExpectColumnValuesToBeUnique(column='play_pattern')),
         ('Average rating is between 1 and 5', E.ExpectColumnValuesToBeBetween(column='avg_rating', min_value=1, max_value=5)),
         ('Low-rating share is between 0 and 100 %', E.ExpectColumnValuesToBeBetween(column='low_rating_pct', min_value=0, max_value=100)),
         ('Growth relative to the toy market is positive', E.ExpectColumnValuesToBeBetween(column='relative_growth_index', min_value=0, strict_min=True)),
         ('Quadrant is one of the five defined labels', E.ExpectColumnValuesToBeInSet(column='quadrant', value_set=QUADRANTS)),
         ('Every product is counted in exactly one evidence level', E.ExpectColumnPairValuesToBeEqual(column_A='products', column_B='products_with_evidence')),
     ]},
    {'table': 'project2_marts.mart_flower_theme_evidence',
     'query': """select theme, play_pattern, mentions, total_reviews, mention_pct, share_of_low_reviews_pct, avg_rating_when_mentioned, evidence
                 from project2_marts.mart_flower_theme_evidence""",
     'rules': [
         ('Mention share is between 0 and 100 %', E.ExpectColumnValuesToBeBetween(column='mention_pct', min_value=0, max_value=100)),
         ('Share of low-rated reviews is between 0 and 100 %', E.ExpectColumnValuesToBeBetween(column='share_of_low_reviews_pct', min_value=0, max_value=100)),
         ('Rating when mentioned is between 1 and 5', E.ExpectColumnValuesToBeBetween(column='avg_rating_when_mentioned', min_value=1, max_value=5)),
         ('Evidence tier is strong / medium / weak', E.ExpectColumnValuesToBeInSet(column='evidence', value_set=TIERS)),
         ('Mentions never exceed the reviews of the pattern', E.ExpectColumnPairValuesAToBeGreaterThanB(column_A='total_reviews', column_B='mentions', or_equal=True)),
     ]},
    {'table': 'project2_marts.mart_flower_need_evidence',
     'query': 'select need, play_pattern, sentences, products, brands, avg_rating, evidence from project2_marts.mart_flower_need_evidence',
     'rules': [
         ('A need is backed by at least one wish sentence', E.ExpectColumnValuesToBeBetween(column='sentences', min_value=1)),
         ('Products never exceed wish sentences', E.ExpectColumnPairValuesAToBeGreaterThanB(column_A='sentences', column_B='products', or_equal=True)),
         ('Evidence tier is strong / medium / weak', E.ExpectColumnValuesToBeInSet(column='evidence', value_set=TIERS)),
     ]},
    {'table': 'project2_marts.mart_keepa_group_verdict',
     'query': """select keepa_group, products_analyzed, signals_up, verdict, rating_now_median, price_now_median,
                        products_selling_100_plus, s3_new_since_2024_selling_50_plus
                 from project2_marts.mart_keepa_group_verdict""",
     'rules': [
         ('All seven product groups have a 2026 verdict', E.ExpectTableRowCountToEqual(value=7)),
         ('Verdict is trending / stable / not trending', E.ExpectColumnValuesToBeInSet(column='verdict', value_set=['trending', 'stable', 'not trending'])),
         ('A group is judged on 1 to 50 products', E.ExpectColumnValuesToBeBetween(column='products_analyzed', min_value=1, max_value=50)),
         ('Signals up is between 0 and 3', E.ExpectColumnValuesToBeBetween(column='signals_up', min_value=0, max_value=3)),
         ('Median rating is between 1 and 5', E.ExpectColumnValuesToBeBetween(column='rating_now_median', min_value=1, max_value=5)),
         ('Median price is positive', E.ExpectColumnValuesToBeBetween(column='price_now_median', min_value=0, strict_min=True)),
     ]},
    {'table': 'project2_marts.mart_keepa_new_forms',
     'query': 'select new_form, products, selling_50_plus, monthly_sold_sum, brands from project2_marts.mart_keepa_new_forms',
     'rules': [
         ('A product form has at least one product', E.ExpectColumnValuesToBeBetween(column='products', min_value=1)),
         ('Products selling 50+ never exceed products', E.ExpectColumnPairValuesAToBeGreaterThanB(column_A='products', column_B='selling_50_plus', or_equal=True)),
         ('Monthly units are not negative', E.ExpectColumnValuesToBeBetween(column='monthly_sold_sum', min_value=0)),
     ]},
]


def main(scope=None):
    suites = [s for s in SUITES if scope is None or ('keepa' in s['table']) == (scope == '2026')]
    suffix = f'_{scope}' if scope else ''
    engine = create_engine(f'bigquery://{PROJECT}', location='US')
    context = gx.get_context(mode='ephemeral')
    source = context.data_sources.add_pandas(name='project2_flower_marts')
    checks, ok = [], True
    with engine.connect() as con:
        for spec in suites:
            frame = pd.read_sql_query(text(spec['query']), con)
            for col in frame.select_dtypes(include='object').columns:
                try:
                    frame[col] = frame[col].astype(float)       # NUMERIC arrives as Decimal
                except (TypeError, ValueError):
                    pass
            name = spec['table'].split('.')[-1]
            batch = source.add_dataframe_asset(name=name).add_batch_definition_whole_dataframe('snapshot')
            suite = gx.ExpectationSuite(name=f'{name}_business_rules')
            for _, rule in spec['rules']:
                suite.add_expectation(rule)
            suite = context.suites.add(suite)
            validation = context.validation_definitions.add(gx.ValidationDefinition(name=f'validate_{name}', data=batch, suite=suite))
            result = validation.run(batch_parameters={'dataframe': frame})
            ok = ok and result.success
            for (label, _), check in zip(spec['rules'], result.results):
                checks.append({'table': spec['table'], 'rule': label, 'expectation': check.expectation_config.type,
                               'status': 'PASS' if check.success else 'FAIL', 'rows_checked': len(frame),
                               'unexpected_count': (check.result or {}).get('unexpected_count')})
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    report = {'gx_version': gx.__version__, 'timestamp_utc': stamp, 'scope': scope or 'all', 'expectation_count': len(checks),
              'overall_result': 'PASS' if ok else 'FAIL', 'data_access': 'SELECT only; ephemeral GX context', 'checks': checks}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / f'validation_results{suffix}.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + '\n')
    lines = [f'# Great Expectations business gate ({scope or "all marts"})', '', f'GX {gx.__version__} · {stamp} · {len(checks)} expectations · **{report["overall_result"]}**', '',
             '| Table | Business rule | Result |', '|---|---|---|']
    lines += [f"| {c['table'].split('.')[-1]} | {c['rule']} | {c['status']} |" for c in checks]
    (OUTPUT / f'validation_summary{suffix}.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'expectations': len(checks), 'overall_result': report['overall_result'],
                      'failed': [c['rule'] for c in checks if c['status'] != 'PASS']}, ensure_ascii=False))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
