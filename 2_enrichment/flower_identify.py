"""Step 1 - identify flower-related toys straight from the raw Amazon 2023 metadata.

Reads meta_Toys_and_Games.jsonl.gz from PROJECT2_RAW_DIR (read-only), recalls every product whose
title / features / description / categories / details mention a flower term, then
assigns a relevance tier. No review-count or age filter is applied.
Output: duckdb/flower_enrichment.duckdb (table flower_products), docs/evidence/enrichment/01_identify_summary.json
"""
import json
import re
from pathlib import Path

import duckdb
import pandas as pd

from paths import EVIDENCE as OUT, RAW_META, WORK_DB

# Flower lexicon (recall). Plant-adjacent words are tracked separately, not as flowers.
FLOWER = (r"flowers?|floral|florist|bouquets?|blossoms?|blooms?|blooming|petals?|roses?|tulips?|daisy|daisies|"
          r"sunflowers?|lily|lilies|orchids?|lotus|peony|peonies|lavender|carnations?|hydrangeas?|dahlias?|"
          r"daffodils?|popp(?:y|ies)|magnolias?|chrysanthemums?|hibiscus|plumerias?|jasmine|marigolds?|"
          r"wildflowers?|cherry blossoms?|sakura|camellias?|gardenias?|lilac|wisteria|poinsettias?|bird of paradise")
PLANT_ADJ = r"succulents?|cact(?:us|i)|bonsai|potted plants?|botanical|terrarium|fairy garden"

# Phrases where a flower word is a colour, a character, a brand or a non-flower thing.
AMBIGUOUS = [r"rose gold", r"rose ?pink", r"dusty rose", r"rose red", r"rose quartz", r"lavender (purple|color|colour|blue|grey|gray)",
             r"\blilac (color|colour|purple)", r"daisy duck", r"princess daisy", r"\bdaisy\b(?=.*\b(mario|luigi|peach|yoshi)\b)",
             r"springflower", r"spring flower toys", r"flower girl", r"piranha plant", r"cauliflower", r"mayflower",
             r"lotus (evija|exige|elise|evora|emira|car)", r"powerpuff", r"blossom,? bubbles", r"shopkins", r"\bbloom\b(?=.*winx)",
             r"steven universe", r"\blily\b(?=.*(baby alive|lol|l\.o\.l|na na|hatchimal|doll\b))", r"briar rose",
             r"rose (the|from) ", r"guns n.? roses", r"orchid seed", r"lotus\.flower", r"littlest pet shop.*", r"\blps\b.*", r"\blps\b",
             r"\b(flowers?|floral|rose|daisy|sunflower) (dress|dresses|headbands?|eyes?|pattern|print|handbag|purse|bag|kitten|outfit|hair ?clips?|earrings?|rug|mat|cushion cover)\b",
             r"\bwith (a |yellow |pink |white |red |purple |blue )?(flowers?|rose|daisy) (headband|dress|crown|eyes?|hat|bow|clip)\b",
             r"\b(roses|floral|flower) (rug|carpet|tea ?cups?|tea set|washcloth|blanket|bedding|dice)\b"]
AMBIG_RE = re.compile('|'.join(AMBIGUOUS))
FLOWER_RE = re.compile(rf"\b({FLOWER})\b")
# Plant-adjacent tier is stricter than recall: terrarium / fairy garden decor is usually not floral.
PLANT_RE = re.compile(r"\b(succulents?|cact(?:us|i)|bonsai|potted plants?|botanical)\b")
# Flower used as a print / motif rather than the object of play.
MOTIF_RE = re.compile(rf"\b(floral|flower|flowers|rose|daisy|sunflower|hibiscus|cherry blossom)[ -](print|pattern|design|patterned|shaped|motif|"
                      rf"embroidered|lace|accents?|details?|decorations? on|theme[d]? (dress|outfit|party))|"
                      rf"\bfloral\b(?! (craft|kit|arrangement|bouquet|toy|garden|foam))|"
                      rf"\bwith (a )?(little |small |pink |white )?(flower|flowers|rose)\b(?! (bouquet|garden|kit|craft))")
# Flower is clearly the thing being built / made / grown / cuddled / displayed.
OBJECT_RE = re.compile(rf"\b({FLOWER})\b.{{0,25}}\b(bouquets?|kit|kits|craft|crafts|building|bricks?|blocks?|toy|toys|plush|plushie|"
                       rf"stuffed|pillow|garden|pots?|press|crowns?|music box|model|shop|market|cart|arrangement|making|maker|seeds?|grow|growing|"
                       rf"stacking|squishy|fidget|wreath|vase|basket|headbands? making|dancer|dancing|playset)\b|"
                       rf"\b(build|make|making|grow|growing|plant|paint|create|arrange|press|pressed|crochet|knit|felt|paper|pipe cleaner|artificial|fake|"
                       rf"preserved|eternal|forever|everlasting|plush|stuffed|dancing|solar|wooden|3d|diy|mini|micro|miniature|potted)\b.{{0,25}}\b({FLOWER})\b|"
                       rf"\bbouquets?\b|\bflower (garden|shop|market|crown|press|pot|kit|craft|toy|plush|cart|stand toy)\b|\bflorist\b")
# Flowers only as artwork on a flat game/puzzle/card/sticker: its own group, play mechanics unrelated to flowers.
IMAGE_RE = re.compile(r"\b(jigsaw|puzzles?|playing cards?|card deck|deck of cards|bridge (tallies|set|gift)|tallies|stamps?|stickers?|tcg|yu-gi-oh|magic: the gathering|"
                      r"mtg|pokemon card|vanguard|trading card|color by numbers?|paint by numbers?|diamond painting|coloring)\b")
FLORAL_ADJ = re.compile(r"\bfloral\b(?! (arrangement|bouquet|foam|craft|kit))")
NON_TOY_CATS = {'Party Supplies'}  # flower party decor / leis: counted but kept out of the toy scope


def recall(con):
    con.execute(f"""create table meta as
      select parent_asin, title, main_category, categories, average_rating, rating_number, price, store, features, description,
             details,
             lower(coalesce(title,'')) t_title,
             coalesce(lower(array_to_string(features,' ')),'') t_feat,
             coalesce(lower(array_to_string(description,' ')),'') t_desc,
             lower(coalesce(details->>'Theme','')||' '||coalesce(details->>'Style','')||' '||coalesce(details->>'Pattern','')||' '||coalesce(details->>'Occasion','')) t_det
      from read_json('{RAW_META}', format='newline_delimited',
        columns={{'parent_asin':'VARCHAR','title':'VARCHAR','main_category':'VARCHAR','categories':'VARCHAR[]','average_rating':'DOUBLE',
                  'rating_number':'BIGINT','price':'VARCHAR','store':'VARCHAR','features':'VARCHAR[]','description':'VARCHAR[]','details':'JSON'}})""")
    total = con.execute("select count(*) from meta").fetchone()[0]
    pat = FLOWER + '|' + PLANT_ADJ
    df = con.execute(f"""select * exclude(details),
        details->>'Brand' d_brand, details->>'Manufacturer' d_manufacturer, details->>'Brand Name' d_brand_name,
        details->>'Theme' d_theme, details->>'Number of Pieces' d_pieces, details->>'Manufacturer recommended age' d_age,
        details->>'Date First Available' d_first_available, details->>'Best Sellers Rank' d_bsr, details->>'Material' d_material
      from meta where regexp_matches(t_title||' '||t_feat||' '||t_desc||' '||t_det||' '||coalesce(lower(array_to_string(categories,' ')),''), '\\b({pat})\\b')""").df()
    return total, df


def brand_of(r):
    for v in (r.d_brand, r.d_brand_name, r.store, r.d_manufacturer):
        if isinstance(v, str) and v.strip() and v.strip().lower() not in ('unknown', 'generic', 'n/a', 'none'):
            return re.sub(r'[^a-z0-9]+', ' ', v.lower()).strip()
    return None


NAME_RISK = re.compile(r"\b(daisy|lily|rose|poppy|jasmine|sakura|blossom|petal|lotus|dahlia|magnolia|camellia|lilac|lavender|bloom|iris|violet|marigold|gardenia)\b")
FLOWER_CONTEXT = re.compile(r"\b(flowers?|floral|bouquets?|garden|gardening|plants?|petals|stems?|vase|pot|pots|potted|bloom(ing|s)?|blossoms|"
                            r"roses|daisies|lilies|poppies|tulips?|sunflowers?|orchids?|cherry blossoms?|botanical|florist|seeds?|wreath)\b")
SAFE_WORDS = re.compile(r"\b(flowers?|floral|florist|bouquets?|tulips?|sunflowers?|orchids?|peony|peonies|carnations?|hydrangeas?|daffodils?|"
                        r"chrysanthemums?|hibiscus|plumerias?|wildflowers?|cherry blossoms?|wisteria|poinsettias?|roses|daisies|lilies|poppies|"
                        r"blossoms|petals|bird of paradise)\b")


def flower_in(text):
    """True when the text names a flower as a flower (not as a character, person or colour)."""
    text = AMBIG_RE.sub(' ', text)
    if SAFE_WORDS.search(text):
        return True
    return bool(NAME_RISK.search(text) and FLOWER_CONTEXT.search(NAME_RISK.sub(' ', text)))


def tier(r):
    title = AMBIG_RE.sub(' ', r.t_title)
    body = AMBIG_RE.sub(' ', r.t_feat + ' ' + r.t_desc)
    in_title = flower_in(title)
    body_hits = len(SAFE_WORDS.findall(body))
    plant = bool(PLANT_RE.search(title))
    cat2 = r.categories[1] if r.categories is not None and len(r.categories) > 1 else None
    title_obj = FLORAL_ADJ.sub(' ', title)
    if in_title and IMAGE_RE.search(title) and not re.search(r"3d|wooden (flower|rose)|building", title):
        t = 'T1i flower artwork (puzzle / cards / stickers)'
    elif in_title and flower_in(title_obj) and OBJECT_RE.search(title_obj):
        t = 'T1 flower is the object'
    elif in_title and MOTIF_RE.search(title) and body_hits < 3:
        t = 'T3 floral print or motif'
    elif in_title:
        t = 'T2 flower is a theme element' if body_hits >= 1 or 'flower' in r.t_det else 'T3 floral print or motif'
    elif plant:
        t = 'P plant-adjacent (succulent / bonsai / garden)'
    elif body_hits >= 3:
        t = 'T4 description-only mention (weak lead)'
    else:
        t = 'X ambiguous or incidental'
    party = cat2 in NON_TOY_CATS or bool(re.search(r"\b(leis?|hawaiian|luau|party (favors?|decorations?|supplies)|centerpieces?|cake topper|balloons?|tissue paper pom|backdrop|banner)\b", r.t_title))
    return pd.Series({'tier': t, 'scope': 'party' if party else 'toy', 'cat2': cat2,
                      'cat3': r.categories[2] if r.categories is not None and len(r.categories) > 2 else None,
                      'title_flower_terms': ','.join(sorted(set(FLOWER_RE.findall(title)))), 'body_flower_hits': body_hits})


def main():
    con = duckdb.connect()
    total, df = recall(con)
    df = pd.concat([df, df.apply(tier, axis=1)], axis=1)
    df['brand'] = df.apply(brand_of, axis=1)
    df['price'] = pd.to_numeric(df.price, errors='coerce')
    out = df.drop(columns=['t_title', 't_feat', 't_desc', 't_det'])
    branch = duckdb.connect(str(WORK_DB))
    branch.register('out_df', out)
    branch.execute('create or replace table flower_products as select * from out_df')
    branch.close()
    summary = {'raw_products': int(total), 'recalled': int(len(df)),
               'by_tier_scope': df.groupby(['tier', 'scope']).size().rename('n').reset_index().to_dict('records')}
    (OUT / '01_identify_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
