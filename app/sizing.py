import re

CLOTHING_LADDER = {
    'XXS': 0, 'XS': 1, 'S': 2, 'M': 3, 'L': 4, 'XL': 5,
    'XXL': 6, '2XL': 6, '3XL': 7,
}

LEGGINGS_LADDER = {
    'OS': 0, 'T/C': 1, 'TC': 1, 'T/C2': 2, 'TC2': 2,
}

DRESS_NUMERIC_LADDER = {
    str(n): i for i, n in enumerate(range(0, 30, 2))
}

DENIM_NUMERIC_LADDER = {
    str(n): i for i, n in enumerate(range(24, 48, 2))
}

KIDS_LADDER = {
    '2': 0, '4': 1, '6': 2, '8': 3, '10': 4, '12': 5, '14': 6,
    'S': 0, 'M': 1, 'L': 2,
}

FAMILY_LADDERS = {
    'clothing': CLOTHING_LADDER,
    'leggings': LEGGINGS_LADDER,
    'dress_numeric': DRESS_NUMERIC_LADDER,
    'kids': KIDS_LADDER,
    'denim': DENIM_NUMERIC_LADDER,
}

KIDS_STYLES = {
    'sloan', 'mae', 'gracie', 'dot dot smile', 'azure kids',
    'sariah', 'adeline', 'disney kids',
}

LEGGINGS_TOKENS = {'os', 't/c', 'tc', 't/c2', 'tc2'}


def normalize_size(size_token):
    s = size_token.strip().upper()
    s = s.replace('T/C 2', 'T/C2').replace('TC 2', 'TC2')
    return s


def classify_family(product_style, size_token):
    style_lower = (product_style or '').lower()
    size_norm = normalize_size(size_token)
    size_lower = size_norm.lower()

    if size_lower in LEGGINGS_TOKENS or 'legging' in style_lower:
        return 'leggings'

    for kid_style in KIDS_STYLES:
        if kid_style in style_lower:
            return 'kids'

    if re.match(r'denim', style_lower):
        return 'denim'

    if re.match(r'^\d+$', size_norm) and size_norm not in CLOTHING_LADDER:
        return 'dress_numeric'

    return 'clothing'


def size_to_ordinal(size_token, family):
    ladder = FAMILY_LADDERS.get(family, CLOTHING_LADDER)
    size_norm = normalize_size(size_token)
    return ladder.get(size_norm)


def ordinal_to_size(ordinal, family):
    ladder = FAMILY_LADDERS.get(family, CLOTHING_LADDER)
    for token, val in ladder.items():
        if val == ordinal:
            return token
    return None


def available_sizes_for_family(family):
    ladder = FAMILY_LADDERS.get(family, CLOTHING_LADDER)
    seen = {}
    for token, val in ladder.items():
        if val not in seen:
            seen[val] = token
    return sorted(seen.items(), key=lambda x: x[0])


PRODUCT_FAMILIES = ['Top', 'Skirt', 'Long Pants', 'Short Pants', 'Dress', 'Athleisure']

_PRODUCT_FAMILY_RULES = [
    ('Athleisure', {'legging', 'jogger', 'serena', 'athleisure'}),
    ('Short Pants', {'monroe', 'shorts', 'short pant', 'bermuda'}),
    ('Long Pants', {'maurine', 'palazzo', 'jean', 'denim', 'trouser', 'sashay pant'}),
    ('Dress', {'carly', 'julia', 'nicole', 'joy', 'jade', 'nicki', 'dani', 'dress'}),
    ('Skirt', {'cassie', 'azure', 'madison', 'lola', 'lucy', 'mimi', 'maxi', 'skirt', 'ivy'}),
]


def classify_product_family(product_name, product_style, sizing_family=None):
    if sizing_family == 'leggings':
        return 'Athleisure'
    if sizing_family == 'denim':
        return 'Long Pants'
    text = ' '.join(filter(None, [product_name, product_style])).lower()
    for family, keywords in _PRODUCT_FAMILY_RULES:
        if any(kw in text for kw in keywords):
            return family
    return 'Top'
