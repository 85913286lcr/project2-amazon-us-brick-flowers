"""Streamlit app: explore the evidence behind "sell adult brick flowers".

It follows the slides: which kind, what goes wrong, my plan, Amazon 2026. It only reads the tested dbt marts in
BigQuery and adds no rules of its own. The one number that is not from the pipeline is marked as such on the
Amazon 2026 tab. Run locally with `streamlit run app.py`, or deploy to Cloud Run (README.md).
"""
import os

import altair as alt
import pandas as pd
import streamlit as st
from google.cloud import bigquery

PROJECT = os.environ.get('GOOGLE_CLOUD_PROJECT') or os.environ.get('PROJECT2_GCP_PROJECT', 'united-firefly-509307-h9')
BRICK = 'Brick flower bouquets & bonsai (adult display)'
BLUE, PURPLE, GREY, INK = '#2E7BBF', '#6B4FC0', '#B8B4AE', '#2E2925'      # blue = Amazon 2023, purple = Amazon 2026

st.set_page_config(page_title='What should my store sell?', page_icon='🌸', layout='wide')


@st.cache_data(ttl=3600, show_spinner='Reading the marts in BigQuery...')
def q(sql):
    """Run one query on the marts. Each query may scan at most 1 GB, so a mistake cannot become expensive."""
    client = bigquery.Client(project=PROJECT, location='US')
    job = client.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000))
    frame = job.result().to_dataframe()
    for col in frame.columns:                           # NUMERIC arrives as Decimal
        if frame[col].dtype == object:
            try:
                frame[col] = frame[col].astype(float)
            except (TypeError, ValueError):
                pass
    return frame


def short(name):
    return name.split(' (')[0]


st.title('What should my store sell?')
st.caption('Find: Amazon Reviews 2023 (Toys & Games, US). Verify: a Keepa snapshot of Amazon.com on 7 Oct 2026. '
           'Reviews and ratings show activity. They are not sales.')

trend = q("""
    select p.play_pattern, p.products, p.brands, p.reviews, p.reviews_2022_jan_sep, p.reviews_2023_jan_sep,
           p.yoy_pct, p.relative_growth_index, p.avg_rating, p.low_rating_pct
    from project2_marts.mart_flower_pattern_trend p
    order by p.reviews_2023_jan_sep desc""")
hero = trend[trend.play_pattern == BRICK].iloc[0]
brands = q(f"""
    select case when is_lego_brand then 'LEGO' else 'Other brands' end as brand_group, count(*) as products,
           sum(reviews_2022_jan_sep) as reviews_2022, sum(reviews_2023_jan_sep) as reviews_2023,
           sum(review_avg * review_count) / sum(review_count) as avg_rating
    from project2_marts.mart_flower_product_stats where play_pattern = '{BRICK}' group by 1 order by 1""")
brands['change_pct'] = (brands.reviews_2023 / brands.reviews_2022 - 1) * 100
brands['share_2022_pct'] = brands.reviews_2022 / brands.reviews_2022.sum() * 100
brands['share_2023_pct'] = brands.reviews_2023 / brands.reviews_2023.sum() * 100
others = brands[brands.brand_group == 'Other brands'].iloc[0]
groups = q("""
    select keepa_group, products_analyzed, reviews_added_2025, reviews_added_2026, s1_reviews_2026_vs_2025_pct, rating_now_median
    from project2_marts.mart_keepa_group_verdict order by keepa_group""")
g1 = groups[groups.keepa_group.str.startswith('G1')].iloc[0]
pains = q(f"""
    select theme, low_mentions, low_reviews, share_of_low_reviews_pct, products, brands, evidence
    from project2_marts.mart_flower_theme_evidence
    where play_pattern = '{BRICK}' and theme_group like 'Experience%' and avg_rating_when_mentioned < 4.2 and mentions >= 5
    order by share_of_low_reviews_pct desc limit 10""")

a, b, c, d = st.columns(4)
a.metric('Relative growth index vs all toys, 2023', f'{hero.relative_growth_index:.2f}×')
b.metric('Brick-flower reviews, Jan-Sep 2023', f'{int(hero.reviews_2023_jan_sep):,}', f'{hero.yoy_pct:+.0f}% vs 2022')
c.metric('Other brands: share of those reviews', f'{others.share_2023_pct:.0f}%', f'{others.share_2022_pct:.0f}% in 2022', delta_color='off')
d.metric('Ratings added in 2026 vs 2025', f'{g1.s1_reviews_2026_vs_2025_pct:+.0f}%', 'top 50 non-LEGO products', delta_color='off')

tabs = st.tabs(['1  Which kind?', '2  What goes wrong', '3  My plan', '4  Amazon 2026', 'About the data'])

with tabs[0]:
    st.subheader('Brick flowers lead in review activity. Demand extends beyond LEGO.')
    min_reviews = st.slider('Show kinds of flower toy with at least this many reviews in total', 0, 2000, 300, 100)
    view = trend[trend.reviews >= min_reviews].copy()
    view['pattern'] = view.play_pattern.map(short)
    view['highlight'] = view.play_pattern.eq(BRICK).map({True: 'Brick flower bouquets', False: 'Other kinds'})
    chart = alt.Chart(view).mark_circle(opacity=0.85, stroke='white').encode(
        x=alt.X('reviews_2023_jan_sep:Q', scale=alt.Scale(type='log', domain=[10, 20000], nice=False), title='Interest: reviews written in 2023 (log scale)'),
        y=alt.Y('avg_rating:Q', scale=alt.Scale(zero=False), title='Average rating'),
        size=alt.Size('products:Q', title='Products', scale=alt.Scale(range=[80, 1400]), legend=alt.Legend(orient='top', values=[100, 500, 1500])),
        color=alt.Color('highlight:N', scale=alt.Scale(domain=['Brick flower bouquets', 'Other kinds'], range=[BLUE, GREY]), title=None, legend=alt.Legend(orient='top')),
        tooltip=['pattern', 'products', 'brands', 'reviews_2023_jan_sep', alt.Tooltip('relative_growth_index:Q', format='.2f', title='index vs all toys'),
                 alt.Tooltip('avg_rating:Q', format='.2f')])
    named = view[view.reviews_2023_jan_sep >= 100]
    raised = named.pattern.str.startswith('Character plush')        # sits right above another label, so it is lifted a little

    def labels(rows, dy):
        return alt.Chart(rows).mark_text(align='left', dx=10, dy=dy, fontSize=11, color=INK).encode(
            x='reviews_2023_jan_sep:Q', y='avg_rating:Q', text=alt.Text('pattern:N'))
    st.altair_chart((chart + labels(named[~raised], 0) + labels(named[raised], -9)).properties(height=440), width='stretch')
    st.caption('One dot = one kind of flower toy. Right = more reviews in 2023 (Jan-Sep). Up = higher rating. Size = number of products. mart_flower_pattern_trend')

    st.markdown('**Who gets the growth?**')
    who = pd.DataFrame({
        '': brands.brand_group,
        'reviews 2022 → 2023': [f'{int(r.reviews_2022):,} → {int(r.reviews_2023):,}' for r in brands.itertuples()],
        'change': [f'{r.change_pct:+.0f}%' for r in brands.itertuples()],
        'share of reviews': [f'{r.share_2022_pct:.0f}% → {r.share_2023_pct:.0f}%' for r in brands.itertuples()],
        'rating': [f'{r.avg_rating:.2f}' for r in brands.itertuples()]})
    st.dataframe(who, hide_index=True, width='stretch')
    st.caption(f'Brick-flower reviews written Jan-Sep. Other brands received {others.share_2023_pct:.0f}% of them in 2023. mart_flower_product_stats')

    with st.expander('All kinds of flower toy, compared with all toys'):
        table = view[['pattern', 'products', 'brands', 'reviews_2022_jan_sep', 'reviews_2023_jan_sep', 'relative_growth_index', 'avg_rating', 'low_rating_pct']]
        st.dataframe(table.rename(columns={'relative_growth_index': 'index_vs_all_toys'}), hide_index=True, width='stretch')
        st.caption('Index vs all toys = the change in reviews of a kind ÷ the change in all toy reviews. 1.00 = the same as the market.')

with tabs[1]:
    low = int(pains.low_reviews.iloc[0])
    st.subheader('Reviews point to improvement opportunities.')
    st.markdown(f'**% of {low:,} low-star reviews** of brick flowers')
    st.altair_chart(alt.Chart(pains).mark_bar(color=BLUE).encode(
        y=alt.Y('theme:N', sort='-x', title=None, axis=alt.Axis(labelLimit=320)), x=alt.X('share_of_low_reviews_pct:Q', title='%'),
        tooltip=['theme', 'low_mentions', 'products', 'brands', 'evidence']).properties(height=340), width='stretch')
    for col, row in zip(st.columns(3), pains.head(3).itertuples()):
        col.metric(row.theme, f'{row.share_of_low_reviews_pct:.0f}%', f'across {int(row.brands)} brands', delta_color='off')
    st.caption(f'All brick-flower reviews rated 1 or 2 stars (n = {low:,}). One review can mention several topics. mart_flower_theme_evidence')

with tabs[2]:
    st.subheader('Sell adult brick flowers, and fix what buyers complain about.')
    fixes = ['Checked counts, numbered bags', 'Sturdy stems', 'Clear instructions']
    for i, (fix, row) in enumerate(zip(fixes, pains.head(3).itertuples()), start=1):
        st.markdown(f'**{i}. {fix}**  \n{row.theme}: {row.share_of_low_reviews_pct:.0f}% of low-star reviews')
    st.markdown('**How:** better quality and easier to build.')
    st.info('Review activity suggests an opportunity. It does not prove sales. Next: check suppliers and test-sell.')

with tabs[3]:
    st.subheader('Is it still true on Amazon in 2026?')
    lists = q('select source, count(*) as product_families from project2_analytics.fact_keepa_snapshot group by 1')
    names = {'group': 'top sellers today', 'new': 'new since 2024', 'cohort': 'top products of 2023'}
    lists = lists.set_index('source').product_families
    st.markdown(f'**2026 sample: {int(lists.sum()):,} flower-toy product families** after filtering and merging variants, from three lists: '
                + ' + '.join(f'{int(lists[k]):,} {names[k]}' for k in names if k in lists) + '.')

    st.markdown('**1. Is rating activity still growing?**  New ratings, 1 Jan to 7 Oct: 2025 vs 2026, top 50 non-LEGO brick-flower products')
    x, y, z = st.columns(3)
    x.metric('2025', f'{int(g1.reviews_added_2025):,}')
    y.metric('2026', f'{int(g1.reviews_added_2026):,}')
    z.metric('Change', f'{g1.s1_reviews_2026_vs_2025_pct:+.0f}%')
    st.markdown('Yes. Almost three times as many new ratings.')

    st.markdown('**2. Have ratings improved?**')
    st.markdown(f'No change. For the 26 of those products that already had a rating a year ago, the mean was 4.46 then and 4.46 now. '
                f'This is a separate check on the saved snapshot, outside the pipeline. From the pipeline: the median rating of the 50 products today is {g1.rating_now_median:.1f}.')
    st.info('More rating activity; ratings unchanged. The evidence supports the direction: sell brick flowers and test quality improvements.')

    with st.expander('The same comparison for the other groups'):
        view = groups.copy()
        view['group'] = view.keepa_group.str[3:]
        view['is_brick'] = view.keepa_group.str.startswith('G1')
        st.altair_chart(alt.Chart(view).mark_bar().encode(
            y=alt.Y('group:N', sort='-x', title=None, axis=alt.Axis(labelLimit=320)),
            x=alt.X('s1_reviews_2026_vs_2025_pct:Q', title='Ratings added, 2026 vs 2025 (%)'),
            color=alt.Color('is_brick:N', scale=alt.Scale(domain=[True, False], range=[PURPLE, GREY]), legend=None),
            tooltip=['group', 'products_analyzed', 'reviews_added_2025', 'reviews_added_2026', alt.Tooltip('s1_reviews_2026_vs_2025_pct:Q', format='.0f')]).properties(height=300),
            width='stretch')
        st.dataframe(view[['group', 'products_analyzed', 'reviews_added_2025', 'reviews_added_2026', 's1_reviews_2026_vs_2025_pct', 'rating_now_median']],
                     hide_index=True, width='stretch')
    st.caption('2023 uses written reviews; 2026 uses rating counts. The 2026 sample is not the same set of products as 2023. mart_keepa_group_verdict')

with tabs[4]:
    st.subheader('Where these numbers come from')
    counts = q("""select (select count(*) from project2_analytics.dim_product) as products,
                         (select count(*) from project2_analytics.fact_reviews) as reviews,
                         (select count(*) from project2_analytics.dim_flower_product) as flower_toys,
                         (select count(*) from project2_analytics.dim_play_pattern) as kinds_of_flower_toy,
                         (select count(*) from project2_analytics.fact_keepa_snapshot) as amazon_2026_product_families""")
    st.dataframe(counts, hide_index=True, width='stretch')
    st.markdown("""
- **Pipeline:** Python + DuckDB, Meltano, BigQuery, dbt, Great Expectations, Dagster. This app reads the marts and adds no rules.
- **Checks before a number gets here:** 106 dbt tests, 24 Great Expectations rules, and a reconciliation of 10 result tables.
- **Limits:** reviews and ratings are not sales. One US marketplace. The review data ends in September 2023 and thins out after March 2023,
  so growth is always compared with all toys. The labels are rules checked on samples by hand, not a trained model.
- **More analysis** (reviews per month, top products, reviewer segments) is in `notebooks/flower_analysis.ipynb`.
""")
    st.caption(f'BigQuery project: {PROJECT}. Results are cached for one hour.')
