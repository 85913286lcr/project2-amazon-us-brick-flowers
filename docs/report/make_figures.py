"""Draw the four charts of the written report from the marts in BigQuery.

Run: python docs/report/make_figures.py   (needs `gcloud auth application-default login`)
Blue is Amazon 2023, purple is Amazon 2026, the same as in the slides.
"""
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from google.cloud import bigquery

PROJECT = os.environ.get('GOOGLE_CLOUD_PROJECT') or os.environ.get('PROJECT2_GCP_PROJECT', 'united-firefly-509307-h9')
OUT = Path(__file__).parent / 'figures'
BRICK = 'Brick flower bouquets & bonsai (adult display)'
BLUE, PURPLE, GREY, INK = '#2E7BBF', '#6B4FC0', '#B8B4AE', '#2E2925'
SHOWN = {BRICK: 'Brick flower bouquets', 'Toddler flower-garden stacking sets': 'Toddler garden sets',
         'Craft bouquets & paper flowers': 'Craft bouquets', 'Flower-image puzzles & cards': 'Flower-image puzzles',
         'Planting & science kits': 'Planting kits'}

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.edgecolor': GREY, 'text.color': INK, 'axes.labelcolor': INK, 'xtick.color': INK, 'ytick.color': INK})
client = bigquery.Client(project=PROJECT, location='US')


def q(sql):
    job = client.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000))
    return job.result().to_dataframe()


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=160)
    plt.close(fig)


# 1. which kind: growth of each kind against all toys
trend = q('select play_pattern, relative_growth_index from project2_marts.mart_flower_pattern_trend')
trend = trend[trend.play_pattern.isin(SHOWN)].sort_values('relative_growth_index')
fig, ax = plt.subplots(figsize=(6.4, 2.9))
bars = ax.barh(trend.play_pattern.map(SHOWN), trend.relative_growth_index.astype(float),
               color=[BLUE if p == BRICK else GREY for p in trend.play_pattern])
ax.axvline(1, color=INK, linewidth=1, linestyle='--')
ax.text(1.04, len(trend) - 0.42, 'all toys = 1.00', fontsize=8.5, va='center')
ax.set_ylim(-0.6, len(trend) - 0.15)
ax.bar_label(bars, fmt='%.2f×', padding=4)
ax.set_xlim(0, 3.2)
ax.set_xlabel('Relative growth index vs all toys, Jan-Sep 2023 against Jan-Sep 2022')
save(fig, 'fig1_which_kind.png')

# 2. who gets the growth: LEGO against other brands
brands = q(f"""select case when is_lego_brand then 'LEGO' else 'Other brands' end as brand_group,
                      sum(reviews_2022_jan_sep) as r22, sum(reviews_2023_jan_sep) as r23
               from project2_marts.mart_flower_product_stats where play_pattern = '{BRICK}' group by 1 order by 1""")
fig, ax = plt.subplots(figsize=(5.2, 2.9))
x = range(len(brands))
b1 = ax.bar([i - 0.2 for i in x], brands.r22.astype(int), width=0.4, color='#A9CBE8', label='Jan-Sep 2022')
b2 = ax.bar([i + 0.2 for i in x], brands.r23.astype(int), width=0.4, color=BLUE, label='Jan-Sep 2023')
ax.bar_label(b1, fmt='{:,.0f}', padding=2)
ax.bar_label(b2, fmt='{:,.0f}', padding=2)
ax.set_xticks(list(x), brands.brand_group)
ax.set_ylabel('Brick-flower reviews written')
ax.set_ylim(0, float(brands.r23.max()) * 1.15)
ax.legend(frameon=False)
save(fig, 'fig2_who_gets_the_growth.png')

# 3. what goes wrong: topics in 1-2 star reviews of brick flowers
pains = q(f"""select theme, share_of_low_reviews_pct, low_reviews from project2_marts.mart_flower_theme_evidence
              where play_pattern = '{BRICK}' and theme_group like 'Experience%' and avg_rating_when_mentioned < 4.2 and mentions >= 5
              order by share_of_low_reviews_pct desc limit 8""").iloc[::-1]
fig, ax = plt.subplots(figsize=(6.4, 3.1))
bars = ax.barh(pains.theme, pains.share_of_low_reviews_pct.astype(float), color=[GREY] * (len(pains) - 3) + [BLUE] * 3)
ax.bar_label(bars, fmt='%.0f%%', padding=4)
ax.set_xlim(0, 36)
ax.set_xlabel(f'% of {int(pains.low_reviews.iloc[0])} brick-flower reviews rated 1 or 2 stars')
save(fig, 'fig3_what_goes_wrong.png')

# 4. Amazon 2026: ratings added, 2025 against 2026
groups = q("""select keepa_group, reviews_added_2025, reviews_added_2026 from project2_marts.mart_keepa_group_verdict
              where keepa_group like 'G1%'""").iloc[0]
fig, ax = plt.subplots(figsize=(4.2, 2.9))
bars = ax.bar(['1 Jan - 7 Oct 2025', '1 Jan - 7 Oct 2026'], [int(groups.reviews_added_2025), int(groups.reviews_added_2026)],
              color=['#CFC5EE', PURPLE], width=0.55)
ax.bar_label(bars, fmt='{:,.0f}', padding=2)
ax.set_ylabel('New ratings')
ax.set_title('Top 50 non-LEGO brick flowers', fontsize=10, loc='left')
ax.set_ylim(0, int(groups.reviews_added_2026) * 1.15)
save(fig, 'fig4_amazon_2026.png')
print('saved 4 figures to', OUT)
