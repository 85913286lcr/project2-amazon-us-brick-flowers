"""Flower enrichment: label flower toys and their reviews, then hand three tables to the pipeline.

Why this is a Python step and not dbt SQL: the classifier uses regular-expression look-aheads and
per-sentence parsing, which BigQuery's RE2 engine cannot express. The rules therefore run once here,
and everything downstream (star schema, marts, tests) is built by dbt on the loaded tables.

Steps
  1. flower_identify        raw product metadata  -> flower relevance tiers
  2. flower_patterns        flower products       -> play pattern (how the toy is used)
  3. flower_review_evidence raw reviews           -> theme tags + wish sentences
  4. write three tables into the pipeline DuckDB for Meltano:
       flower_product_labels   1 row = 1 flower product
       flower_review_themes    1 row = 1 review x theme it mentions
       flower_wish_needs       1 row = 1 wish sentence x need category
     (raw stays append-only; dbt staging keeps the newest load via Singer's _sdc_sync_started_at)
  5. write the dbt seeds (theme codebook, play patterns) from the same constants
  6. compare the labels with the frozen contract (contract/golden/g01_flower_products_labels.csv)

Run:  python enrichment/build_flower_tables.py
"""
import csv
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flower_identify  # noqa: E402
import flower_patterns  # noqa: E402
import flower_review_evidence  # noqa: E402
from paths import CONTRACT, EVIDENCE, PIPELINE_DB, REPO, WORK_DB  # noqa: E402

SEEDS = REPO / 'project2_dbt' / 'seeds'
# Play pattern -> DIY family: does the buyer build or make the flower?
DIY_FAMILY = {
    'Brick flower bouquets & bonsai (adult display)': 'DIY: adult brick building',
    'Brick scenes (flower shop / garden)': 'DIY: adult brick building',
    'Brick flower accessories (vase / lights / display)': 'DIY: adult brick building',
    'Toddler flower-garden stacking sets': 'DIY: toddler stacking',
    'Craft bouquets & paper flowers': 'DIY: crafts', 'Paint & decorate crafts': 'DIY: crafts',
    'Flower crown & jewellery crafts': 'DIY: crafts', 'Flower pressing': 'DIY: crafts', '3D wooden & crystal models': 'DIY: crafts',
    'Planting & science kits': 'DIY: planting',
    'Flower-image puzzles & cards': 'Puzzles & cards (flower is only the image)'}
NON_DIY = 'Not DIY (plush, decor, electronic, miniature, pretend)'


def run_classifiers():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    flower_identify.main()
    flower_patterns.main()
    flower_review_evidence.main()


def export_tables():
    work = duckdb.connect(str(WORK_DB), read_only=True)
    labels = work.execute("""select parent_asin, tier as relevance_tier, relevance, primary_pattern, patterns, brand
                             from flower_core order by parent_asin""").df()
    tag_cols = [c[0] for c in work.execute('describe review_tags').fetchall() if '|' in c[0]]
    tags = work.execute("""select row_number() over (order by parent_asin, ts, rating) as review_row_id, * from review_tags""").df()
    long = tags.melt(id_vars=['review_row_id', 'parent_asin', 'rating'], value_vars=tag_cols, var_name='tag', value_name='hit')
    long = long[long.hit].drop(columns='hit')
    long[['theme_group', 'theme']] = long.tag.str.split('|', n=1, expand=True)
    themes = long[['review_row_id', 'parent_asin', 'rating', 'theme_group', 'theme']].sort_values(['review_row_id', 'theme_group', 'theme'])
    wish = work.execute("select parent_asin, rating, epoch_ms(ts) as review_ts_ms, sentence, needs from wish_sentences").df()
    wish.insert(0, 'sentence_id', range(1, len(wish) + 1))
    needs = wish.assign(need=wish.needs.str.split('|')).explode('need').drop(columns='needs')
    work.close()

    # Raw is append-only in BigQuery: Singer stamps every load with _sdc_sync_started_at and dbt staging keeps the newest.
    pipe = duckdb.connect(str(PIPELINE_DB))
    for name, frame in [('flower_product_labels', labels), ('flower_review_themes', themes), ('flower_wish_needs', needs)]:
        pipe.register('frame', frame)
        pipe.execute(f'create or replace table {name} as select * from frame')
        pipe.unregister('frame')
    counts = {t: pipe.execute(f'select count(*) from {t}').fetchone()[0] for t in ('flower_product_labels', 'flower_review_themes', 'flower_wish_needs')}
    counts['reviews_tagged'] = int(tags.review_row_id.nunique())
    counts['wish_sentences'] = int(wish.sentence_id.nunique())
    pipe.close()
    return labels, tag_cols, counts


def write_seeds(tag_cols):
    SEEDS.mkdir(parents=True, exist_ok=True)
    with open(SEEDS / 'flower_theme_codebook.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['theme_group', 'theme'])
        w.writerows(t.split('|', 1) for t in tag_cols)
    patterns = [name for name, _ in flower_patterns.PATTERNS] + ['Other / unclassified']
    with open(SEEDS / 'flower_play_patterns.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['play_pattern', 'diy_family', 'is_diy'])
        for p in patterns:
            fam = DIY_FAMILY.get(p, NON_DIY)
            w.writerow([p, fam, str(fam.startswith('DIY')).lower()])


def check_contract(labels):
    golden = CONTRACT / 'golden' / 'g01_flower_products_labels.csv'
    if not golden.exists():
        return 'no contract found - skipped'
    g = pd.read_csv(golden).rename(columns={'tier': 'relevance_tier'}).sort_values('parent_asin').reset_index(drop=True)
    c = labels.sort_values('parent_asin').reset_index(drop=True)[g.columns]
    same = len(g) == len(c) and all((g[col].fillna('') == c[col].fillna('')).all() for col in g.columns)
    return 'PASS' if same else 'FAIL'


def main():
    run_classifiers()
    labels, tag_cols, counts = export_tables()
    write_seeds(tag_cols)
    counts['contract_check_labels'] = check_contract(labels)
    (EVIDENCE / 'enrichment_summary.json').write_text(json.dumps(counts, ensure_ascii=False, indent=2))
    print(json.dumps(counts, ensure_ascii=False))
    if counts['contract_check_labels'] == 'FAIL':
        raise SystemExit('Flower labels differ from the frozen contract')


if __name__ == '__main__':
    main()
