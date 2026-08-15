"""What your wardrobe is made of, and what it's missing.

The spectrum shows the palette. This reads it: how concentrated it is, whether
there are anchors to build on and accents to build with, whether anything sits
in the middle of the lightness range, and which pieces earn their place by
pairing with everything.

All arithmetic. Nothing here calls a model, so it costs nothing to run and
gives the same answer twice.
"""

import math
import re
from collections import Counter

from utils.color_theory import NEUTRAL_CHROMA, harmony, lch
from utils.color_utils import hex_for

# Garment categories, matched against the model's free-text `type`. Ordered
# so the more specific patterns win: "denim jacket" is outerwear, not a bottom.
CATEGORIES = [
    ("outerwear", r"coat|jacket|blazer|parka|overcoat|windbreaker|hoodie|cardigan|gilet|\bvest\b"),
    ("footwear",  r"shoe|sneaker|trainer|boot|sandal|loafer|heel|flip.?flop|slipper|cleat"),
    ("accessory", r"\bhat\b|\bcap\b|beanie|scarf|glove|belt|\bbag\b|backpack|watch|sunglass|"
                  r"eyeglass|\bglasses\b|eyewear|spectacle|earbud|headphone|jewel|necklace|"
                  r"bracelet|\bring\b|\bsock|\btie\b|wallet"),
    # "shorts" plural only: \bshort\b also matches "short-sleeved", which
    # filed every short-sleeved jersey as a bottom.
    ("bottom",    r"trouser|\bpant|jean|\bshorts\b|skirt|chino|legging|jogger|slack|cargo|pyjama|pajama"),
    ("full",      r"dress|jumpsuit|romper|\bsuit\b|overall|kurta|anarkali|sherwani|saree|sari|"
                  r"salwar|kameez|lehenga|abaya|thobe|kaftan|caftan|\brobe\b"),
    ("top",       r"shirt|\btee\b|t.?shirt|\btop\b|blouse|sweater|jumper|knit|polo|jersey|"
                  r"tank|sweatshirt|pullover|tunic|kurti"),
]

ESSENTIAL = ["top", "bottom", "outerwear", "footwear"]

# What can sensibly be worn with what. A shirt doesn't pair with a shirt,
# and nothing goes under a dress.
WEARS_WITH = {
    "top":       {"bottom", "outerwear", "footwear", "accessory"},
    "bottom":    {"top", "outerwear", "footwear", "accessory"},
    "outerwear": {"top", "bottom", "full", "footwear", "accessory"},
    "full":      {"outerwear", "footwear", "accessory"},
    "footwear":  {"top", "bottom", "full", "outerwear", "accessory"},
    "accessory": {"top", "bottom", "full", "outerwear", "footwear", "accessory"},
    "other":     {"top", "bottom", "full", "outerwear", "footwear", "accessory"},
}

# How a slot is named when telling someone what to wear with something.
SLOT_LABEL = {
    "top": "Tops", "bottom": "Bottoms", "outerwear": "Layers",
    "footwear": "Shoes", "accessory": "Accessories", "full": "One-pieces",
    "other": "Other",
}


def wears_with(slot_a, slot_b):
    return slot_b in WEARS_WITH.get(slot_a, set())

# Materials grouped by what they actually do on a given day.
MATERIAL_ROLES = {
    "warm":       r"wool|cashmere|fleece|down|shearling|flannel|corduroy|tweed|thermal|knit",
    "breathable": r"cotton|linen|chambray|jersey|mesh|bamboo|rayon|viscose",
    "weather":    r"nylon|gore|waterproof|shell|polyester|leather|denim|canvas|water.?resistant",
}


# Words that describe a garment but don't identify it, so they're dropped
# when working out whether two rows are the same physical item.
_MODIFIERS = {
    "sleeveless", "short", "long", "sleeved", "sports", "sport", "athletic",
    "casual", "formal", "fitted", "loose", "relaxed", "slim", "straight",
    "cropped", "oversized", "light", "dark", "plain", "graphic", "printed",
    "striped", "patterned", "a", "an", "the", "of", "with", "and", "pair",
}


def _head_noun(item):
    """The noun that names the garment — 'sleeveless sports t-shirt' -> 'shirt'.

    Trailing plurals are stripped so 'wireless earbud' and 'wireless earbuds'
    are the same thing. The result only has to be *consistent*, not correct
    English: 'shorts' becoming 'short' is fine because both sides get it.
    """
    words = re.sub(r"[^a-z ]", " ", (item.get("type") or "").lower()).split()
    kept = [w for w in words if w not in _MODIFIERS and len(w) > 1]
    noun = kept[-1] if kept else (words[-1] if words else "")
    if len(noun) > 3 and noun.endswith("s") and not noun.endswith("ss"):
        noun = noun[:-1]
    return noun


# Coarse fabric families. The model describes the same garment's material
# differently in every photo -- "Synthetic fabric", "Woven synthetic fabric",
# "synthetic" -- so an exact string match never collapsed them.
_MATERIAL_FAMILIES = (
    ("leather",   r"leather|suede|shearling"),
    ("denim",     r"denim"),
    ("wool",      r"wool|cashmere|merino|tweed|flannel"),
    ("silk",      r"silk|satin"),
    ("linen",     r"linen"),
    ("metal",     r"metal|steel|silver|gold|brass|alloy"),
    ("plastic",   r"plastic|acetate|resin"),
    ("synthetic", r"polyester|nylon|synthetic|spandex|elastane|acrylic|fleece|poly"),
    ("cotton",    r"cotton|jersey|chambray|canvas|knit|twill|pique|piqué"),
)


def _material_family(item):
    """The fabric family named earliest in the description, or None.

    Earliest wins so "Cotton or fleece blend" reads as cotton while
    "Synthetic woven material" reads as synthetic. None means unknown,
    which matches anything rather than blocking a merge.
    """
    text = (item.get("material") or "").strip().lower()
    if not text:
        return None
    hits = []
    for family, pattern in _MATERIAL_FAMILIES:
        found = re.search(pattern, text)
        if found:
            hits.append((found.start(), family))
    return min(hits)[1] if hits else None


def dedupe_pieces(items):
    """Collapse the same physical garment photographed in several outfits.

    A shirt worn in four photos is four ClothingItem rows, which inflates
    every count and puts the same piece in a packing list twice.

    Two rows are one garment when they share a head noun, their colours are
    perceptually close, and their fabric families don't contradict — an
    unknown material never blocks a merge, because the model frequently
    omits it in one photo and names it in the next.

    Returns representatives, each carrying a ``copies`` count.
    """
    from utils.color_theory import distance
    from utils.color_utils import hex_for

    clusters = []
    for item in (items or []):
        if not item:
            continue
        noun = _head_noun(item)
        family = _material_family(item)
        item_hex = hex_for(item)

        for cluster in clusters:
            if cluster["noun"] != noun:
                continue
            if distance(cluster["hex"], item_hex) >= 0.08:
                continue
            # Contradicting fabrics mean different garments; an unknown on
            # either side is not a contradiction.
            if cluster["family"] and family and cluster["family"] != family:
                continue
            cluster["members"].append(item)
            if cluster["family"] is None:
                cluster["family"] = family
            break
        else:
            clusters.append({"noun": noun, "family": family,
                             "hex": item_hex, "members": [item]})

    def represent(cluster):
        """Keep whichever row the model described most fully."""
        best = max(cluster["members"],
                   key=lambda i: sum(1 for f in ("material", "brand", "key_features",
                                                 "overall_vibe", "short_description")
                                     if i.get(f)))
        return {"item": best, "members": cluster["members"],
                "noun": cluster["noun"], "family": cluster["family"],
                "hex": hex_for(best)}

    groups = [represent(c) for c in clusters]

    # A single greedy pass is order-dependent: two clusters can form around
    # different seeds and still end up within merging distance. Consolidate
    # on the *representatives* — comparing seeds missed pairs whose chosen
    # representative was a different member with a different colour.
    merging = True
    while merging:
        merging = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                a, b = groups[i], groups[j]
                if (a["noun"] == b["noun"]
                        and distance(a["hex"], b["hex"]) < 0.08
                        and not (a["family"] and b["family"] and a["family"] != b["family"])):
                    combined = {"noun": a["noun"],
                                "family": a["family"] or b["family"],
                                "members": a["members"] + b["members"]}
                    groups[i] = represent(combined)
                    del groups[j]
                    merging = True
                    break
            if merging:
                break

    unique = []
    for group in groups:
        representative = dict(group["item"])
        representative["copies"] = len(group["members"])
        unique.append(representative)
    return unique


def categorise(item):
    """Which slot a garment fills, from the model's free-text type.

    Matched against `type` alone. Including `short_description` seemed
    generous but reads prose: a t-shirt whose description mentioned a ring
    came back as an accessory, and one mentioning shorts as a bottom.
    """
    text = (item.get("type") or "").lower()
    for name, pattern in CATEGORIES:
        if re.search(pattern, text):
            return name
    return "other"


def _material_roles(item):
    text = (item.get("material") or "").lower()
    return {role for role, pattern in MATERIAL_ROLES.items() if re.search(pattern, text)}


def _concentration(counts):
    """Herfindahl index, 0-1. 1.0 means you own exactly one colour."""
    total = sum(counts)
    if not total:
        return 0.0
    return sum((c / total) ** 2 for c in counts)


def analyse(items):
    """Read a wardrobe and return findings, strongest signal first.

    ``items`` is a list of ClothingItem dicts. Returns a dict of measured
    stats plus a list of findings, each with a severity so the page can
    order them without re-deciding what matters.
    """
    items = [i for i in (items or []) if i]
    if not items:
        return {"total": 0, "findings": [], "stats": {}, "versatile": [], "orphans": []}

    hexes = [hex_for(i) for i in items]
    measured = [lch(h) for h in hexes]

    neutrals = [i for i, (_, c, _) in zip(items, measured) if c < NEUTRAL_CHROMA]
    chromatics = [i for i, (_, c, _) in zip(items, measured) if c >= NEUTRAL_CHROMA]

    colour_counts = Counter(hexes)
    top_hex, top_n = colour_counts.most_common(1)[0]
    concentration = _concentration(list(colour_counts.values()))

    lightness = sorted(L for L, _, _ in measured)
    mid_tones = [L for L in lightness if 0.35 <= L <= 0.68]

    slots = Counter(categorise(i) for i in items)
    roles = Counter()
    for item in items:
        for role in _material_roles(item):
            roles[role] += 1

    # Versatility: the mean harmony score against everything else. A count
    # of "pairs above 70" is useless in a neutral-heavy wardrobe, where
    # every piece clears that bar against every other piece; the mean
    # separates the genuinely flexible from the merely inoffensive.
    versatility = []
    for index in range(len(items)):
        others = [j for j in range(len(items)) if j != index]
        if not others:
            continue
        scores = [harmony(hexes[index], hexes[j])["score"] for j in others]
        versatility.append({
            "index": index,
            "item": items[index],
            "hex": hexes[index],
            "mean": round(sum(scores) / len(scores), 1),
            "strong": sum(1 for s in scores if s >= 80),
            "of": len(others),
        })

    versatility.sort(key=lambda row: -row["mean"])
    versatile = versatility[:5]
    # Bottom of the distribution, and only when meaningfully below the pack.
    overall_mean = (sum(v["mean"] for v in versatility) / len(versatility)) if versatility else 0
    orphans = [v for v in reversed(versatility[-5:]) if v["mean"] < overall_mean - 6]

    findings = []
    total = len(items)

    def add(severity, title, detail, action=None):
        findings.append({"severity": severity, "title": title,
                         "detail": detail, "action": action})

    # ── palette concentration ─────────────────────────────────────────
    share = top_n / total
    if share >= 0.30:
        add("high",
            "One colour dominates",
            "%d of your %d pieces are the same colour — %d%% of everything you own."
            % (top_n, total, round(share * 100)),
            "Anything you add in another hue will go further than another piece in this one.")
    elif concentration < 0.12:
        add("low",
            "A broad palette",
            "No single colour is more than %d%% of your wardrobe." % round(share * 100),
            "Plenty to build from — the constraint is combinations, not colours.")

    # ── anchors and accents ───────────────────────────────────────────
    neutral_share = len(neutrals) / total
    if neutral_share > 0.80:
        add("high",
            "Almost entirely neutral",
            "%d of %d pieces read as neutral. Neutrals can't clash, but nothing "
            "in the wardrobe leads a look either." % (len(neutrals), total),
            "One or two saturated pieces would give every neutral you own something to do.")
    elif neutral_share < 0.25:
        add("high",
            "Not enough anchors",
            "Only %d of %d pieces are neutral. Saturated pieces need something "
            "quiet to sit against." % (len(neutrals), total),
            "A neutral bottom or outer layer multiplies what the rest can pair with.")

    # ── lightness ─────────────────────────────────────────────────────
    if len(mid_tones) / total < 0.15:
        add("medium",
            "Missing the middle",
            "%d%% of your wardrobe sits at the light or dark extremes, with little "
            "in between." % round((1 - len(mid_tones) / total) * 100),
            "Mid-tones bridge a dark bottom and a light top so an outfit reads as layered.")

    # ── slots ─────────────────────────────────────────────────────────
    for slot in ESSENTIAL:
        if slots[slot] == 0:
            add("high", "No %s" % slot,
                "Nothing in your wardrobe reads as %s." % slot,
                "The stylist can't build a complete outfit without one.")
        elif slots[slot] <= 2 and total >= 12:
            add("medium", "Thin on %s" % slot,
                "Only %d %s piece%s against %d pieces overall."
                % (slots[slot], slot, "" if slots[slot] == 1 else "s", total),
                "This is the slot limiting how many distinct outfits you can make.")

    # ── materials ─────────────────────────────────────────────────────
    for role, label, why in [
        ("warm", "warm layers", "there's little here for a cold day"),
        ("breathable", "breathable fabrics", "there's little here for a hot one"),
        ("weather", "weather-resistant pieces", "nothing here shrugs off rain"),
    ]:
        if roles[role] == 0:
            add("medium", "No %s" % label,
                "No piece lists a material suggesting %s — %s." % (label, why),
                "Worth checking: the AI may simply not have read the fabric.")

    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: order.get(f["severity"], 3))

    return {
        "total": total,
        "findings": findings,
        "versatile": versatile,
        "orphans": orphans,
        "stats": {
            "colours": len(colour_counts),
            "top_hex": top_hex,
            "top_share": round(share * 100),
            "concentration": round(concentration, 3),
            "neutral_share": round(neutral_share * 100),
            "neutrals": len(neutrals),
            "chromatics": len(chromatics),
            "mid_tone_share": round(len(mid_tones) / total * 100),
            "slots": dict(slots),
            "roles": dict(roles),
            "median_lightness": round(lightness[len(lightness) // 2], 3),
        },
    }


def outfit_capacity(items):
    """How many complete outfits this wardrobe can actually produce.

    Counts top x bottom x footwear combinations whose colours don't fight,
    which is a truer measure of a wardrobe than how many pieces are in it.
    """
    grouped = {}
    for item in items or []:
        grouped.setdefault(categorise(item), []).append(item)

    tops = grouped.get("top", [])
    bottoms = grouped.get("bottom", [])
    shoes = grouped.get("footwear", [])
    if not (tops and bottoms):
        return {"total": 0, "wearable": 0, "blocked_by": "bottoms" if tops else "tops"}

    total = wearable = 0
    for top in tops:
        for bottom in bottoms:
            for shoe in (shoes or [None]):
                total += 1
                colours = [hex_for(top), hex_for(bottom)]
                if shoe:
                    colours.append(hex_for(shoe))
                worst = min(harmony(colours[i], colours[j])["score"]
                            for i in range(len(colours))
                            for j in range(i + 1, len(colours)))
                if worst >= 60:
                    wearable += 1

    return {"total": total, "wearable": wearable, "blocked_by": None}
