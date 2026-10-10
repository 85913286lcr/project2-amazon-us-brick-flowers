"""Dagster orchestration: seven assets that run the pipeline end to end, in dependency order.

    raw_ingestion -> flower_enrichment -> amazon_2026_snapshot -> tables_loaded
                  -> warehouse_models_tested -> business_quality_gate -> contract_reconciled

Each asset runs the real step (it does not read a saved result), fails loudly, and records what it did
under docs/evidence/dagster/. The weekly schedule refreshes the small tables, rebuilds the warehouse and
re-runs every quality check. The Keepa step only calls the API for responses that are not cached yet.

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


@asset(description='Verify the two raw Amazon tables in DuckDB: row counts, null keys, duplicate product keys.')
def raw_ingestion(context):
    run([PYTHON, 'ingestion/ingest_amazon_to_duckdb.py'])
    record(context, 'raw_ingestion', json.loads((REPO / 'docs/evidence/ingestion/ingestion_verify.json').read_text()))


@asset(deps=[raw_ingestion], description='Label flower toys and their reviews (Python rules), write three tables for Meltano.')
def flower_enrichment(context):
    run([PYTHON, 'enrichment/build_flower_tables.py'])
    record(context, 'flower_enrichment', json.loads((REPO / 'docs/evidence/enrichment/enrichment_summary.json').read_text()))


@asset(deps=[flower_enrichment], description='Amazon 2026: Keepa API snapshot (cache first), parsed into two tables for Meltano.')
def amazon_2026_snapshot(context):
    run([PYTHON, 'ingestion/fetch_keepa_snapshot.py'])
    run([PYTHON, 'enrichment/build_keepa_tables.py'])
    record(context, 'amazon_2026_snapshot', json.loads((REPO / 'docs/evidence/enrichment/keepa_summary.json').read_text()))


@asset(deps=[amazon_2026_snapshot], description='Meltano: tap-duckdb -> target-bigquery for the five small tables (append-only raw).')
def tables_loaded(context):
    out = run([MELTANO, 'run', '--refresh-catalog', 'tap-duckdb-refresh', 'target-bigquery'], cwd=REPO / 'meltano')
    records = re.search(r'\((\d+) schemas, (\d+) records', out)
    if 'Run completed' not in out or not records:
        raise Failure('Meltano did not report a completed run')
    record(context, 'tables_loaded', {'streams': int(records.group(1)), 'records_sent': int(records.group(2))})


@asset(deps=[tables_loaded], description='dbt build --full-refresh: seeds, staging, star schema, marts and every data test.')
def warehouse_models_tested(context):
    out = re.sub(r'\x1b\[[0-9;]*m', '', run([DBT, 'build', '--full-refresh', '--no-use-colors'], cwd=REPO / 'project2_dbt'))
    summary = re.search(r'Done\. PASS=(\d+) WARN=(\d+) ERROR=(\d+) SKIP=(\d+)', out)
    if not summary or int(summary.group(3)) or int(summary.group(4)):
        raise Failure('dbt build did not finish cleanly')
    (EVIDENCE.parent / 'dbt').mkdir(parents=True, exist_ok=True)
    (EVIDENCE.parent / 'dbt' / 'dbt_build_latest.txt').write_text(out)
    tests = re.search(r'(\d+) data tests', out)
    known = re.findall(r'WARN (\d+) (known_issue_\w+)', out)
    record(context, 'warehouse_models_tested', {'passed': int(summary.group(1)), 'warnings': int(summary.group(2)), 'errors': 0,
                                                'known_issues': {name: int(n) for n, name in known},
                                                'data_tests': int(tests.group(1)) if tests else None})


@asset(deps=[warehouse_models_tested], description='Great Expectations business rules on the decision marts.')
def business_quality_gate(context):
    run([PYTHON_QUALITY, 'quality/gx_validate_flower_marts.py'])
    report = json.loads((REPO / 'docs/evidence/great_expectations/validation_results.json').read_text())
    if report['overall_result'] != 'PASS':
        raise Failure('Great Expectations gate failed')
    record(context, 'business_quality_gate', {'expectations': report['expectation_count'], 'result': report['overall_result'],
                                              'timestamp_utc': report['timestamp_utc']})


@asset(deps=[business_quality_gate], description='Export the marts and compare them with the frozen contract the store was built on.')
def contract_reconciled(context):
    export = REPO / 'docs/evidence/contract/export'
    run([PYTHON_QUALITY, 'scripts/export_marts_for_contract.py', export])
    out = run([PYTHON_QUALITY, 'scripts/verify_against_contract.py', export])
    (REPO / 'docs/evidence/contract/verify.txt').write_text(out)
    if 'RESULT PASS' not in out:
        raise Failure('The warehouse no longer reproduces the contract')
    record(context, 'contract_reconciled', {'result': 'PASS', 'tables_matched': out.count('\nOK ') + out.startswith('OK '),
                                            'scope': 'Amazon 2023 and Amazon 2026 (g01-g10)'})


ASSETS = [raw_ingestion, flower_enrichment, amazon_2026_snapshot, tables_loaded, warehouse_models_tested, business_quality_gate, contract_reconciled]
pipeline_job = define_asset_job('project2_flower_pipeline', selection=AssetSelection.all())
weekly_schedule = ScheduleDefinition(job=pipeline_job, cron_schedule='0 6 * * 1', execution_timezone='Asia/Singapore',
                                     name='weekly_flower_pipeline')
defs = Definitions(assets=ASSETS, jobs=[pipeline_job], schedules=[weekly_schedule])
