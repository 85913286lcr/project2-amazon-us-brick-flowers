"""Fetch the Amazon 2026 snapshot from the Keepa API (amazon.com) into data/keepa_2026/.

Every response is cached as a JSON file, and a cached file is never requested again, so re-running this
script against a complete cache costs no tokens. The analysis uses the snapshot of 2026-10-07.

What is fetched
  finder/    Product Finder results: top products of each group, "sells 100+ a month" counts,
             and products first listed since 2024 that sell 50+ a month
  products/  one file per ASIN: price, sales rank, rating count and monthly-sold history
  plan.json  which ASINs belong to which request

Tokens: about 2 per product (history + rating) and 11 per Finder query; 2,930 in total for this snapshot.
Needs KEEPA_API_KEY in the environment. Usage: python 1_ingestion/fetch_keepa_snapshot.py
"""
import gzip
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / '2_enrichment'))
from keepa_groups import COUNT_QUERIES, GROUPS, NEW_WORDS  # noqa: E402

CACHE = Path(os.environ.get('PROJECT2_KEEPA_DIR', REPO / 'data' / 'keepa_2026'))
DOMAIN, TOYS_ROOT = 1, 165793011          # amazon.com, Toys & Games
KEEPA_EPOCH_MIN = 21564000                # Keepa time = unix minutes - this offset
PER_GROUP, NEW_MAX = 100, 500


def keepa_minute(dt):
    return int(dt.replace(tzinfo=timezone.utc).timestamp() // 60) - KEEPA_EPOCH_MIN


def call(endpoint, params):
    import certifi
    url = f'https://api.keepa.com/{endpoint}?' + urllib.parse.urlencode(dict(params, key=os.environ['KEEPA_API_KEY']))
    for _ in range(6):
        try:
            with urllib.request.urlopen(url, timeout=180, context=ssl.create_default_context(cafile=certifi.where())) as r:
                body = r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429:             # out of tokens: wait for the refill
                time.sleep(65)
                continue
            raise SystemExit(f'Keepa HTTP {e.code} on {endpoint}')
        res = json.loads(gzip.decompress(body) if body[:2] == b'\x1f\x8b' else body)
        if res.get('error'):
            raise SystemExit(f"Keepa error on {endpoint}: {res['error'].get('message')}")
        print(f"  {endpoint}: used {res.get('tokensConsumed')} tokens, {res.get('tokensLeft')} left", flush=True)
        return res
    raise SystemExit('Keepa kept answering 429')


def wait_for_tokens(need):
    while True:
        status = call('token', {})
        if status.get('tokensLeft', 0) >= need:
            return
        time.sleep(max(5, status.get('refillIn', 60000) / 1000) + 2)


def finder(name, selection):
    path = CACHE / 'finder' / f'{name}.json'
    if not path.exists():
        wait_for_tokens(12)
        res = call('query', {'domain': DOMAIN, 'selection': json.dumps(selection)})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'selection': selection, 'asinList': res.get('asinList', []), 'totalResults': res.get('totalResults'),
                                    'checked_at': datetime.now(timezone.utc).isoformat()}))
    return json.loads(path.read_text())


def products(asins):
    folder = CACHE / 'products'
    folder.mkdir(parents=True, exist_ok=True)
    todo = [a for a in dict.fromkeys(asins) if not (folder / f'{a}.json').exists()]
    for i in range(0, len(todo), 20):
        batch = todo[i:i + 20]
        wait_for_tokens(2 * len(batch))
        res = call('product', {'domain': DOMAIN, 'asin': ','.join(batch), 'history': 1, 'rating': 1, 'stats': 180})
        found = {p['asin']: p for p in res.get('products', [])}
        for a in batch:                    # unknown ASINs are cached as empty so they are not bought twice
            (folder / f'{a}.json').write_text(json.dumps(found.get(a, {})))


def selection(words, **extra):
    s = {'title': words, 'rootCategory': [TOYS_ROOT], 'productType': [0], 'sort': [['current_SALES', 'asc']], 'perPage': 50, 'page': 0}
    s.update(extra)
    return s


def main():
    plan_path = CACHE / 'plan.json'
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
    else:
        group_asins = {}
        for group, queries in GROUPS.items():
            found = []
            for i, q in enumerate(queries):
                found += finder(f'{group[:2]}_q{i}', selection(q))['asinList']
            group_asins[group] = list(dict.fromkeys(found))[:PER_GROUP]
        since_2024 = keepa_minute(datetime(2024, 1, 1))
        new = []
        for w in NEW_WORDS:
            new += finder(f'new_{w}', selection(w, listedSince_gte=since_2024, monthlySold_gte=50,
                                                sort=[['monthlySold', 'desc']], perPage=100))['asinList']
        plan = {'group_asins': group_asins, 'new_asins': list(dict.fromkeys(new))[:NEW_MAX], 'cohort_asins': {}}
        plan_path.write_text(json.dumps(plan))
    for group, queries in COUNT_QUERIES.items():
        for i, q in enumerate(queries):
            finder(f'{group[:2]}_count{i}', selection(q, monthlySold_gte=100))
    wanted = [a for v in plan['group_asins'].values() for a in v] + plan['new_asins'] + [a for v in plan.get('cohort_asins', {}).values() for a in v]
    missing = [a for a in dict.fromkeys(wanted) if not (CACHE / 'products' / f'{a}.json').exists()]
    print(f'{len(set(wanted))} products planned, {len(missing)} not cached yet')
    if missing:
        products(missing)


if __name__ == '__main__':
    main()
