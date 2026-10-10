import nbformat as nbf

OUT = str(__import__('pathlib').Path(__file__).resolve().parent / 'flower_analysis.ipynb')
nb = nbf.v4.new_notebook()
md = lambda s: nb.cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: nb.cells.append(nbf.v4.new_code_cell(s.strip()))

md("""
# Which flower toy should the store sell? Analysis on the Project 2 warehouse

This notebook reads the **dbt marts in BigQuery through SQLAlchemy** and answers the business question with pandas:

1. Pipeline integrity: do the warehouse row counts equal the raw source?
2. Which kind of flower toy has demand, growth and satisfaction?
3. **Monthly trend** of that demand
4. **Top-selling products** (review volume is the demand proxy, the dataset has no sales)
5. **Customer segmentation** by purchase (review) behaviour
6. Why people buy it, and what to improve
7. Is "DIY" itself the trend?
8. Amazon 2026: does the 2023 answer still hold?

Data: Amazon Reviews 2023, Toys & Games (US). Reviews end on 2023-09-11, so every year-on-year comparison uses January–September, and growth is read **relative to the whole toy market** because the dataset itself thins out in 2023.
""")

code("""
import os
import warnings
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import create_engine, text

warnings.filterwarnings('ignore')
pd.set_option('display.max_colwidth', 70)
pd.set_option('display.float_format', lambda v: f'{v:,.2f}')

PROJECT = os.environ.get('PROJECT2_GCP_PROJECT', 'united-firefly-509307-h9')
engine = create_engine(f'bigquery://{PROJECT}', location='US')   # SQLAlchemy engine on the warehouse

def q(sql):
    \"\"\"Run a query on the warehouse and return a DataFrame. Only small mart tables are read.\"\"\"
    with engine.connect() as con:
        return pd.read_sql_query(text(sql), con)

BRICK = 'Brick flower bouquets & bonsai (adult display)'   # the play pattern this analysis ends on
BLUE, GREY, INK = '#2a78d6', '#a3a29c', '#1f2937'
plt.rcParams.update({'font.family': 'Arial', 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.edgecolor': '#c3c2b7', 'figure.dpi': 110})
""")

md("## 1. Pipeline integrity\nThe star schema must hold every raw record. The same check runs as a dbt test on every build.")
code("""
integrity = q('''
select 'products' as entity,
       (select count(*) from project2_raw.main_amazon_products_raw) as raw_rows,
       (select count(*) from project2_analytics.dim_product) as warehouse_rows
union all
select 'reviews',
       (select count(*) from project2_raw.main_amazon_reviews_raw),
       (select count(*) from project2_analytics.fact_reviews)
''')
integrity['match'] = integrity.raw_rows == integrity.warehouse_rows
integrity
""")
code("""
q('''
select (select count(*) from project2_analytics.dim_customer) as customers,
       (select count(*) from project2_analytics.dim_date) as review_dates,
       (select count(*) from project2_analytics.dim_flower_product) as flower_products,
       (select count(*) from project2_analytics.fact_flower_reviews) as flower_reviews,
       (select count(*) from project2_analytics.dim_play_pattern) as play_patterns
''')
""")

md("""
## 2. Which kind of flower toy?
`mart_flower_pattern_trend` has one row per **play pattern** (how the toy is used). Interest = reviews written Jan–Sep 2023; satisfaction = average rating; `relative_growth_index` = the pattern's 2023/2022 growth divided by the toy market's (1.0 = same as the market).
""")
code("""
trend = q('''
select p.play_pattern, p.play_pattern as pattern, d.is_diy, p.products, p.brands, p.reviews,
       p.reviews_2022_jan_sep as rv_2022, p.reviews_2023_jan_sep as rv_2023,
       p.relative_growth_index as growth_vs_market, p.avg_rating, p.low_rating_pct, p.new_products_2022_23, p.quadrant
from project2_marts.mart_flower_pattern_trend p
join project2_analytics.dim_play_pattern d using (play_pattern)
order by p.reviews_2023_jan_sep desc
''')
trend.drop(columns=['play_pattern']).head(12)
""")
code("""
big = trend[trend.reviews >= 300]
fig, ax = plt.subplots(figsize=(9.5, 5.6))
nudge = {'Flower plush & pillows': (8, -12), 'Craft bouquets & paper flowers': (10, 4), 'Character plush with flower motif': (-2, 14)}
for _, r in big.iterrows():
    hero = r.play_pattern == BRICK
    ax.scatter(r.rv_2023, r.avg_rating, s=40 + r.products * 0.9, color=BLUE if hero else GREY,
               alpha=0.9 if hero else 0.6, edgecolor='white', linewidth=1.5, zorder=3)
    if r.rv_2023 >= 100:                      # label the patterns with real volume; small ones stay as dots
        dx, dy = nudge.get(r.pattern, (8, 6))
        ax.annotate(f"{r.pattern.split(' (')[0]}  {r.growth_vs_market:.2f}x", (r.rv_2023, r.avg_rating), xytext=(dx, dy),
                    textcoords='offset points', fontsize=8.5, color=INK, weight='bold' if hero else 'normal',
                    ha='right' if dx < 0 else 'left')
ax.axvline(big.rv_2023.median(), color='#c3c2b7', ls='--', lw=1)
ax.axhline(big.avg_rating.median(), color='#c3c2b7', ls='--', lw=1)
ax.set_xscale('log'); ax.set_xlim(right=big.rv_2023.max() * 4)
ax.set_xlabel('Interest: reviews written Jan-Sep 2023 (log scale)')
ax.set_ylabel('Satisfaction: average rating')
ax.set_title('Play patterns by interest and satisfaction (label = growth vs toy market, bubble = number of products)', loc='left', fontsize=10.5)
plt.tight_layout(); plt.show()
""")
md("""
**Reading.** Adult brick flowers have the highest current interest of all flower toys and are the only large pattern growing far faster than the market (2.76x). Their rating sits at the median: buyers want the product but are not fully satisfied, so there is room for a better-made version.
""")

md("## 3. Monthly trend\nMonthly review volume per play pattern (`mart_flower_monthly_reviews`). Review volume stands in for sales.")
code("""
monthly = q('''
select review_month, play_pattern, reviews
from project2_marts.mart_flower_monthly_reviews
where review_month between date '2019-01-01' and date '2023-08-31'
''')
monthly['review_month'] = pd.to_datetime(monthly.review_month)
brick = monthly[monthly.play_pattern == BRICK].set_index('review_month').reviews.sort_index()
others = monthly[monthly.play_pattern != BRICK].groupby('review_month').reviews.sum().sort_index()
fig, ax = plt.subplots(figsize=(9.5, 4.4))
ax.plot(others.index, others.values, color=GREY, lw=1.6)
ax.plot(brick.index, brick.values, color=BLUE, lw=2.4)
ax.axvspan(pd.Timestamp('2023-03-15'), others.index.max(), color='#f1f0ec', zorder=0)
ax.text(pd.Timestamp('2023-03-25'), others.max() * 0.93, 'dataset thins out', fontsize=8.5, color='#52514e')
ax.text(pd.Timestamp('2021-03-01'), 120, 'Brick flower bouquets & bonsai', ha='center', fontsize=9, weight='bold', color=BLUE)
ax.annotate('All other flower toys', (others.idxmax(), others.max()), xytext=(8, 0), textcoords='offset points', fontsize=9, color=INK)
ax.set_ylabel('Reviews per month')
ax.set_title('Monthly reviews: brick flowers vs all other flower toys (complete months, 2019 - Aug 2023)', loc='left', fontsize=10.5)
plt.tight_layout(); plt.show()
""")
code("""
yearly = q(f'''
select review_year, sum(reviews) as brick_flower_reviews
from project2_marts.mart_flower_monthly_reviews
where play_pattern = '{BRICK}' and month_of_year <= 9 and review_year between 2019 and 2023
group by 1 order by 1
''')
base = q('select review_year, jan_sep_reviews as all_toy_reviews from project2_marts.mart_review_baseline where review_year between 2019 and 2023 order by 1')
yearly = yearly.merge(base, on='review_year')
yearly['brick_flower_yoy_pct'] = yearly.brick_flower_reviews.pct_change() * 100
yearly['toy_market_yoy_pct'] = yearly.all_toy_reviews.pct_change() * 100
yearly
""")
md("""
**Reading.** Brick-flower reviews rose every year, including 2023 when the whole toy dataset fell by about a third. Other flower toys peaked in 2020-21 and then declined, while brick flowers grew from a few percent of that volume in 2020 to about half of it by early 2023. Both lines peak around December-January: flower toys are bought as gifts.

The sharp drop after March 2023 is the dataset, not the market: reviews written shortly before the collection date are only partly captured, for every category. That is why growth is always compared with the whole toy market over the same months.
""")

md("## 4. Top-selling products (by review volume)\n`mart_flower_product_stats` keeps every product. There is no minimum review count; each product carries an evidence level instead.")
code("""
top_products = q(f'''
select left(title, 62) as title, brand, review_count, reviews_2023_jan_sep as rv_2023, review_avg as avg_rating,
       low_rating_pct, price, evidence_level
from project2_marts.mart_flower_product_stats
where play_pattern = '{BRICK}'
order by reviews_2023_jan_sep desc, review_count desc
limit 12
''')
top_products
""")
code("""
q(f'''
select case when is_lego_brand then 'LEGO' else 'Other brands' end as brand_group,
       count(*) as products, sum(review_count) as reviews,
       sum(reviews_2022_jan_sep) as rv_2022, sum(reviews_2023_jan_sep) as rv_2023,
       sum(review_avg * review_count) / sum(review_count) as avg_rating,
       sum(low_rating_pct * review_count) / sum(review_count) as low_rating_pct
from project2_marts.mart_flower_product_stats
where play_pattern = '{BRICK}'
group by 1 order by 1
''')
""")
md("""
**Reading.** LEGO sets lead the ranking and hold the best ratings, but most of the 2023 volume and almost all of the growth comes from other brands, which are rated lower and collect more low ratings. Demand is there; quality outside LEGO is the gap.
""")

md("## 5. Customer segmentation by purchase behaviour\n`mart_flower_customer_segments`: one row per customer who reviewed a flower toy, joined to `dim_customer` (lifetime behaviour across all toys).")
code("""
loyalty = q('''
select flower_loyalty_segment as segment, count(*) as customers, avg(flower_avg_rating) as avg_flower_rating,
       avg(lifetime_review_count) as avg_lifetime_reviews, avg(flower_share_of_reviews) * 100 as flower_share_of_their_reviews_pct
from project2_marts.mart_flower_customer_segments group by 1 order by 1
''')
loyalty['share_of_customers_pct'] = loyalty.customers / loyalty.customers.sum() * 100
loyalty
""")
code("""
interest = q('''
select flower_interest_segment as segment, count(*) as customers, avg(flower_avg_rating) as avg_flower_rating,
       avg(lifetime_review_count) as avg_lifetime_reviews
from project2_marts.mart_flower_customer_segments group by 1 order by 2 desc
''')
activity = q('''
select activity_segment as segment, count(*) as customers, avg(flower_avg_rating) as avg_flower_rating
from project2_marts.mart_flower_customer_segments group by 1 order by 1
''')
fig, axes = plt.subplots(1, 2, figsize=(11.5, 3.6))
for ax, frame, title in [(axes[0], interest, 'Customers by flower interest'), (axes[1], activity, 'Customers by overall review activity')]:
    colors = [BLUE if 'brick' in s else GREY for s in frame.segment]
    bars = ax.barh(frame.segment, frame.customers, color=colors if ax is axes[0] else GREY)
    for b, r in zip(bars, frame.avg_flower_rating):
        ax.text(b.get_width(), b.get_y() + b.get_height() / 2, f'  {b.get_width():,.0f} customers, avg {r:.2f}', va='center', fontsize=8.5, color=INK)
    ax.set_title(title, loc='left', fontsize=10.5); ax.invert_yaxis(); ax.set_xlim(0, frame.customers.max() * 2.0); ax.set_xticks([])
plt.tight_layout(); plt.show()
interest
""")
md("""
**Reading.** Most flower-toy customers buy once (gift purchases). A small group returns for a second and third product; they rate higher and are heavy reviewers overall. They are the natural audience for series and add-on packs. Customers who bought brick flowers *and* another flower toy are the most satisfied segment.
""")

md("## 6. Why people buy brick flowers, and what to improve\n`mart_flower_theme_evidence` (regex codebook on review text) and `mart_flower_need_evidence` (sentences where buyers say what they wish the product had). Evidence tier: strong = 30+ reviews **and** 10+ products **and** 5+ brands.")
code("""
themes = q(f'''
select theme_group as grp, theme, mentions, mention_pct, avg_rating_when_mentioned as rating_when_mentioned,
       share_of_low_reviews_pct, products, brands, evidence
from project2_marts.mart_flower_theme_evidence
where play_pattern = '{BRICK}' and mentions >= 20
''')
themes[themes.grp.str.startswith('Motive')].sort_values('mention_pct', ascending=False).head(10).drop(columns=['share_of_low_reviews_pct'])
""")
code("""
pains = themes[themes.grp.str.startswith('Experience') & (themes.rating_when_mentioned < 4.2)].sort_values('share_of_low_reviews_pct', ascending=True)
fig, ax = plt.subplots(figsize=(8.5, 4))
bars = ax.barh(pains.theme, pains.share_of_low_reviews_pct, color=[BLUE if v >= 15 else GREY for v in pains.share_of_low_reviews_pct])
for b, n in zip(bars, pains.brands):
    ax.text(b.get_width() + 0.4, b.get_y() + b.get_height() / 2, f'{b.get_width():.0f}%  ·  {n} brands', va='center', fontsize=8.5, color=INK)
ax.set_xlabel('Share of 1–2 star reviews that mention the problem (%)'); ax.set_xlim(0, pains.share_of_low_reviews_pct.max() * 1.35)
ax.set_title('What goes wrong in low-rated brick-flower reviews', loc='left', fontsize=11)
plt.tight_layout(); plt.show()
""")
code("""
q(f'''
select need as unmet_need, sentences as wish_sentences, products, brands, avg_rating, evidence
from project2_marts.mart_flower_need_evidence
where play_pattern = '{BRICK}' and need != 'Uncategorised'
order by sentences desc limit 10
''')
""")
md("""
**Reading.** People buy brick flowers as a gift and as decor: a flower that lasts. What fails is the making: missing pieces and builds that fall apart dominate low ratings, across roughly a hundred brands. Buyers ask for clearer instructions, a vase, sturdier stems and numbered bags. These are the product specifications for the store.
""")

md("## 7. Is DIY itself the trend?")
code("""
q('select * from project2_marts.mart_flower_diy_2023 order by relative_growth_index desc')
""")
md("""
**Reading.** In 2023 only one DIY family, adult brick building, beat the market. Toddler stacking sets moved with the market; crafts and planting kits fell behind. So the 2023 evidence supports "build a bouquet", not DIY in general.
""")

md("""
## 8. Amazon 2026: does the 2023 answer still hold?
The review dataset stops in 2023, so I checked today's market with a Keepa API snapshot (2026-10-07): the current top 50 products of seven groups, products first listed since 2024, and the 2023 top products followed into 2026.

Three signals per group (`mart_keepa_group_verdict`):
- **S1** rating count added 1 Jan - 7 Oct 2026 vs the same window in 2025
- **S2** units sold per month now vs a year ago
- **S3** products listed since 2024 that sell 50+ a month, compared with the median group

Two or three signals up = trending, one = stable, none = not trending.
""")
code("""
verdict = q(\'\'\'
select keepa_group as product_group, products_analyzed as products, reviews_added_2025, reviews_added_2026,
       s1_reviews_2026_vs_2025_pct as s1_reviews_pct, s2_monthly_sold_yoy_pct as s2_sold_pct,
       s3_new_since_2024_selling_50_plus as s3_new_sellers, products_selling_100_plus,
       rating_now_median as rating, price_now_median as price, signals_up, verdict
from project2_marts.mart_keepa_group_verdict order by keepa_group
\'\'\')
verdict
""")
code("""
v = verdict.sort_values('s3_new_sellers')
fig, axes = plt.subplots(1, 2, figsize=(11.5, 3.8), sharey=True)
hero = [BLUE if g.startswith('G1') else GREY for g in v.product_group]
names = [g[3:] for g in v.product_group]
axes[0].barh(names, v.s3_new_sellers, color=hero)
for y, n in enumerate(v.s3_new_sellers):
    axes[0].text(n + 1, y, f'{n:.0f}', va='center', fontsize=9, color=INK)
axes[0].set_title('New products since 2024 that sell 50+ a month', loc='left', fontsize=10.5)
axes[1].barh(names, v.s1_reviews_pct, color=hero)
for y, n in enumerate(v.s1_reviews_pct):
    axes[1].text(n + (6 if n >= 0 else -6), y, f'{n:+.0f}%', va='center', ha='left' if n >= 0 else 'right', fontsize=9, color=INK)
axes[1].axvline(0, color='#c3c2b7', lw=1)
axes[1].set_title('Rating count added in 2026 vs 2025 (same window)', loc='left', fontsize=10.5)
axes[1].set_xlim(v.s1_reviews_pct.min() - 45, v.s1_reviews_pct.max() + 45)
axes[0].set_xlim(0, v.s3_new_sellers.max() * 1.15)
plt.tight_layout(); plt.show()
""")
md("""
**Reading.** Non-LEGO brick flowers are trending on all three signals: reviews nearly tripled against 2025 and 65 new products since 2024 already sell 50+ a month, more than any other group. LEGO's own flower sets sell far more units but their review growth is negative, because LEGO keeps replacing older sets with new ones. Planting kits and toddler garden sets are not trending, as in 2023. Flower crafts changed: behind the market in 2023, trending in 2026.

Non-LEGO brick flowers still rate lower than LEGO (4.5 vs 4.9), so the quality gap found in the 2023 reviews is still open.
""")
code("""
q(\'\'\'
select new_form as product_form, products, selling_50_plus, monthly_sold_sum as units_per_month, brands,
       rating_median as rating, price_median as price
from project2_marts.mart_keepa_new_forms
where new_form not in ('Other', 'Other crafts')
order by monthly_sold_sum desc
\'\'\')
""")
code("""
cohort = q(\'\'\'
select keepa_group as product_group, count(*) as products_2023_top, countif(sales_rank_now is not null) as still_ranked,
       sum(reviews_added_2023) as added_2023, sum(reviews_added_2025) as added_2025, sum(reviews_added_2026) as added_2026
from project2_analytics.fact_keepa_snapshot
where source = 'cohort'
group by 1 order by 1
\'\'\')
cohort
""")
md("""
**Reading.** What is new since 2024: gothic and dark-romance brick flowers, single-stem and mini flower series, fabric bouquet kits for kids, and no-glue "poke art" bouquets. The last one answers the glue-and-mess complaint from the 2023 craft reviews.

The cohort table is a warning for running the store: in most groups the top products of 2023 collect far fewer reviews in 2026 (flower crafts are the exception, and only 4 of the 20 brick-flower products from 2023 could still be matched). Growth comes from new products replacing old ones, so the range has to be refreshed regularly.

## Conclusion
- **Sell adult brick flowers.** Highest interest among flower toys in 2023 (growth 2.76x the market) and still trending in 2026.
- **Compete on the making experience**: complete, numbered parts; clear instructions; sturdy stems; a vase included.
- **Design for gifting and for the returning collector**: series and add-on packs; themed lines (gothic, single stems) are where new products are entering.

## Limits
- Review counts and rating counts are demand proxies, not sales. Keepa's monthly-sold figure is Amazon's rounded "bought in past month" badge.
- One US marketplace. The review data ends in September 2023 and is incomplete after March 2023.
- Themes and needs come from a rule-based codebook that I checked on samples; it is not labelled data.
- The 2026 view looks at today's top products, which favours recent winners; the cohort view favours ageing products. I read them together.
""")

nb.metadata['kernelspec'] = {'display_name': 'Python (project2-analysis)', 'language': 'python', 'name': 'project2-analysis'}
nbf.write(nb, OUT)
print(OUT)
