"""Keepa product groups and the Product Finder queries used to find them. Shared by the fetch and build steps."""

# Finder matches all keywords of a query (AND), so each group is the union of several queries.
GROUPS = {
    'G1 Adult brick flowers (non-LEGO)': ['flower building blocks', 'bouquet building', 'botanical building', 'bonsai building blocks',
                                          'succulent building blocks', 'flower building set'],
    'G2 LEGO flower sets': ['lego botanicals', 'lego botanical', 'lego flower', 'lego bouquet'],
    'G3 Toddler flower-garden sets': ['flower garden building', 'build bouquet', 'flower garden stacking'],
    'G4 Flower crafts': ['flower craft kit', 'bouquet craft kit', 'felt flower', 'paper flower kit', 'flower press kit', 'flower crown kit'],
    'G5 Planting kits': ['flower growing kit', 'paint plant flower', 'flower garden kit'],
    'G6 Flower plush': ['flower plush', 'succulent plush', 'sunflower plush', 'tulip plush'],
    'G7 Solar dancing flowers': ['solar dancing flower', 'solar flower'],
}
GROUP_BY_ID = {name[:2]: name for name in GROUPS}
OTHER_GROUP = 'Other / not a target pattern'
DIY_GROUP_IDS = ('G1', 'G2', 'G3', 'G4', 'G5')
COUNT_QUERIES = {g: q[:2] for g, q in GROUPS.items()}          # "sells 100+ a month" counts
NEW_WORDS = ['flower', 'flowers', 'floral', 'bouquet', 'blossom', 'rose', 'roses', 'tulip', 'sunflower', 'orchid', 'succulent',
             'bonsai', 'lily', 'daisy', 'lotus', 'peony', 'botanical', 'botanicals', 'plant', 'plants']

# 2023 play pattern -> group
PATTERN_TO_GROUP = {
    'Brick flower bouquets & bonsai (adult display)': 'G1', 'Brick scenes (flower shop / garden)': 'G1',
    'Toddler flower-garden stacking sets': 'G3',
    'Craft bouquets & paper flowers': 'G4', 'Paint & decorate crafts': 'G4', 'Flower crown & jewellery crafts': 'G4',
    'Flower pressing': 'G4', '3D wooden & crystal models': 'G4',
    'Planting & science kits': 'G5', 'Flower plush & pillows': 'G6', 'Solar dancing flowers & electronic': 'G7',
}
