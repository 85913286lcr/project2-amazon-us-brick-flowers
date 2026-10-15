"""Ingestion: two raw Amazon Reviews 2023 files -> two tables in a local DuckDB file.

Three steps, each printed so the run can be audited:
  1. Preview   - 3 rows and the detected schema of each file (auto-detected types can be wrong)
  2. Load      - keep 10 product fields and 9 review fields; straight from .jsonl.gz into tables
  3. Verify    - row counts, null keys, duplicate product keys

Why DuckDB: it reads the compressed files directly, has no size cap (the 16M reviews do not fit a free
hosted Postgres), needs no server, and lets the checks be written in SQL.

Usage
  python 1_ingestion/ingest_amazon_to_duckdb.py            # verify the existing tables (default, read-only)
  python 1_ingestion/ingest_amazon_to_duckdb.py --rebuild  # re-create both tables from the raw files
"""
import argparse
import json
import os
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]
RAW_DIR = Path(os.environ.get('PROJECT2_RAW_DIR', REPO.parents[1] / 'Data' / 'Raw'))
DB = REPO / 'duckdb' / 'giftfinder.duckdb'
EVIDENCE = REPO / 'docs' / 'evidence' / 'ingestion'
EXPECTED = {'amazon_products_raw': 890_874, 'amazon_reviews_raw': 16_260_406}

SOURCES = {
    'amazon_products_raw': {
        'file': 'meta_Toys_and_Games.jsonl.gz',
        'columns': {'parent_asin': 'VARCHAR', 'title': 'VARCHAR', 'main_category': 'VARCHAR', 'categories': 'VARCHAR[]',
                    'average_rating': 'DOUBLE', 'rating_number': 'BIGINT', 'price': 'VARCHAR', 'store': 'VARCHAR',
                    'features': 'VARCHAR[]', 'description': 'VARCHAR[]'},
        # price arrives as text ("12.99", "None", "—"); anything that is not a number becomes NULL
        'select': """parent_asin, title, main_category, categories, average_rating, rating_number,
                     try_cast(price as double) as price, store, features, description""",
    },
    'amazon_reviews_raw': {
        'file': 'Toys_and_Games.jsonl.gz',
        'columns': {'rating': 'DOUBLE', 'title': 'VARCHAR', 'text': 'VARCHAR', 'asin': 'VARCHAR', 'parent_asin': 'VARCHAR',
                    'user_id': 'VARCHAR', 'timestamp': 'BIGINT', 'helpful_vote': 'BIGINT', 'verified_purchase': 'BOOLEAN'},
        'select': 'rating, title, text, asin, parent_asin, user_id, "timestamp", helpful_vote, verified_purchase',
    },
}


def reader(spec):
    cols = ', '.join(f"'{k}': '{v}'" for k, v in spec['columns'].items())
    return f"read_json('{RAW_DIR / spec['file']}', format='newline_delimited', columns={{{cols}}})"


def preview(con):
    for table, spec in SOURCES.items():
        path = RAW_DIR / spec['file']
        print(f'\n[1 preview] {path.name}')
        print(con.execute(f"describe select * from read_json_auto('{path}', sample_size=1000)").df()[['column_name', 'column_type']].to_string(index=False))
        print(con.execute(f"select {spec['select']} from {reader(spec)} limit 3").df().to_string(index=False, max_colwidth=40))


def load(con):
    for table, spec in SOURCES.items():
        print(f'\n[2 load] {table}')
        con.execute(f"create or replace table {table} as select {spec['select']} from {reader(spec)}")


def verify(con):
    report = {}
    for table, expected in EXPECTED.items():
        key = 'parent_asin'
        rows, null_keys = con.execute(f'select count(*), count(*) filter (where {key} is null) from {table}').fetchone()
        report[table] = {'rows': rows, 'expected_rows': expected, 'null_keys': null_keys}
    distinct = con.execute('select count(distinct parent_asin) from amazon_products_raw').fetchone()[0]
    report['amazon_products_raw']['duplicate_keys'] = report['amazon_products_raw']['rows'] - distinct
    ok = all(v['rows'] == v['expected_rows'] and v['null_keys'] == 0 for v in report.values()) and report['amazon_products_raw']['duplicate_keys'] == 0
    report['result'] = 'PASS' if ok else 'FAIL'
    print('\n[3 verify]', json.dumps(report, indent=2))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / 'ingestion_verify.json').write_text(json.dumps(report, indent=2))
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rebuild', action='store_true', help='re-create the tables from the raw files')
    args = parser.parse_args()
    con = duckdb.connect(str(DB), read_only=not args.rebuild)
    if args.rebuild:
        preview(con)
        load(con)
    if not verify(con):
        raise SystemExit('Ingestion verification failed')


if __name__ == '__main__':
    main()
