"""Colour helpers for the Spectrum design system.

Every bit of chroma in OutfitGenie's interface comes from garments the AI has
actually read, which means the templates can never be handed a missing or
malformed hex. Every function here is total: it always returns something
usable, falling back to a neutral rather than raising.

Three sources of hex, in priority order:
  1. ``ClothingItem.color_hex``  -- what the vision model returned
  2. ``NAMED``                   -- a fallback map for items analysed before
                                    color_hex existed, so the UI looks right
                                    before ``scripts/backfill_hex.py`` runs
  3. ``NEUTRAL``                 -- an unreadable item still renders
"""

import re

NEUTRAL = "#8A8D93"

# Pure black and pure white make for a dead spectrum band, so garments the
# model calls "black" or "white" resolve to the near-neutrals a real fabric
# actually photographs as.
_BLACK = "#232428"
_WHITE = "#F2F1EC"

# Deliberately not exhaustive. The backfill resolves the long tail; this
# covers the colour words the vision prompt reaches for most often.
NAMED = {
    "black": _BLACK, "white": _WHITE, "ivory": "#F4F0E4", "cream": "#EFE7D6",
    "ecru": "#F0EDE6", "oat": "#D8CDBA", "beige": "#D6C9B0", "tan": "#C4A484",
    "khaki": "#BFAE83", "camel": "#B08D5A", "sand": "#DCCBAE", "taupe": "#A89A8C",
    "brown": "#6B4A32", "chocolate": "#4A3123", "chestnut": "#7A4A2E",
    "rust": "#9C4A2B", "terracotta": "#B45B3E", "orange": "#D2691E",
    "amber": "#C68A24", "mustard": "#C9A227", "gold": "#BFA14A",
    "yellow": "#E3C34A", "lime": "#9FBF3B", "olive": "#5E6444",
    "sage": "#8A9A7B", "green": "#3F6B45", "forest": "#2E4A34",
    "emerald": "#2F7A5A", "mint": "#A8D5BA", "teal": "#2F6B6B",
    "turquoise": "#3FA6A6", "cyan": "#4BA9C4", "sky": "#8FB8D6",
    "blue": "#2B4C7E", "navy": "#1F2A44", "denim": "#4A6D8C",
    "indigo": "#3B4A73", "cobalt": "#2A4FA8", "periwinkle": "#8E9BD9",
    "purple": "#5B4372", "violet": "#6B4E8C", "lavender": "#B9A7D0",
    "plum": "#5D3A52", "magenta": "#A63A76", "pink": "#D89BB0",
    "rose": "#C08A85", "blush": "#E0BFB8", "coral": "#D97A6C",
    "salmon": "#DE8B7A", "red": "#A8322B", "crimson": "#8E2230",
    "burgundy": "#5C2333", "maroon": "#5A2A2A", "wine": "#5A2434",
    "grey": "#7E8288", "gray": "#7E8288", "charcoal": "#33363B",
    "slate": "#5A6472", "silver": "#B9BCC0", "stone": "#A8A49C",
    "natural": "#DED6C4", "nude": "#D8B79C",
    # Patterns aren't colours, but garments get described this way and a
    # sensible swatch beats a grey blank in the band.
    "multicolor": "#8A8D93", "multicolour": "#8A8D93",
    "multicolored": "#8A8D93", "multicoloured": "#8A8D93",
    "rainbow": "#8A8D93", "camouflage": "#5E6444", "camo": "#5E6444",
    "floral": "#B98BA4", "denim": "#4A6D8C",
}

# Words that qualify a colour rather than being one. "dark blue" has to darken
# blue, not resolve to grey because "dark" came first in the sentence.
# (lightness shift, desaturation)
MODIFIERS = {
    "dark":    (-.24, .00), "deep":    (-.26, .00), "midnight": (-.34, .05),
    "light":   (.26, .00),  "pale":    (.30, .08),  "soft":     (.16, .10),
    "bright":  (.06, -.15), "vivid":   (.00, -.20), "rich":     (-.10, -.08),
    "muted":   (.04, .28),  "dusty":   (.06, .30),  "dusky":    (-.10, .26),
    "heather": (.10, .34),  "faded":   (.14, .30),  "washed":   (.18, .28),
    "burnt":   (-.14, .10),
}

# Used only when a modifier appears with no colour word beside it.
_MODIFIER_ALONE = {
    "dark": "#3A3D42", "midnight": "#22252B", "deep": "#3A3D42",
    "light": "#C9CCD1", "pale": "#DCDDE0", "soft": "#C9CCD1",
    "muted": "#9A9EA3", "dusty": "#A8A49C", "dusky": "#6E7278",
    "heather": "#9A9EA3", "faded": "#B4B7BB", "washed": "#B4B7BB",
    "burnt": "#9C4A2B", "bright": "#C9CCD1", "vivid": "#8A8D93", "rich": "#5A5D63",
}


def _shift(hex_value, lightness, desaturate):
    """Nudge a base colour by a modifier's lightness and saturation deltas."""
    h = hex_value.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))

    if desaturate:
        grey = 0.299 * r + 0.587 * g + 0.114 * b
        t = max(-1.0, min(1.0, desaturate))
        r, g, b = (c + (grey - c) * t for c in (r, g, b))

    if lightness:
        target = 255.0 if lightness > 0 else 0.0
        t = min(1.0, abs(lightness))
        r, g, b = (c + (target - c) * t for c in (r, g, b))

    return "#" + "".join("%02X" % max(0, min(255, int(round(c)))) for c in (r, g, b))

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_WORD_RE = re.compile(r"[a-z]+")


def normalize_hex(value):
    """Return ``#RRGGBB`` for anything hex-shaped, else ``None``.

    Accepts ``fff``, ``#fff``, ``FFFFFF``. Anything else -- a colour name, an
    empty string, ``None``, a model that answered in prose -- returns None so
    the caller can fall through to the next source.
    """
    if not value or not isinstance(value, str):
        return None
    match = _HEX_RE.match(value.strip())
    if not match:
        return None
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return "#" + digits.upper()


def hex_from_name(name):
    """Best-effort hex for a free-text colour name, or ``None``.

    The vision model answers with phrases -- ``"Gray and white"``, ``"Blue
    with pink accents"``, ``"dark navy"`` -- so this reads words rather than
    requiring the whole string to be a known colour.

    The first true colour word wins, matching how people read these phrases
    ("gray and white" is a grey garment with white on it). Any modifier
    sitting beside it is then applied, so "dark blue" darkens blue instead of
    resolving to the grey that "dark" means on its own.
    """
    if not name or not isinstance(name, str):
        return None

    words = _WORD_RE.findall(name.lower())
    base = next((NAMED[w] for w in words if w in NAMED), None)
    modifier = next((w for w in words if w in MODIFIERS), None)

    if base is None:
        return _MODIFIER_ALONE.get(modifier) if modifier else None
    if modifier is None:
        return base
    lightness, desaturate = MODIFIERS[modifier]
    return _shift(base, lightness, desaturate)


def hex_for(item):
    """Resolve a garment's hex from a dict or a ``ClothingItem``. Never None."""
    if item is None:
        return NEUTRAL
    if isinstance(item, dict):
        stored, name = item.get("color_hex"), item.get("color")
    else:
        stored, name = getattr(item, "color_hex", None), getattr(item, "color", None)
    return normalize_hex(stored) or hex_from_name(name) or NEUTRAL


def luminance(hex_value):
    """WCAG relative luminance, 0.0 (black) to 1.0 (white)."""
    h = (normalize_hex(hex_value) or NEUTRAL).lstrip("#")
    channels = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def is_light(hex_value):
    return luminance(hex_value) > 0.55


def ink_on(hex_value):
    """Ink or paper, whichever stays readable on top of this swatch."""
    return "#16171A" if is_light(hex_value) else "#F2F1EC"


def _label(names):
    """Pick the clearest label for a hex several garments share."""
    ranked = sorted(names.items(), key=lambda kv: (-kv[1], len(kv[0]), kv[0]))
    return ranked[0][0] if ranked else "unnamed"


def build_spectrum(entries, limit=12):
    """Aggregate garments into the proportional band the whole UI is built on.

    ``entries`` is an iterable of ``(colour_name, colour_hex, count)``. Results
    group by resolved hex -- "navy" and "dark blue" landing on the same value
    become one segment -- and sort by how much of it you own, so the band
    reads as a wardrobe inventory rather than a rainbow.

    Anything past ``limit`` is folded into a single "other" segment so a
    50-colour closet still renders as a legible band.
    """
    buckets = {}
    for name, stored_hex, count in entries:
        count = int(count or 0)
        if count <= 0:
            continue
        resolved = normalize_hex(stored_hex) or hex_from_name(name) or NEUTRAL
        bucket = buckets.setdefault(resolved, {"count": 0, "names": {}})
        bucket["count"] += count
        if name:
            key = str(name).strip().lower()
            bucket["names"][key] = bucket["names"].get(key, 0) + count

    # Merge colours the eye can't tell apart. The vision model reports a
    # dozen slightly different blacks (#242629, #25262A, #1E1E1C ...) which
    # would otherwise fragment the band into a dozen identical-looking
    # slivers and push every real colour into the overflow bucket.
    from utils.color_theory import distance  # local: color_theory imports this module

    merged = []
    for hex_value, bucket in sorted(buckets.items(), key=lambda kv: -kv[1]["count"]):
        for target in merged:
            if distance(target["hex"], hex_value) < 0.055:
                target["count"] += bucket["count"]
                for name, n in bucket["names"].items():
                    target["names"][name] = target["names"].get(name, 0) + n
                break
        else:
            merged.append({"hex": hex_value, "count": bucket["count"],
                           "names": dict(bucket["names"])})

    ordered = [(m["hex"], m) for m in sorted(merged, key=lambda m: (-m["count"], m["hex"]))]
    total = sum(m["count"] for _, m in ordered)
    if not total:
        return []

    head, tail = ordered[:limit], ordered[limit:]
    segments = [
        {
            "hex": hex_value,
            "name": _label(bucket["names"]),
            "count": bucket["count"],
            "pct": round(bucket["count"] * 100.0 / total, 1),
            "light": is_light(hex_value),
            "is_other": False,
        }
        for hex_value, bucket in head
    ]
    if tail:
        # A rollup of the long tail, not a colour anything is actually dyed.
        # Flagged so the UI never offers it as something to filter by --
        # nothing can match it, so clicking it always returned nothing.
        rest = sum(b["count"] for _, b in tail)
        segments.append({
            "hex": NEUTRAL,
            "name": "%d more colours" % len(tail),
            "count": rest,
            "pct": round(rest * 100.0 / total, 1),
            "light": False,
            "is_other": True,
        })
    return segments


def spectrum_from_items(items, limit=12):
    """Build a band from a list of item dicts or ``ClothingItem`` objects."""
    entries = []
    for item in items or []:
        if isinstance(item, dict):
            entries.append((item.get("color"), item.get("color_hex"), 1))
        else:
            entries.append((getattr(item, "color", None),
                            getattr(item, "color_hex", None), 1))
    return build_spectrum(entries, limit=limit)
