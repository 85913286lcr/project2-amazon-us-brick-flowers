"""Check that the pipeline reproduces the frozen contract (contract/golden).

The website and the AI gift guide were built on the contract; this script proves the warehouse arrives
at the same numbers. Rows are matched on the manifest keys. Numbers must agree within 6e-4, because the
golden tables are stored rounded to three decimals. Exit code 1 on any difference.

Usage: python 6_reconcile/verify_against_contract.py <dir_with_exported_csvs> [--scope 2023|all]
"""
import json
import sys
from pathlib import Path

import pandas as pd

CONTRACT = Path(__file__).resolve().parents[1] / 'contract'
TOLERANCE = 6e-4
SCOPE_2023 = ('g01_', 'g02_', 'g03_', 'g04_', 'g05_')


def compare(golden, candidate, keys):
    if len(golden) != len(candidate) or set(golden.columns) != set(candidate.columns):
        return f'shape differs: golden {golden.shape} vs pipeline {candidate.shape}'
    joined = golden.merge(candidate[golden.columns], on=keys, how='outer', suffixes=('_g', '_c'), indicator=True)
    unmatched = int((joined._merge != 'both').sum())
    diffs = []
    for col in [c for c in golden.columns if c not in keys]:
        a, b = joined[f'{col}_g'], joined[f'{col}_c']
        numeric = all(pd.api.types.is_numeric_dtype(x) and not pd.api.types.is_bool_dtype(x) for x in (a, b))
        if numeric:
            bad = ~(((a - b).abs() <= TOLERANCE) | (a.isna() & b.isna()))
        else:
            bad = ~((a.astype(str) == b.astype(str)) | (a.isna() & b.isna()))
        if bad.any():
            diffs.append(f'{col}({int(bad.sum())})')
    if unmatched or diffs:
        return f'unmatched keys {unmatched}; columns {", ".join(diffs) or "-"}'
    return None


def main(candidate_dir, scope):
    manifest = json.loads((CONTRACT / 'manifest.json').read_text())
    failed, lines = 0, []
    for item in manifest['files']:
        if 'keys' not in item:
            continue
        name = Path(item['file']).name
        if scope == '2023' and not name.startswith(SCOPE_2023):
            lines.append(f'SKIPPED  {name} (outside --scope 2023)')
            continue
        path = Path(candidate_dir) / name
        if not path.exists():
            lines.append(f'MISSING  {name}')
            failed += 1
            continue
        problem = compare(pd.read_csv(CONTRACT / item['file']), pd.read_csv(path), item['keys'])
        if problem:
            lines.append(f'DIFF     {name}: {problem}')
            failed += 1
        else:
            lines.append(f'OK       {name} ({item["rows"]} rows)')
    result = 'PASS' if not failed else f'FAIL ({failed} files)'
    lines.append(f'RESULT {result} · contract {manifest["contract_version"]} · scope {scope}')
    print('\n'.join(lines))
    return 0 if not failed else 1


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    scope = sys.argv[sys.argv.index('--scope') + 1] if '--scope' in sys.argv else 'all'
    args = [a for a in args if a != scope]
    sys.exit(main(args[0], scope))
