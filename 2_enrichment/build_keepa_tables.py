"""Turn the cached Keepa API responses (Amazon 2026) into two tables for the pipeline.

    keepa_products        1 row = 1 product family per source (group / new / cohort)
    keepa_finder_counts   1 row = 1 group: how many products sell 100+ a month

Each product gets the same play-pattern rules as the 2023 data, so 2023 and 2026 are compared like for like.
The numbers taken from the API history:
  reviews_added_<year>  rating count gained between 1 Jan and 7 Oct of that year (same window every year)
  monthly_sold_now / monthly_sold_1y_ago, sales rank now and at the end of each window

Three sources of products:
  group   current top sellers of each group (Product Finder, sorted by sales rank)
  new     products first listed since 2024 that sell 50+ a month
  cohort  the 2023 top products of each group, followed into 2026

Aggregation (verdict per group, DIY comparison, new product forms) is done later in dbt.
Run: python 2_enrichment/build_keepa_tables.py
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flower_identify as identify  # noqa: E402
import flower_patterns as patterns  # noqa: E402
from keepa_groups import COUNT_QUERIES, GROUP_BY_ID, OTHER_GROUP, PATTERN_TO_GROUP  # noqa: E402
from paths import EVIDENCE, KEEPA_DIR, PIPELINE_DB  # noqa: E402

SNAPSHOT = datetime(2026, 10, 7, tzinfo=timezone.utc)      # the day the API was called; windows end on this day
KEEPA_EPOCH_MIN = 21564000

# Finder title search also returns garden decor and miniature kits: not toys in our sense.
NON_TOY = r"wind spinner|windmill|whirligig|yard|garden decor|stake light|pathway|lawn|patio|book nook|dollhouse|terrarium|crystal growing|stepping stone|centerpieces"
# Products that the 2023 rules put in the wrong group for a 2026 title.
REROUTE = [('G5', r"paint (&|and) plant|growing kit|planting|flower seeds|greenhouse"),
           ('G4', r"fabric flower|bouquet maker|flower making kit|flower bouquet making|poke|press(ing)? kit"),
           ('G1', r"(build|brick|block).*(cross|religious|adults?|botanical)")]

# Product forms among launches since 2024. First match wins.
FORM_NOISE = r"balloon|napkin|tablecloth|mahjong|plates|baby shower|banner|garland|cake topper|tarot|earrings|nap mat|locker|hot wheels|deck box|boulder|tamagotchi|kaleidoscope|tea set|dice"
BRICK = r'build|brick|block'
FORMS = [
    ('New LEGO flower sets', lambda t, brand: brand.lower() == 'lego'),
    ('Flower advent calendars', lambda t, brand: 'advent' in t),
    ('Gothic & dark-romance brick flowers', lambda t, brand: bool(re.search(r'gothic|skull|black (rose|dahlia)|corpse|halloween|wednesday|raven', t)) and bool(re.search(BRICK, t))),
    ('Bouquet-format collectibles (blind box / licensed)', lambda t, brand: bool(re.search(r'mini brands|squishmallow|funko|doorables|capsule|blind box|mystery', t))),
    ('Poke-art, no-glue bouquet kits', lambda t, brand: bool(re.search(r'poke|mess.free|no.glue', t))),
    ('Fabric bouquet & flower-shop kits for kids', lambda t, brand: bool(re.search(r'fabric flower|flower market|flowers market|build your (own )?flower bouquet|bouquet maker', t))),
    ('Flower press kits', lambda t, brand: bool(re.search(r'press', t))),
    ('Single-stem & mini flower brick series', lambda t, brand: bool(re.search(BRICK, t)) and bool(re.search(r'mini|single|series|3 ?pack|bloom up|basket stuffer', t))),
    ('Other brick bouquets & bonsai', lambda t, brand: bool(re.search(BRICK, t))),
    ('Crochet emotional-support succulents', lambda t, brand: bool(re.search(r'crochet|affirmation|emotional support|positive', t))),
    ('Other flower & succulent plush', lambda t, brand: bool(re.search(r'plush|stuffed|pillow', t))),
    ('Other crafts', lambda t, brand: bool(re.search(r'craft|kit|diy|dough|clay', t))),
]


def keepa_minute(dt):
    return int(dt.timestamp() // 60) - KEEPA_EPOCH_MIN


def from_keepa_minute(m):
    return datetime.fromtimestamp((m + KEEPA_EPOCH_MIN) * 60, timezone.utc)


def pairs(flat):
    flat = flat or []
    return list(zip(flat[::2], flat[1::2]))


def value_at(history, minute):
    """Last valid value at or before a Keepa minute (history is time-ordered; -1 means no data)."""
    value = None
    for t, x in history:
        if t > minute:
            break
        if x is not None and x >= 0:
            value = x
    return value


def play_pattern(title):
    labels = [name for name, rule in patterns.PATTERNS if rule not in ('__IMAGE__', '__PLUSH__') and re.search(rule, title)]
    if patterns.PLUSH_RE.search(title) and not patterns.CHARACTER_RE.search(title):
        labels.insert(0, 'Flower plush & pillows')
    if identify.IMAGE_RE.search(title):
        labels.insert(0, 'Flower-image puzzles & cards')
    return labels[0] if labels else 'Other / unclassified'


def group_of(pattern, title, brand):
    group = PATTERN_TO_GROUP.get(pattern)
    if group == 'G3' and re.search(r"\blego\b|compatible|adults?|women|minidolls?|gothic", title):
        group = 'G1'                       # licensed or adult brick flowers match the toddler rule by wording
    if group == 'G1' and brand.lower() == 'lego':
        group = 'G2'
    if re.search(NON_TOY, title):
        return None
    if group in ('G3', 'G4', 'G7'):
        for target, rule in REROUTE:
            if target != group and re.search(rule, title):
                group = target
                break
    if group == 'G1' and brand.lower() == 'lego':
        group = 'G2'
    return group


def product_row(source, asin, p, windows, cohort_group):
    title = p['title']
    t = title.lower()
    brand = (p.get('brand') or '').strip()
    pattern = play_pattern(t)
    if source == 'cohort':                 # cohort keeps its 2023 group
        group, is_flower = cohort_group[asin], True
    else:
        group, is_flower = group_of(pattern, t, brand), identify.flower_in(t) or bool(identify.PLANT_RE.search(t))
    csv = p.get('csv') or []
    rating_counts = pairs(csv[17]) if len(csv) > 17 else []
    ranks = pairs(csv[3]) if len(csv) > 3 else []
    sold_history = pairs(p.get('monthlySoldHistory'))
    current = (p.get('stats') or {}).get('current') or []
    stat = lambda i: current[i] if len(current) > i and current[i] and current[i] > 0 else None
    price = stat(18) or stat(1)            # buy box incl. shipping, else new price (cents)
    row = {'source': source, 'asin': asin, 'parent_asin': p.get('parentAsin') or asin, 'title': title, 'brand': brand,
           'is_flower': is_flower, 'primary_pattern': pattern, 'keepa_group': GROUP_BY_ID.get(group, OTHER_GROUP),
           'listed_since': from_keepa_minute(p['listedSince']).date().isoformat() if p.get('listedSince', 0) > 0 else None,
           'monthly_sold_now': p.get('monthlySold'),
           'monthly_sold_1y_ago': value_at(sold_history, keepa_minute(SNAPSHOT.replace(year=SNAPSHOT.year - 1))),
           'rating_now': stat(16) / 10 if stat(16) else None, 'rating_count_now': stat(17),
           'price_now': price / 100 if price else None, 'sales_rank_now': stat(3)}
    for year, (start, end) in windows.items():
        before, after = value_at(rating_counts, start), value_at(rating_counts, end)
        if before is not None and after is not None:
            added = max(0, after - before)
        else:                              # listed inside the window: everything it has was added this year
            added = after if after is not None and p.get('listedSince', 0) >= start else None
        row[f'reviews_added_{year}'] = added
        row[f'rank_{year}'] = value_at(ranks, end)
    return row


def new_form(title, brand):
    return next((name for name, rule in FORMS if rule(title, brand)), 'Other')


def main():
    plan = json.loads((KEEPA_DIR / 'plan.json').read_text())
    windows = {y: (keepa_minute(datetime(y, 1, 1, tzinfo=timezone.utc)), keepa_minute(SNAPSHOT.replace(year=y))) for y in (2023, 2024, 2025, 2026)}
    cohort_group = {asin: gid for gid, asins in plan.get('cohort_asins', {}).items() for asin in asins}
    sources = [('group', [a for asins in plan['group_asins'].values() for a in asins]), ('new', plan['new_asins']), ('cohort', list(cohort_group))]
    rows = []
    for source, asins in sources:
        for asin in dict.fromkeys(asins):
            path = KEEPA_DIR / 'products' / f'{asin}.json'
            p = json.loads(path.read_text()) if path.exists() else {}
            if p and p.get('title'):
                rows.append(product_row(source, asin, p, windows, cohort_group))
    df = pd.DataFrame(rows)
    df = df[df.is_flower].drop(columns='is_flower')
    # Variations share one rating count, so keep one row per product family: the best-selling variation.
    df = df.sort_values(['monthly_sold_now', 'asin'], ascending=[False, True], na_position='last', kind='mergesort')
    df = df.drop_duplicates(['source', 'parent_asin']).reset_index(drop=True)
    df.insert(0, 'row_order', range(1, len(df) + 1))         # dbt uses this order for "top 50 per group"

    # Product forms among launches since 2024 (one row per family across the group and new sources).
    launches = df[df.source.isin(['group', 'new'])].drop_duplicates('parent_asin')
    launches = launches[(launches.listed_since >= '2024-01-01') & ~launches.title.str.lower().str.contains(FORM_NOISE)]
    forms = launches.apply(lambda r: new_form(r.title.lower(), r.brand), axis=1)
    df['new_form'] = forms.reindex(df.index)

    counts = pd.DataFrame([
        {'keepa_group': group,
         'products_selling_100_plus': max(json.loads((KEEPA_DIR / 'finder' / f'{group[:2]}_count{i}.json').read_text()).get('totalResults') or 0
                                          for i in range(len(queries)))}
        for group, queries in COUNT_QUERIES.items()])

    pipe = duckdb.connect(str(PIPELINE_DB))
    for name, frame in [('keepa_products', df), ('keepa_finder_counts', counts)]:
        pipe.register('frame', frame)
        pipe.execute(f'create or replace table {name} as select * from frame')
        pipe.unregister('frame')
    pipe.close()
    summary = {'snapshot': SNAPSHOT.date().isoformat(), 'api_responses_read': len(rows), 'keepa_products': len(df),
               'by_source': df.source.value_counts().to_dict(), 'launches_since_2024_with_form': int(df.new_form.notna().sum()),
               'keepa_finder_counts': len(counts)}
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / 'keepa_summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
