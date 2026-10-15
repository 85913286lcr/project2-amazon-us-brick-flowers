"""Step 3 - read the raw review text of every in-scope flower product (no minimum review count).

Input : flower_core (flower_patterns) + raw reviews (Toys_and_Games.jsonl.gz in PROJECT2_RAW_DIR, read-only)
Output: tables flower_reviews, review_tags, product_stats, wish_sentences; docs/evidence/enrichment/03_codebook.json
Each review is tagged with a transparent regex codebook (multi-label). Wish sentences are extracted
separately so unmet needs come from what buyers explicitly say is missing.
"""
import json
import re
from pathlib import Path

import duckdb
import pandas as pd

from paths import EVIDENCE as OUT, RAW_REVIEWS, WORK_DB as DB

CODEBOOK = {
    'Motive: gifting': {
        'Bought as a gift': r"\b(gift|gifts|gifted|present)\b",
        'Gift for a partner': r"\b(wife|girlfriend|husband|boyfriend|fianc[eé]e?|spouse|partner)\b",
        'Gift for mom': r"\b(my (mom|mother|mum|mama)|for (mom|mother))\b",
        'Gift for grandparents': r"\b(grandma|grandmother|nana|grandpa|grandfather|mother.in.law)\b",
        'Gift for a girl': r"\b(daughter|granddaughter|niece|little girl|my girls)\b",
        'Gift for a boy': r"\b(son|grandson|nephew|little boy)\b",
        'Gift for friend / teacher / coworker': r"\b(teacher|teachers|coworker|co-worker|boss|friend|bestie|neighbor)\b",
        'Bought for themselves': r"\b(for myself|treat myself|bought (this|it|these) for me|i bought (this|it) for myself|as an adult)\b",
        'Birthday': r"\b(birthday|bday)\b",
        'Christmas & holidays': r"\b(christmas|xmas|stocking|holiday)\b",
        'Valentines Day': r"valentine",
        'Mothers Day': r"mother'?s day|mothers day",
        'Easter & spring': r"\b(easter|spring)\b",
        'Anniversary & wedding': r"\b(anniversary|wedding|bridal|engagement)\b",
        'Get well & sympathy': r"\b(get well|hospital|surgery|sympathy|funeral|memorial|passed away|in memory|grieving)\b",
        'Teacher appreciation & graduation': r"teacher appreciation|end of (the )?(school )?year|graduat",
        'Classroom & party group': r"\b(classroom|class|students|party favors?|goodie bags?|girl scouts?|troop|camp|vbs|sunday school)\b",
    },
    'Motive: value': {
        'Flowers that never wilt': r"never (die|wilt)|won'?t (die|wilt)|will not die|last(s)? forever|instead of (real|fresh) flowers|real flowers (die|wilt)|no water(ing)?|don'?t (need|have) to water|black thumb|kill (every )?(plants|flowers)|allerg",
        'Home or desk decor': r"\b(decor|display|displayed|shelf|desk|office|mantle|mantel|centerpiece|windowsill|nightstand|bookshelf)\b",
        'Relaxing, mindful build': r"\b(relax|relaxing|therapeutic|therapy|stress|calming|mindful|zen|meditat|anxiety)\b",
        'Built together with family': r"(together with|did (it|this) together|built (it )?together|made (it|them) together|bonding|family (activity|time|fun)|with (my|her|his) (mom|dad|daughter|son|kids|grand))",
        'Learning & fine-motor skills': r"\b(fine motor|educational|learn|learning|stem|creativity|imagination|counting|color recognition|hand.eye)\b",
        'Screen-free time': r"\b(screen time|kept (her|him|them) (busy|entertained|occupied)|keep (her|him|them) busy|rainy day|for hours|hours of fun)\b",
        'Loves flowers & gardening': r"(loves? flowers|flower lover|loves? (gardening|plants)|gardener|plant lady|plant lover|green thumb)",
        'Collecting a series': r"\b(collect|collection|collector|series|whole set)\b",
    },
    'Experience: making': {
        'Easy and fun to build': r"(easy to (build|assemble|put together|make|follow)|fun to (build|make|put together|assemble)|enjoyed (building|making|putting))",
        'Build time mentioned (hours)': r"(took (me|us|her|him|my \w+) (about |around |roughly )?(\d+|an?|one|two|three|several|a few) (hours?|evenings?|days?|nights?))|(\d+ hours? to (build|complete|finish|make))",
        'Sense of accomplishment': r"(proud|sense of accomplishment|satisfying|relaxing (to build|build|process)|enjoyed the (build|process)|therapeutic (build|process))",
        'Poor instructions': r"(instructions? (were|are|was|is) (hard|confusing|unclear|bad|terrible|poor|awful|difficult|useless|vague|tiny)|hard to follow|no instructions|couldn'?t follow|confusing instructions|instructions (were|are) (in )?(chinese|not in english)|poor instructions)",
        'Clear instructions': r"instructions (were|are|was|is) (clear|easy|great|good|simple|well)",
        'Missing pieces': r"\b(missing|didn'?t come with|not included|were not included|short (a|some|one|two))\b",
        'Tiny pieces, hard to press': r"(tiny pieces|small pieces|pieces (are|were) (so |very |too |really )?(small|tiny)|hard to (press|snap|push|connect|attach)|sore fingers|fingers hurt|tweezers|brick separator)",
        'Falls apart or droops': r"(fall(s|ing)? (apart|off|out)|fell (apart|off)|come(s)? apart|came apart|pop(s|ped)? off|won'?t stay|doesn'?t stay|keeps? falling|droop|sag|flimsy stems?|stems? (bend|broke|snap))",
        'Too hard, needed help': r"(too (hard|difficult|complicated) for|needed (my |a lot of |an adult'?s? )?help|had to help|frustrat|couldn'?t (do|figure|get) (it|them))",
        'Too easy, finished quickly': r"(too easy|done in (minutes|no time)|finished (it |them )?(in|within) (minutes|an hour|10|15|20|30)|over in (minutes|an hour)|only took (\d+|a few|ten|five) minutes)",
        'Messy glue or paint': r"\b(mess|messy|glue|sticky|paint (came|chip|peel|dried|is dry))\b",
        'Repetitive build': r"\b(repetitive|tedious|monotonous|boring to build)\b",
    },
    'Experience: display': {
        'Beautiful, realistic': r"\b(beautiful|gorgeous|stunning|realistic|looks? real|lifelike|so pretty|vibrant)\b",
        'Smaller than expected': r"(smaller than (i |we )?(expected|thought|pictured)|so small|too small|very small|expected (it |them )?(to be )?bigger|thought (it|they) would be bigger|tiny)",
        'Bigger than expected': r"(bigger than (i |we )?expected|larger than (i |we )?expected|great size|nice size|good size)",
        'Not as pictured': r"(not as pictured|doesn'?t look like the (picture|photo)|not like the (picture|photo)|misleading|colou?rs? (are|were|is|was) (off|different|dull|not)|faded|fade)",
        'Arrived broken or breaks easily': r"\b(broke|broken|cracked|snapped|fragile|damaged)\b",
        'Feels cheap': r"\b(cheap|cheaply|flimsy|poor quality|low quality|thin plastic)\b",
        'Vase or pot mentioned': r"\b(vase|vases|pot|pots|planter|base)\b",
        'Dust': r"\bdust(y|ing)?\b",
        'Lights': r"\b(lights?|led|lighting|glow)\b",
        'Seeds did not grow': r"(didn'?t (grow|sprout)|nothing (grew|sprouted)|seeds? (didn'?t|did not|never|won'?t) (grow|sprout|germinate)|never (grew|sprouted)|no sprouts?)",
        'Solar or electronics not working': r"(doesn'?t (work|move|dance|light)|stopped (working|moving|dancing)|only (works|moves|dances) in (direct |bright )?sun|needs? (direct|bright|strong) (sun|light)|dead on arrival)",
    },
    'Price': {
        'Good value': r"(worth (the|every)|great (value|price|deal)|good (value|price|deal)|for the price|affordable|inexpensive)",
        'Overpriced': r"(overpriced|too expensive|pricey|not worth|waste of money|price is (high|steep)|over ?priced)",
    },
}

WISH_MARK = (r"(\bi wish\b|\bwish (it|they|there|the|that)\b|would (be|have been) (nice|better|great|helpful|good|cool)|would love|\bif only\b|"
             r"should (have|come|include|be)|\bneeds? (a |an |to |more |better )|could (use|have been|be improved)|it would help|i hope (they|the|you)|"
             r"would have (liked|preferred|been)|didn'?t come with|doesn'?t come with|does not come with|did not come with|\bno (vase|pot|box|instructions|stand|base|lights?)\b|"
             r"suggest(ion)?|recommend (adding|that they)|only (complaint|downside|con|issue|negative|thing))")
NEEDS = {
    'Include a vase or pot': r"\b(vases?|flower ?pots?|planters?)\b|\bpots?\b(?! of)",
    'Stable base': r"(\bstand\b|\bbase\b|weighted|tip(s|ped)? over|topple|stable|stability|lean(s|ing)?)",
    'More flowers, fuller look': r"(more (flowers|stems|blooms|petals|variety|kinds|types|of (them|these))|\b(bigger|larger|fuller|taller)\b)",
    'Clearer instructions or video': r"(instructions?|manual|directions|diagram|video|tutorial)",
    'Numbered bags and spare parts': r"(numbered|label(l)?ed|sorted|separate bags|bags (were|are) not|organized by|spare|extra pieces|replacement (pieces|parts))",
    'Sturdier stems and joints': r"(sturdier|stronger|\bstems?\b|stay (together|in place|up)|hold (together|up|better)|fall(s|ing)? (apart|off|over)|tighter|clutch|droop)",
    'Colour options, more realistic': r"(colou?r (options?|choices?|variety)|more colou?rs|different colou?rs|realistic|look(s)? (more )?real)",
    'Lights': r"(\bled\b|\blights?\b(?! ?(weight|green|pink|blue|purple|brown))|lit up|light up|\bglow)",
    'Gift box or card': r"(gift box|gift bag|gift wrap|nicer box|better box|nice box|box (was|is|came) (damaged|crushed|broken|flimsy|open)|packaging|presentation|greeting card|card (to|for) (write|attach))",
    'More material': r"(more (material|supplies|paint|felt|beads|seeds|soil|glue|paper|wire|petals|leaves|dough|clay)|enough (material|supplies|paint|felt|seeds|for (each|every|two|both|all)))",
    'Seeds that actually grow': r"(didn'?t (grow|sprout)|\bseeds?\b|sprout|germinat|\bsoil\b|grow (better|faster))",
    'Difficulty matched to age': r"(too (hard|difficult|easy|complicated)|younger|older kids|easier|simpler|challeng)",
    'Better durability': r"(better quality|poor quality|cheap(ly)?|flimsy|broke|durable|sturdy)",
    'No-glue assembly': r"(\bglue|adhesive|sticky|stick (better|together))",
    'Storage box': r"(storage|\bcase\b|container|organiz)",
    'Dust cover or display case': r"(dust|display case|glass cover|acrylic|\bcover\b|dome)",
    'Volume & sound control': r"(volume|loud|\bsounds?\b|songs|music)",
    'Lower price': r"(cheaper|less expensive|overpriced|price (is|was) (high|steep)|not worth)",
    'Solar & battery': r"(solar|batter(y|ies)|direct sun|sunlight)",
    'Clear size information': r"(dimension|measurement|size (listed|info)|how (big|small)|smaller than (i |we )?(expected|thought|pictured)|too small|so small)",
    'Add-on packs to complete a bouquet': r"(another set|more sets|buy (a couple|more|another|two)|full bouquet|more arrangements|add.?ons?|expansion|more than (just )?one of each|connector pieces|more pieces)",
    'Hidden wires & battery box': r"(wires?|cables?|power box|battery box|cord).{0,40}(hide|hidden|visible|show|messy)|(hide|hidden|conceal).{0,30}(wires?|cables?|battery|cord)",
    'Scent': r"\b(scent|scented|smell|fragrance)\b",
    'Reusable, can be rebuilt': r"(reusable|rebuild|take (it )?apart|again and again|over and over|refill)",
}


def main():
    con = duckdb.connect(str(DB))
    con.execute(f"""create or replace table flower_reviews as
      select r.parent_asin, r.asin, r.rating, r.title r_title, r.text, r.user_id, to_timestamp(r.timestamp/1000) ts,
             r.helpful_vote, r.verified_purchase, c.primary_pattern, c.relevance, c.brand,
             lower(coalesce(r.title,'')||' . '||coalesce(r.text,'')) txt
      from read_json('{RAW_REVIEWS}', format='newline_delimited',
             columns={{'rating':'DOUBLE','title':'VARCHAR','text':'VARCHAR','asin':'VARCHAR','parent_asin':'VARCHAR','user_id':'VARCHAR',
                       'timestamp':'BIGINT','helpful_vote':'BIGINT','verified_purchase':'BOOLEAN'}}) r
      join flower_core c using(parent_asin)""")
    cols = []
    for grp, d in CODEBOOK.items():
        for tag, pat in d.items():
            cols.append(f"regexp_matches(txt, '{pat.replace(chr(39), chr(39) * 2)}') as \"{grp}|{tag}\"")
    con.execute(f"create or replace table review_tags as select parent_asin, rating, ts, primary_pattern, brand, {', '.join(cols)} from flower_reviews")
    con.execute("""create or replace table product_stats as
      select c.parent_asin, c.title, c.brand, c.primary_pattern, c.patterns, c.relevance, c.price, c.average_rating meta_rating, c.rating_number meta_rating_count,
             c.d_first_available, c.d_bsr, c.d_pieces, c.d_age, c.cat2, c.cat3,
             count(r.rating) review_count, avg(r.rating) review_avg, 100.0*avg(case when r.rating<=2 then 1 else 0 end) low_pct,
             count(*) filter (where year(r.ts)=2023 and month(r.ts)<=9) rv23, count(*) filter (where year(r.ts)=2022 and month(r.ts)<=9) rv22,
             count(*) filter (where year(r.ts)=2021 and month(r.ts)<=9) rv21,
             min(r.ts) first_review, max(r.ts) last_review,
             case when count(r.rating)>=30 then 'strong (30+ reviews)' when count(r.rating)>=5 then 'medium (5-29 reviews)' when count(r.rating)>=1 then 'weak (1-4 reviews)' else 'no reviews (metadata only)' end evidence_level
      from flower_core c left join flower_reviews r using(parent_asin) group by all""")
    # Wish sentences: split each review into sentences and keep those carrying an explicit wish / missing marker.
    rows = con.execute(f"select parent_asin, rating, ts, primary_pattern, brand, txt from flower_reviews where regexp_matches(txt, '{WISH_MARK.replace(chr(39), chr(39) * 2)}')").fetchall()
    wish_re, out = re.compile(WISH_MARK), []
    for asin, rating, ts, pat, brand, txt in rows:
        for sent in re.split(r'(?<=[.!?])\s+|<br\s*/?>|\n', txt):
            if wish_re.search(sent) and 15 <= len(sent) <= 400:
                needs = [k for k, p in NEEDS.items() if re.search(p, sent)]
                out.append((asin, rating, ts, pat, brand, sent.strip(), '|'.join(needs) or 'Uncategorised'))
    wish = pd.DataFrame(out, columns=['parent_asin', 'rating', 'ts', 'primary_pattern', 'brand', 'sentence', 'needs'])
    con.register('wish_df', wish)
    con.execute('create or replace table wish_sentences as select * from wish_df')
    (OUT / '03_codebook.json').write_text(json.dumps({'codebook': CODEBOOK, 'wish_marker': WISH_MARK, 'need_categories': NEEDS}, ensure_ascii=False, indent=2))
    s = con.execute("select count(*), count(distinct parent_asin) from flower_reviews").fetchone()
    p = con.execute("select evidence_level, count(*) from product_stats group by 1 order by 1").fetchall()
    print({'reviews': s[0], 'products_with_reviews': s[1], 'evidence_levels': p, 'wish_sentences': len(wish),
           'wish_reviews': len(rows)})


if __name__ == '__main__':
    main()
