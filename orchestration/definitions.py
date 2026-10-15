"""Dagster orchestration: the pipeline in the order the work was done, in two stages.

    FIND (Amazon 2023 reviews)
        raw_ingestion -> flower_enrichment -> labels_loaded -> models_2023_tested
                      -> quality_gate_2023 -> answer_2023_reconciled

    VERIFY (Amazon 2026 snapshot), starts only after the 2023 answer is confirmed
        amazon_2026_snapshot -> snapshot_labelled -> snapshot_loaded -> models_2026_tested
                             -> quality_gate_2026 -> answer_2026_reconciled

The 2026 data is fetched for the product groups that the 2023 answer points to, so it cannot come first.
Each asset runs the real step (it does not read a saved result), fails loudly, and records what it did
under docs/evidence/dagster/. The Keepa step only calls the API for responses that are not cached yet.

Jobs: find_2023 (first stage), verify_2026 (second stage), project2_flower_pipeline (both, in order).

The steps live in separate virtual environments (Meltano, dbt and Great Expectations pin conflicting
dependencies), so each command is configurable through an environment variable.
"""
import json
import os
import re
import subprocess
from pathlib import Path

from dagster import AssetSelection, Definitions, Failure, MetadataValue, ScheduleDefinition, asset, define_asset_job

REPO = Path(__file__).resolve().parents[1]
EVIDENCE = REPO / 'docs' / 'evidence' / 'dagster'
PYTHON = os.environ.get('PROJECT2_PYTHON', 'python')                    # duckdb + pandas
PYTHON_QUALITY = os.environ.get('PROJECT2_PYTHON_QUALITY', 'python')    # great_expectations + sqlalchemy-bigquery
MELTANO = os.environ.get('PROJECT2_MELTANO', 'meltano')
DBT = os.environ.get('PROJECT2_DBT', 'dbt')
TAG_2026 = 'tag:amazon_2026+'            # the models built from the 2026 snapshot, and their tests


def run(args, cwd=REPO, timeout=3600):
    result = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise Failure(description=f'Command failed: {" ".join(map(str, args))}',
                      metadata={'stdout': MetadataValue.text(result.stdout[-3000:]), 'stderr': MetadataValue.text(result.stderr[-3000:])})
    return result.stdout + result.stderr


def record(context, name, details):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / f'{name}.json').write_text(json.dumps(details, indent=2, ensure_ascii=False) + '\n')
    context.add_output_metadata({'result': MetadataValue.json(details)})


def meltano_load(context, name, tap):
    out = run([MELTANO, 'run', '--refresh-catalog', tap, 'target-bigquery'], cwd=REPO / 'meltano')
    records = re.search(r'\((\d+) schemas, (\d+) records', out)
    if 'Run completed' not in out or not records:
        raise Failure('Meltano did not report a completed run')
    record(context, name, {'tap': tap, 'streams': int(records.group(1)), 'records_sent': int(records.group(2))})


def dbt_build(context, name, selection):
    out = re.sub(r'\x1b\[[0-9;]*m', '', run([DBT, 'build', '--no-use-colors', *selection], cwd=REPO / 'project2_dbt'))
    summary = re.search(r'Done\. PASS=(\d+) WARN=(\d+) ERROR=(\d+) SKIP=(\d+)', out)
    if not summary or int(summary.group(3)) or int(summary.group(4)):
        raise Failure('dbt build did not finish cleanly')
    (EVIDENCE.parent / 'dbt').mkdir(parents=True, exist_ok=True)
    (EVIDENCE.parent / 'dbt' / f'dbt_build_{name}.txt').write_text(out)
    tests = re.search(r'(\d+) data tests', out)
    known = re.findall(r'WARN (\d+) (known_issue_\w+)', out)
    record(context, name, {'passed': int(summary.group(1)), 'warnings': int(summary.group(2)), 'errors': 0,
                           'known_issues': {issue: int(n) for n, issue in known},
                           'data_tests_in_project': int(tests.group(1)) if tests else None})


def quality_gate(context, name, scope):
    run([PYTHON_QUALITY, 'quality/gx_validate_flower_marts.py', scope])
    report = json.loads((REPO / f'docs/evidence/great_expectations/validation_results_{scope}.json').read_text())
    if report['overall_result'] != 'PASS':
        raise Failure('Great Expectations gate failed')
    record(context, name, {'scope': scope, 'expectations': report['expectation_count'], 'result': report['overall_result'],
                           'timestamp_utc': report['timestamp_utc']})


def reconcile(context, name, scope):
    export = REPO / 'docs/evidence/contract/export'
    run([PYTHON_QUALITY, 'scripts/export_marts_for_contract.py', export, '--scope', scope])
    out = run([PYTHON_QUALITY, 'scripts/verify_against_contract.py', export, '--scope', scope])
    (REPO / f'docs/evidence/contract/verify_{scope}.txt').write_text(out)
    if 'RESULT PASS' not in out:
        raise Failure('The warehouse no longer reproduces the contract')
    record(context, name, {'result': 'PASS', 'scope': scope, 'tables_matched': out.count('\nOK ') + out.startswith('OK ')})


# ---------------------------------------------------------------- stage 1: FIND, on the Amazon 2023 reviews

@asset(group_name='find_2023', description='Verify the two raw Amazon tables in DuckDB: row counts, null keys, duplicate product keys.')
def raw_ingestion(context):
    run([PYTHON, 'ingestion/ingest_amazon_to_duckdb.py'])
    record(context, 'raw_ingestion', json.loads((REPO / 'docs/evidence/ingestion/ingestion_verify.json').read_text()))


@asset(group_name='find_2023', deps=[raw_ingestion], description='Label flower toys and their reviews (Python rules), write three tables for Meltano.')
def flower_enrichment(context):
    run([PYTHON, 'enrichment/build_flower_tables.py'])
    record(context, 'flower_enrichment', json.loads((REPO / 'docs/evidence/enrichment/enrichment_summary.json').read_text()))


@asset(group_name='find_2023', deps=[flower_enrichment], description='Meltano: the three label tables to BigQuery (append-only raw).')
def labels_loaded(context):
    meltano_load(context, 'labels_loaded', 'tap-duckdb-labels-2023')


@asset(group_name='find_2023', deps=[labels_loaded], description='dbt build of everything based on the 2023 reviews: staging, star schema, marts and their tests.')
def models_2023_tested(context):
    dbt_build(context, 'models_2023_tested', ['--full-refresh', '--exclude', TAG_2026])


@asset(group_name='find_2023', deps=[models_2023_tested], description='Great Expectations business rules on the 2023 marts.')
def quality_gate_2023(context):
    quality_gate(context, 'quality_gate_2023', '2023')


@asset(group_name='find_2023', deps=[quality_gate_2023], description='The 2023 answer equals the results the store was built on (contract tables g01-g05).')
def answer_2023_reconciled(context):
    reconcile(context, 'answer_2023_reconciled', '2023')


# ---------------------------------------------------------------- stage 2: VERIFY, on the Amazon 2026 snapshot

@asset(group_name='verify_2026', deps=[answer_2023_reconciled],
       description='Amazon 2026: Keepa API snapshot for the groups the 2023 answer points to. Cached responses are not fetched again.')
def amazon_2026_snapshot(context):
    out = run([PYTHON, 'ingestion/fetch_keepa_snapshot.py'])
    record(context, 'amazon_2026_snapshot', {'log': out.strip().splitlines()[-3:]})


@asset(group_name='verify_2026', deps=[amazon_2026_snapshot],
       description='Label the 2026 products with the same play-pattern rules as 2023, write two tables for Meltano.')
def snapshot_labelled(context):
    run([PYTHON, 'enrichment/build_keepa_tables.py'])
    record(context, 'snapshot_labelled', json.loads((REPO / 'docs/evidence/enrichment/keepa_summary.json').read_text()))


@asset(group_name='verify_2026', deps=[snapshot_labelled], description='Meltano: the two snapshot tables to BigQuery (append-only raw).')
def snapshot_loaded(context):
    meltano_load(context, 'snapshot_loaded', 'tap-duckdb-snapshot-2026')


@asset(group_name='verify_2026', deps=[snapshot_loaded], description='dbt build of the models based on the 2026 snapshot, and their tests.')
def models_2026_tested(context):
    dbt_build(context, 'models_2026_tested', ['--select', TAG_2026])


@asset(group_name='verify_2026', deps=[models_2026_tested], description='Great Expectations business rules on the 2026 marts.')
def quality_gate_2026(context):
    quality_gate(context, 'quality_gate_2026', '2026')


@asset(group_name='verify_2026', deps=[quality_gate_2026], description='All ten contract tables, 2023 and 2026, equal the results the store was built on.')
def answer_2026_reconciled(context):
    reconcile(context, 'answer_2026_reconciled', 'all')


FIND = [raw_ingestion, flower_enrichment, labels_loaded, models_2023_tested, quality_gate_2023, answer_2023_reconciled]
VERIFY = [amazon_2026_snapshot, snapshot_labelled, snapshot_loaded, models_2026_tested, quality_gate_2026, answer_2026_reconciled]
ASSETS = FIND + VERIFY
find_job = define_asset_job('find_2023', selection=AssetSelection.groups('find_2023'))
verify_job = define_asset_job('verify_2026', selection=AssetSelection.groups('verify_2026'))
pipeline_job = define_asset_job('project2_flower_pipeline', selection=AssetSelection.all())
weekly_schedule = ScheduleDefinition(job=pipeline_job, cron_schedule='0 6 * * 1', execution_timezone='Asia/Singapore',
                                     name='weekly_flower_pipeline')
defs = Definitions(assets=ASSETS, jobs=[find_job, verify_job, pipeline_job], schedules=[weekly_schedule])
