"""Colour relationships, computed.

Every garment carries a real hex, so whether two pieces work together is a
measurable question rather than a matter of taste. This module answers it in
OKLCH -- a perceptually uniform space, so a 30 degree hue step looks like the
same size step wherever you are on the wheel, which is not true of HSL.

Nothing here calls a model. The stylist may narrate the result; the result
itself is arithmetic.

    lch("#1F2A44")                  -> (L, C, H)
    harmony("#1F2A44", "#D8CDBA")   -> {'relation': 'neutral anchor', 'score': 88, ...}
    rank_partners(piece, wardrobe)  -> best matches first, each with a reason
"""

import math

from utils.color_utils import normalize_hex, NEUTRAL

# Below this chroma a colour reads as a neutral: it sits beside anything
# without competing. Blacks, greys, greiges, most denim-adjacent navies.
NEUTRAL_CHROMA = 0.045

# Hue windows, in degrees. Perceptual space, so these are honest widths.
_MONOCHROME = 12
_ANALOGOUS = 45
# Contiguous with the complementary window: a 145 degree pair is a wide
# triad, not an accident, and shouldn't fall through to "tension".
_TRIADIC = (100, 150)
_COMPLEMENT = (150, 210)


def _srgb_to_linear(channel):
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def oklab(hex_value):
    """sRGB hex to OKLab (Björn Ottosson's transform)."""
    h = (normalize_hex(hex_value) or NEUTRAL).lstrip("#")
    r, g, b = (_srgb_to_linear(int(h[i:i + 2], 16)) for i in (0, 2, 4))

    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b

    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))

    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def lch(hex_value):
    """OKLCH: lightness 0-1, chroma 0-~0.4, hue 0-360."""
    L, a, b = oklab(hex_value)
    chroma = math.hypot(a, b)
    hue = math.degrees(math.atan2(b, a)) % 360
    return L, chroma, hue


def is_neutral(hex_value):
    return lch(hex_value)[1] < NEUTRAL_CHROMA


def hue_gap(hue_a, hue_b):
    """Shortest distance between two hue angles, 0-180."""
    diff = abs(hue_a - hue_b) % 360
    return min(diff, 360 - diff)


def distance(hex_a, hex_b):
    """Perceptual distance in OKLab. ~0.02 is barely telling them apart."""
    a, b = oklab(hex_a), oklab(hex_b)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def harmony(hex_a, hex_b):
    """How two colours sit together.

    Returns a relation name, a 0-100 score, and a plain-language reason.
    The scoring rewards three things real outfits depend on: a recognised
    hue relationship, enough lightness separation that the pieces read as
    separate garments, and at least one neutral to carry a bold hue.
    """
    la, ca, ha = lch(hex_a)
    lb, cb, hb = lch(hex_b)

    light_gap = abs(la - lb)
    gap = hue_gap(ha, hb)
    neutral_a, neutral_b = ca < NEUTRAL_CHROMA, cb < NEUTRAL_CHROMA

    # Two neutrals, or a neutral plus anything: the safest thing in clothing.
    if neutral_a and neutral_b:
        relation = "neutral pair"
        base = 78
        reason = "Both read as neutrals, so they can't clash"
    elif neutral_a or neutral_b:
        relation = "neutral anchor"
        base = 88
        chromatic_chroma = cb if neutral_a else ca
        reason = ("A neutral carries the %s without competing with it"
                  % ("bolder piece" if chromatic_chroma > 0.12 else "colour"))
    elif gap <= _MONOCHROME:
        relation = "monochrome"
        base = 72
        reason = "Same hue family — needs the lightness to do the work"
    elif gap <= _ANALOGOUS:
        relation = "analogous"
        base = 82
        reason = "Neighbouring hues, %d° apart — quiet and cohesive" % round(gap)
    elif _COMPLEMENT[0] <= gap <= _COMPLEMENT[1]:
        relation = "complementary"
        base = 80
        reason = "Opposite hues, %d° apart — deliberate contrast" % round(gap)
    elif _TRIADIC[0] <= gap <= _TRIADIC[1]:
        relation = "triadic"
        base = 70
        reason = "A third of the wheel apart — lively, needs a neutral third piece"
    else:
        relation = "tension"
        base = 44
        reason = "%d° apart — close enough to look accidental" % round(gap)

    score = base

    # Lightness separation. Two mid-tone pieces of similar weight muddy
    # each other; real outfits stack light against dark.
    if light_gap < 0.08 and not (neutral_a and neutral_b):
        score -= 18
        reason += ", and they sit at nearly the same lightness"
    elif light_gap > 0.35:
        score += 8

    # Two saturated colours fighting for attention.
    if not neutral_a and not neutral_b and ca > 0.12 and cb > 0.12:
        score -= 10

    return {
        "relation": relation,
        "score": max(0, min(100, round(score))),
        "reason": reason,
        "hue_gap": round(gap),
        "lightness_gap": round(light_gap, 3),
    }


def rank_partners(target_hex, candidates, limit=None):
    """Rank wardrobe pieces against one piece, best pairing first.

    ``candidates`` is an iterable of dicts carrying at least ``color_hex``
    (or resolvable ``color``). Each result is the candidate plus its
    harmony verdict.
    """
    from utils.color_utils import hex_for

    scored = []
    for candidate in candidates or []:
        candidate_hex = hex_for(candidate)
        verdict = harmony(target_hex, candidate_hex)
        scored.append({"item": candidate, "hex": candidate_hex, **verdict})

    scored.sort(key=lambda row: (-row["score"], row["hue_gap"]))
    return scored[:limit] if limit else scored


def outfit_score(hex_values):
    """Score a whole look: the average of every pair in it.

    A three-piece outfit has three pairings, a four-piece has six. Scoring
    every pair rather than adjacent ones catches the case where the shoes
    fight the jacket even though both work with the trousers.
    """
    colours = [h for h in (normalize_hex(x) or None for x in hex_values) if h]
    if len(colours) < 2:
        return {"score": None, "pairs": []}

    pairs = []
    for i in range(len(colours)):
        for j in range(i + 1, len(colours)):
            verdict = harmony(colours[i], colours[j])
            pairs.append({"a": colours[i], "b": colours[j], **verdict})

    weakest = min(pairs, key=lambda p: p["score"])
    return {
        "score": round(sum(p["score"] for p in pairs) / len(pairs)),
        "weakest": weakest,
        "pairs": pairs,
    }
