"""Shared locations for the flower enrichment step.

The raw Amazon files are large and live outside the repository; point PROJECT2_RAW_DIR at them.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW_DIR = Path(os.environ.get('PROJECT2_RAW_DIR', REPO.parents[1] / 'Data' / 'Raw'))
RAW_META = RAW_DIR / 'meta_Toys_and_Games.jsonl.gz'
RAW_REVIEWS = RAW_DIR / 'Toys_and_Games.jsonl.gz'
PIPELINE_DB = REPO / 'duckdb' / 'giftfinder.duckdb'          # what Meltano reads
WORK_DB = REPO / 'duckdb' / 'flower_enrichment.duckdb'       # scratch tables of this step
KEEPA_DIR = Path(os.environ.get('PROJECT2_KEEPA_DIR', REPO / 'data' / 'keepa_2026'))   # cached Keepa API responses
EVIDENCE = REPO / 'docs' / 'evidence' / 'enrichment'
CONTRACT = REPO / 'contract'
