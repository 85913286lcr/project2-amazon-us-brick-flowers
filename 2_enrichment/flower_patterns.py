"""Step 2 - classify how each flower product is played with (multi-label + one primary pattern).

Input : duckdb/flower_enrichment.duckdb.flower_products (from flower_identify)
Output: table flower_core (analysis scope with play patterns), docs/evidence/enrichment/02_patterns_summary.json
Scope : T1 flower-as-object, T1i flower artwork, P plant-adjacent; party decor and apparel/jewellery
        are kept out of the toy scope but counted. T2/T4 stay as exploration context only.
"""
import json
import re
from pathlib import Path

import duckdb
import pandas as pd

from paths import EVIDENCE as OUT, WORK_DB as DB

NON_TOY = re.compile(r"\b(hat|cap|beanie|earrings?|pendant|necklace(?! (making|kit|craft))|bracelet(?! (making|kit|craft))|blanket|washcloth|"
                     r"bedding|socks?|shirt|t-shirt|leggings|swimsuit|hair clips?|barrettes?|phone case|keychain)\b")

# Ordered: the first matching pattern is the primary one; every match is kept as a label.
PATTERNS = [
    ('Flower-image puzzles & cards', r"__IMAGE__"),
    ('Toddler flower-garden stacking sets', r"flower garden.{0,40}(building|stacking|toys?|set|kit|playset)|build (a|your) (bouquet|garden)|garden building|stacking flowers?|flower (stacking|building) toy|count (&|and) stack flower|build (&|and) (spin|bloom)|floral arrangement (toy|playset)|flower arrangement (toy|playset)|(toddler|preschool|montessori).{0,60}flowers?.{0,30}(build|stack)"),
    ('Brick flower accessories (vase / lights / display)', r"(vase|light kit|lighting kit|led light|led lighting|display case|dust cover|display stand|acrylic).{0,60}(for|compatible with|fit) (lego|10280|10281|10309|10311|10289|10313|40460|40461|40646|40647)|for lego.{0,40}(bouquet|orchid|bonsai|succulent|flower|botanical)"),
    ('3D wooden & crystal models', r"^(?!.*(brick|blocks?)).*\b(3d|wooden|wood|crystal|metal)\b.{0,20}\b(puzzle|model|kit)\b|music box kit"),
    ('Brick flower bouquets & bonsai (adult display)', r"(lego|building|bricks?|blocks?|micro ?blocks?|mini ?blocks?|nano ?blocks?|moc\b|compatible).*(bouquet|bonsai|orchid|succulent|botanical|potted|plant|sakura|cherry blossom|rose|tulip|sunflower|lily|flowers?)|(bouquet|bonsai|orchid|succulent|botanical).*(building|bricks?|blocks?)"),
    ('Brick scenes (flower shop / garden)', r"(lego|building|bricks?|blocks?).*(shop|store|cart|garden|house|station|pavilion)"),
    ('Flower pressing', r"\bpress(ed|ing)?\b.{0,20}(flowers?|leaf|leaves)|flower press|leaf press"),
    ('Planting & science kits', r"\b(grow|growing|seeds?|planting|plant kit|gardening kit|terrarium|science kit|germinat|wildflower garden|crystal flower)\b"),
    ('Flower crown & jewellery crafts', r"(jewelry|bracelet|necklace|headbands?|crown|hair accessor).{0,30}(making|kit|craft|diy)|(make|making|diy).{0,30}(crowns?|bracelets?|headbands?|jewelry)"),
    ('Paint & decorate crafts', r"\b(paint|painting|color your own|decorate|sand art|sequin|mosaic|glitter|snow globe)\b.{0,40}(flowers?|pots?|vase|bouquet|rose)|(flowers?|pot|vase).{0,30}(paint|painting) kit"),
    ('Craft bouquets & paper flowers', r"\b(craft|crafts|kit|diy|make your own|felt|button|crepe|tissue paper|paper|pipe cleaners?|chenille|foam|clay|dough|crochet|knit|sequin)\b.{0,40}\b(flowers?|bouquets?|roses?|sunflowers?|tulips?|daisy|daisies|petals|succulents?|lily|lilies|orchids?|peony|peonies|lotus|blossoms?|carnations?|hydrangeas?|wildflowers?)\b|\b(flowers?|bouquets?|roses?|sunflowers?|tulips?|daisy|daisies|petals|succulents?|lily|lilies|orchids?|peony|peonies|lotus|blossoms?|carnations?|hydrangeas?|wildflowers?)\b.{0,40}\b(craft|crafts|kit|diy|making|maker)\b"),
    ('Solar dancing flowers & electronic', r"\b(solar|dancing|dancer|music box|light up|led|electronic|talking|singing|interactive|remote|robot)\b"),
    ('Flower plush & pillows', r"__PLUSH__"),
    ('Preserved & artificial flower gifts', r"rose bear|forever rose|preserved|eternal|everlasting|artificial|faux|fake flowers?|silk flowers?|glass dome|enchanted rose"),
    ('Dollhouse miniature flowers', r"(dollhouse|doll house|1:12|1/12|miniature|micro landscape).{0,60}(flowers?|roses?|tulips?|plants?|potted|bonsai|succulents?|bouquet|vase|flower ?bed|planter|hanging basket)|(flowers?|potted|plants?|bonsai|bouquet|vase|planter).{0,40}(dollhouse|doll house|1:12|1/12|miniature)"),
    ('Pretend play', r"pretend|playset|play set|florist|flower (shop|market|stand|cart)|tea party|garden tools?|role ?play"),
    ('Dress-up accessories', r"\b(crown|halo|wand|tiara|wig|costume|dress up|headband|lei)\b"),
    ('Magic & gag', r"\b(magic|trick|appearing|prank|gag)\b"),
    ('Bath, outdoor & water', r"\b(bath|sprinkler|water|pool|outdoor|bubble|kite|garden hose)\b"),
    ('Fidget & sensory', r"\b(fidget|squishy|pop it|sensory|stress|dimple|squeeze)\b"),
    ('Character plush with flower motif', r"\b(plush|plushie|stuffed|figure|figurine|doll|bear|bunny|unicorn|cat|dog|penguin|pikachu|monchhichi)\b"),
]
PLUSH_RE = re.compile(r"(flowers?|sunflowers?|tulips?|roses?|daisy|daisies|succulents?|cact(us|i)|potted|bouquet|lotus|orchids?|plants?)\s?(plush|plushie|pillow|stuffed)|(plush|plushie|stuffed|giant|jumbo)\s(flowers?|bouquet|sunflowers?|tulips?|roses?|daisy|succulents?|orchids?)")
CHARACTER_RE = re.compile(r"\b(rabbit|bunny|bear|cat|kitty|dog|puppy|penguin|pikachu|pok.mon|pusheen|miffy|husky|shiba|unicorn|bulborb|squish(y|ies)|mario|zombies?|duck|monkey|panda|fox|frog|bee|elephant|hello kitty)\b")
MINI_NOT_FLOWER = re.compile(r"\b(pigs?|piggy|ducks?|figurines?|figures?|benches?|couple|boat|oar|bed frame|beds?|chairs?|sofa|food|sandwich|dinner|potatoes|yams|cake|animals?|birds?|insects?|gnomes?|fairies)\b")
IMAGE_TIER = 'T1i flower artwork (puzzle / cards / stickers)'


def classify(r):
    t = r.title.lower() if isinstance(r.title, str) else ''
    labels = []
    for name, pat in PATTERNS:
        if pat == '__IMAGE__':
            if r.tier == IMAGE_TIER:
                labels.append(name)
        elif name == 'Dollhouse miniature flowers' and MINI_NOT_FLOWER.search(t):
            continue
        elif pat == '__PLUSH__':
            # The flower / plant itself is the plush; an animal or character holding a flower is a different toy.
            if PLUSH_RE.search(t) and (not CHARACTER_RE.search(t) or re.search(r"(flower|plant) ?pot", t)):
                labels.append(name)
        elif re.search(pat, t):
            labels.append(name)
    primary = labels[0] if labels else 'Other / unclassified'
    return pd.Series({'primary_pattern': primary, 'patterns': '|'.join(labels) or 'Other / unclassified'})


def main():
    con = duckdb.connect(str(DB))
    fp = con.execute("select * from flower_products").df()
    in_scope = fp.tier.str[:2].isin(['T1', 'P ']) & (fp.scope == 'toy')
    nontoy = fp.title.fillna('').str.lower().str.contains(NON_TOY)
    core = fp[in_scope & ~nontoy].copy()
    core = pd.concat([core, core.apply(classify, axis=1)], axis=1)
    # Plant-adjacent products only stay when the play pattern is botanical (bricks, grow, plush plant, miniature plants).
    not_floral = core.title.fillna('').str.lower().str.contains(r"butterfly|insect|caterpillar|ladybug|roly|ant farm|habitat|dancing cactus|talking cactus|singing cactus|mimic|repeat(s|ing)? what|pinata", regex=True)
    core = core[~((core.tier.str[:1] == 'P') & not_floral)]
    core = core[~((core.tier.str[:1] == 'P') & core.primary_pattern.isin(['Character plush with flower motif', 'Other / unclassified', 'Bath, outdoor & water', 'Flower-image puzzles & cards']))]
    core['relevance'] = core.tier.map(lambda x: 'core: flower is the play object' if x == 'T1 flower is the object' else ('core: flower artwork' if x == IMAGE_TIER else 'adjacent: plant or garden'))
    con.register('core_df', core)
    con.execute('create or replace table flower_core as select * from core_df')
    summary = {
        'recalled': len(fp),
        'excluded': {'party_decor': int((fp.scope == 'party').sum()), 'apparel_jewellery_in_T1P': int((in_scope & nontoy).sum()),
                     'T2_theme_element(exploration only)': int(((fp.tier.str[:2] == 'T2') & (fp.scope == 'toy')).sum()),
                     'T3_motif': int(((fp.tier.str[:2] == 'T3')).sum()), 'T4_description_only': int((fp.tier.str[:2] == 'T4').sum()),
                     'X_ambiguous': int((fp.tier.str[:1] == 'X').sum())},
        'core_products': len(core),
        'by_relevance': core.relevance.value_counts().to_dict(),
        'by_primary_pattern': core.primary_pattern.value_counts().to_dict(),
    }
    (OUT / '02_patterns_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
