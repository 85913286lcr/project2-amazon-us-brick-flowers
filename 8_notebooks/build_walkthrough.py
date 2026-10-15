"""Write 00_pipeline_walkthrough.ipynb: open every layer of the pipeline in order and show what is in it.

The DuckDB file (4.7 GB) and the raw data cannot go on GitHub, so this notebook is the record of what they contain.
Run it, then execute it so the outputs are saved:
  python 8_notebooks/build_walkthrough.py
  python -m nbconvert --to notebook --execute --inplace 8_notebooks/00_pipeline_walkthrough.ipynb
"""
from pathlib import Path

import nbformat as nbf

OUT = Path(__file__).resolve().parent / '00_pipeline_walkthrough.ipynb'
nb = nbf.v4.new_notebook()
md = lambda s: nb.cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: nb.cells.append(nbf.v4.new_code_cell(s.strip()))

md("""
# Pipeline walkthrough: every step, opened

This notebook opens each layer of the pipeline in the order the data flows through it and shows what is inside.
The DuckDB file (4.7 GB) and the raw files are not in the repository, so the saved outputs here are the record of
what they contain. Nothing is written: DuckDB is opened read-only and BigQuery is only queried.

| Step | Folder | Opened here |
|---|---|---|
| 1 Ingest | `1_ingestion/` | DuckDB: the two raw tables, their columns and sample rows |
| 2 Label | `2_enrichment/` | DuckDB: the flower labels, review themes, wish sentences and the 2026 snapshot |
| 3 Load | `3_meltano/` | BigQuery `project2_raw`: the same tables, row counts next to DuckDB |
| 4 Transform | `4_dbt/` | BigQuery staging, analytics (star schema) and marts |
| 5 Test | `4_dbt/tests/`, `5_quality/` | dbt test results and Great Expectations rules |
| 6 Reconcile | `6_reconcile/` | the warehouse results compared with the frozen contract |
| 7 Orchestrate | `7_orchestration/` | the last Dagster run, step by step |
| 8 Analyse | `8_notebooks/` | continues in `flower_analysis.ipynb` |
""")

code("""
import json
import os
import re
import warnings
from pathlib import Path

import duckdb
import pandas as pd
from IPython.display import Image, Markdown, display
from sqlalchemy import create_engine, text

warnings.filterwarnings('ignore')
pd.set_option('display.max_colwidth', 60)
pd.set_option('display.width', 200)

REPO = Path.cwd().parent if Path.cwd().name == '8_notebooks' else Path.cwd()
EVIDENCE = REPO / 'docs' / 'evidence'
duck = duckdb.connect(str(REPO / 'duckdb' / 'giftfinder.duckdb'), read_only=True)

PROJECT = os.environ.get('PROJECT2_GCP_PROJECT', 'united-firefly-509307-h9')
engine = create_engine(f'bigquery://{PROJECT}', location='US')

def bq(sql):
    with engine.connect() as con:
        return pd.read_sql_query(text(sql), con)

def dk(sql):
    return duck.sql(sql).df()

print('DuckDB', duckdb.__version__, '· duckdb/giftfinder.duckdb (read-only)')
print('BigQuery project', PROJECT)
""")

md("""
## 1 · Ingest: the raw files in DuckDB
`1_ingestion/ingest_amazon_to_duckdb.py` reads the two `.jsonl.gz` files (Amazon Reviews 2023, Toys & Games) and
keeps 10 product fields and 9 review fields. Every table in the DuckDB file:
""")
code("""
tables = dk("select table_name, estimated_size as approx_rows, column_count from duckdb_tables() order by table_name")
tables['rows'] = [duck.sql(f'select count(*) from {t}').fetchone()[0] for t in tables.table_name]
tables.drop(columns='approx_rows')
""")
md("Columns of the two raw tables:")
code("""
for t in ['amazon_products_raw', 'amazon_reviews_raw']:
    display(Markdown(f'**{t}**'))
    display(dk(f'describe {t}')[['column_name', 'column_type']].T)
""")
md("Three rows of each:")
code("""
dk('''select parent_asin, left(title, 50) as title, main_category, categories[1:2] as categories,
             average_rating, rating_number, price, store
      from amazon_products_raw where price is not null limit 3''')
""")
code("""
dk('''select parent_asin, asin, rating, left(title, 30) as title, left(text, 60) as text,
             left(user_id, 12) as user_id, epoch_ms(timestamp) as written_at, helpful_vote, verified_purchase
      from amazon_reviews_raw limit 3''')
""")
md("The checks the ingest script runs (empty and duplicate keys), recomputed here:")
code("""
dk('''
select 'amazon_products_raw' as table_name, count(*) as rows,
       count(*) filter (where parent_asin is null or parent_asin = '') as empty_keys,
       count(*) - count(distinct parent_asin) as duplicate_keys
from amazon_products_raw
union all
select 'amazon_reviews_raw', count(*),
       count(*) filter (where parent_asin is null or parent_asin = '' or user_id is null), cast(null as bigint)
from amazon_reviews_raw
''')
""")

md("""
## 2 · Label: flower toys, review themes, wishes
`2_enrichment/build_flower_tables.py` applies the flower rules (Python regex, which BigQuery's RE2 cannot run)
and writes three tables back into DuckDB for Meltano to load.
""")
code("""
dk('''select relevance_tier, count(*) as products, count(distinct primary_pattern) as play_patterns
      from flower_product_labels group by 1 order by 1''')
""")
code("""
dk('''select primary_pattern as play_pattern, count(*) as products, count(distinct brand) as brands
      from flower_product_labels group by 1 order by products desc limit 8''')
""")
code("""
display(dk('''select * from flower_review_themes
              where parent_asin in (select parent_asin from flower_product_labels where primary_pattern like 'Brick flower%') limit 4'''))
display(dk('select sentence_id, parent_asin, rating, left(sentence, 80) as sentence, need from flower_wish_needs where need <> \\'Uncategorised\\' limit 3'))
""")
md("""
**2b · Amazon 2026.** `1_ingestion/fetch_keepa_snapshot.py` reads the saved Keepa responses (7 Oct 2026) and
`2_enrichment/build_keepa_tables.py` applies the same play-pattern rules:
""")
code("""
dk('''select keepa_group, count(*) as products, sum(monthly_sold_now) as units_per_month_now,
             sum(reviews_added_2025) as ratings_added_2025, sum(reviews_added_2026) as ratings_added_2026
      from keepa_products group by 1 order by products desc''')
""")

md("""
## 3 · Load: DuckDB to BigQuery with Meltano
`3_meltano/meltano.yml` loads the DuckDB tables into `project2_raw` (prefix `main_`). Raw is append-only, so the
small tables hold one batch per load and staging reads the newest one (macro `latest_load`). Meltano stores each row as
JSON in a `data` column, with the batch time in `_sdc_sync_started_at`. The newest batch must equal DuckDB.
""")
code("""
BATCH = "safe_cast(json_value(data, '$._sdc_sync_started_at') as int64)"
pairs = {'amazon_products_raw': False, 'amazon_reviews_raw': False, 'flower_product_labels': True,
         'flower_review_themes': True, 'flower_wish_needs': True, 'keepa_products': True, 'keepa_finder_counts': True}
rows = []
for t, batched in pairs.items():
    if batched:
        r = bq(f'''select count(*) as all_rows, count(distinct {BATCH}) as batches,
                          countif({BATCH} = (select max({BATCH}) from project2_raw.main_{t})) as newest_batch
                   from project2_raw.main_{t}''').iloc[0]
    else:
        r = bq(f'select count(*) as all_rows, 1 as batches, count(*) as newest_batch from project2_raw.main_{t}').iloc[0]
    rows.append({'table': t, 'duckdb_rows': duck.sql(f'select count(*) from {t}').fetchone()[0],
                 'bigquery_all_rows': r.all_rows, 'batches': r.batches, 'bigquery_newest_batch': r.newest_batch})
load = pd.DataFrame(rows)
load['match'] = load.duckdb_rows == load.bigquery_newest_batch
load
""")

md("""
## 4 · Transform: dbt builds staging, the star schema and the marts
Every model of the dbt project, by layer. Staging models are views, so BigQuery reports no row count for them.
""")
code("""
models = sorted(p.stem for p in (REPO / '4_dbt' / 'models').rglob('*.sql')) + \\
         sorted(p.stem for p in (REPO / '4_dbt' / 'seeds').glob('*.csv'))
layers = []
for ds in ['project2_staging', 'project2_analytics', 'project2_marts']:
    t = bq(f'select table_id as model, if(type = 2, "view", "table") as kind, row_count from {ds}.__TABLES__')
    t.insert(0, 'dataset', ds)
    layers.append(t[t.model.isin(models)])
layers = pd.concat(layers).sort_values(['dataset', 'model']).reset_index(drop=True)
layers.loc[layers.kind == "view", "row_count"] = None
layers
""")
md("The star schema: the review fact keeps every raw review, and each foreign key finds its dimension.")
code("""
bq('''
select 'fact_reviews rows = raw reviews' as check_name,
       (select count(*) from project2_analytics.fact_reviews) = (select count(*) from project2_raw.main_amazon_reviews_raw) as ok
union all
select 'dim_product rows = raw products',
       (select count(*) from project2_analytics.dim_product) = (select count(*) from project2_raw.main_amazon_products_raw)
union all
select 'every fact_reviews product is in dim_product',
       not exists (select 1 from project2_analytics.fact_reviews f
                   left join project2_analytics.dim_product p using (parent_asin) where p.parent_asin is null)
union all
select 'every fact_reviews customer is in dim_customer',
       not exists (select 1 from project2_analytics.fact_reviews f
                   left join project2_analytics.dim_customer c using (user_id) where c.user_id is null)
union all
select 'every fact_flower_reviews product is in dim_flower_product',
       not exists (select 1 from project2_analytics.fact_flower_reviews f
                   left join project2_analytics.dim_flower_product p using (parent_asin) where p.parent_asin is null)
''')
""")
code("""
bq('''select * from project2_analytics.fact_flower_reviews
      where play_pattern like 'Brick flower%' and review_year = 2023 order by review_datetime limit 3''')
""")

md("""
## 5 · Test: dbt tests and Great Expectations
dbt runs its tests during `dbt build` (log in `docs/evidence/dbt/`). Great Expectations then checks business rules on
the marts (`5_quality/gx_validate_flower_marts.py`).
""")
code("""
for f in sorted((EVIDENCE / 'dbt').glob('*.txt')):
    done = [l for l in f.read_text().splitlines() if 'Done. PASS=' in l]
    warns = re.findall(r'WARN (\\d+) (known_issue_\\w+)', f.read_text())
    print(f.name, '·', done[-1].split('Done. ')[1] if done else 'no summary')
    for n, name in warns:
        print(f'   warn  {name}: {int(n):,} rows (a known problem in the source, see docs/data_quality_notes.md)')
""")
code("""
for scope in ['2023', '2026']:
    display(Markdown((EVIDENCE / 'great_expectations' / f'validation_summary_{scope}.md').read_text()))
""")

md("""
## 6 · Reconcile: the warehouse reproduces the frozen results
`6_reconcile/` exports the marts and compares them, row by row, with `contract/golden/` (the results the store was
built on). A difference fails the run.
""")
code("""
print((EVIDENCE / 'contract' / 'verify_all.txt').read_text())
""")

md("""
## 7 · Orchestrate: the last Dagster run
`7_orchestration/definitions.py` runs steps 1 to 6 for 2023 (FIND), then again for 2026 (VERIFY).
""")
code("""
run = json.loads((EVIDENCE / 'dagster' / 'run_result.json').read_text())
print('run', run['run_id'], '·', run['finished_utc'], '·', run['run_result'])
print('schedule', run['schedule'])
pd.DataFrame([{'stage': stage, 'step': s, 'status': run['stage_statuses'][s]}
              for stage, steps in run['stages'].items() for s in steps])
""")
code("""
for png in sorted((REPO / 'docs' / 'screenshots').glob('dagster_*.png')):
    display(Markdown(f'`{png.name}`'), Image(filename=str(png), width=900))
""")

md("""
## 8 · Analyse
The analysis (monthly trend, top products, customer segments, Amazon 2026) continues in
[`flower_analysis.ipynb`](flower_analysis.ipynb), on the marts opened in step 4.
""")
code("""
duck.close()
""")

nb.metadata['kernelspec'] = {'name': 'project2-analysis', 'display_name': 'Project 2 analysis', 'language': 'python'}
nbf.write(nb, str(OUT))
print('wrote', OUT)
