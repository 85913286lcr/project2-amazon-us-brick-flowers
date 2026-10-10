"""Export the dbt marts in the layout of the frozen contract, so they can be compared with it.

Reads BigQuery through SQLAlchemy and writes one CSV per golden table into <out_dir>.
Usage: python scripts/export_marts_for_contract.py [out_dir]   (default: docs/evidence/contract/export)
"""
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

REPO = Path(__file__).resolve().parents[1]
PROJECT = os.environ.get('PROJECT2_GCP_PROJECT', 'united-firefly-509307-h9')
EXPORTS = {
    'g01_flower_products_labels': """
        select parent_asin, relevance_tier as tier, relevance, play_pattern as primary_pattern, all_patterns as patterns, brand
        from project2_analytics.dim_flower_product""",
    'g02_pattern_overview_2023': """
        select play_pattern as primary_pattern, products, brands, reviews,
               products_strong_evidence as ev_strong, products_medium_evidence as ev_mid, products_weak_evidence as ev_weak,
               reviews_2021_jan_sep as rv21, reviews_2022_jan_sep as rv22, reviews_2023_jan_sep as rv23,
               avg_rating, low_rating_pct as low_pct, cast(median_price as float64) as median_price, new_products_2022_23,
               metadata_ratings as meta_ratings, yoy_pct, relative_growth_index, quadrant
        from project2_marts.mart_flower_pattern_trend""",
    'g03_need_evidence_2023': """
        select need, sentences, products, brands, avg_rating, first_year, last_year, patterns,
               play_pattern as primary_pattern, evidence
        from project2_marts.mart_flower_need_evidence""",
    'g04_theme_evidence_2023': """
        select theme_group as grp, theme, play_pattern as primary_pattern, mentions as n, total_reviews as total, products, brands,
               avg_rating_when_mentioned, pattern_avg_rating as pattern_avg, low_mentions as n_low, low_reviews as low_total,
               mention_pct, share_of_low_reviews_pct, evidence
        from project2_marts.mart_flower_theme_evidence""",
    'g05_diy_2023': """
        select diy_family, products, brands, reviews_2022_jan_sep as rv22, reviews_2023_jan_sep as rv23, yoy_pct, relative_growth_index
        from project2_marts.mart_flower_diy_2023""",
    'g06_keepa2026_group_verdicts': """
        select keepa_group as `group`, is_diy as DIY, products_analyzed, reviews_added_2023, reviews_added_2024, reviews_added_2025,
               reviews_added_2026, s1_reviews_2026_vs_2025_pct as S1_reviews_2026_vs_2025_pct,
               s1_reviews_2025_vs_2023_pct as S1_reviews_2025_vs_2023_pct, monthly_sold_now_sum, monthly_sold_1y_ago_sum,
               s2_monthly_sold_yoy_pct as S2_monthly_sold_yoy_pct, same_products_monthly_sold_yoy_pct,
               products_selling_100_plus as finder_count_monthlySold_100plus,
               s3_new_since_2024_selling_50_plus as S3_new_since_2024_selling_50plus, median_rank_2023, median_rank_2025,
               median_rank_2026, rating_now_median, price_now_median, s1_up as S1_up, s2_up as S2_up, s3_up as S3_up, signals_up, verdict
        from project2_marts.mart_keepa_group_verdict""",
    'g07_keepa2026_products': """
        select source, asin, parent_asin, title, brand, play_pattern as primary_pattern, keepa_group as `group`,
               cast(listed_since as string) as listed_since, monthly_sold_now, rating_now, rating_count_now, price_now,
               reviews_added_2023, reviews_added_2024, reviews_added_2025, reviews_added_2026
        from project2_analytics.fact_keepa_snapshot""",
    'g08_diy_2026': """
        select is_diy as diy, reviews_added_2025, reviews_added_2026,
               new_since_2024_selling_50_plus as S3_new_since_2024_selling_50plus, reviews_2026_vs_2025_pct
        from project2_marts.mart_keepa_diy_2026""",
    'g09_new_forms_2026_products': """
        select parent_asin, asin, title, brand, cast(listed_since as string) as listed_since, monthly_sold_now, rating_now,
               price_now, new_form as form
        from project2_analytics.fact_keepa_snapshot where new_form is not null""",
    'g10_new_forms_2026_summary': """
        select new_form as form, products, selling_50_plus as selling_50plus, monthly_sold_sum, brands, rating_median, price_median
        from project2_marts.mart_keepa_new_forms""",
}


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f'bigquery://{PROJECT}', location='US')
    with engine.connect() as con:
        for name, sql in EXPORTS.items():
            frame = pd.read_sql_query(text(sql), con)
            frame.to_csv(out / f'{name}.csv', index=False)
            print(f'{name}: {len(frame)} rows')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else REPO / 'docs/evidence/contract/export')
