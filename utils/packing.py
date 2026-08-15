"""Pack the fewest pieces that cover the most days.

Given a city and a date range, this pulls the forecast, works out what the
trip actually demands (a warm layer? a shell? breathable fabric?), then picks
a capsule from the wardrobe by greedy set cover -- at each step taking the
piece that covers the most still-uncovered requirements, tie-broken by how
well it pairs with what's already in the bag.

The forecast is free-tier OpenWeather: 5 days at 3-hour steps. Trips beyond
that window are reported honestly rather than invented.
"""

import os
import re
from collections import defaultdict
from datetime import datetime, timedelta

import requests

from utils.color_theory import harmony
from utils.color_utils import hex_for
from utils.wardrobe_insights import categorise

FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
FORECAST_DAYS = 5

# What a day demands, by temperature (Fahrenheit) and sky.
WARM_BELOW = 55
BREATHABLE_ABOVE = 75

MATERIAL_WARM = r"wool|cashmere|fleece|down|shearling|flannel|corduroy|tweed|thermal|knit|puffer"
MATERIAL_BREATHABLE = r"cotton|linen|chambray|jersey|mesh|bamboo|rayon|viscose"
MATERIAL_SHELL = r"nylon|gore|waterproof|shell|polyester|leather|denim|canvas|water.?resistant"


def get_forecast(city):
    """Daily summary for the next few days, or None.

    Returns a list of {date, low, high, condition, rain} in the user's
    imperial units, matching the rest of the app.
    """
    key = os.getenv("WEATHER_API_KEY")
    if not key or not city:
        return None
    try:
        response = requests.get(FORECAST_URL, timeout=20, params={
            "q": city, "appid": key, "units": "imperial",
        })
        response.raise_for_status()
        entries = response.json().get("list", [])
    except requests.exceptions.RequestException:
        return None

    days = defaultdict(lambda: {"temps": [], "conditions": [], "rain": False})
    for entry in entries:
        stamp = datetime.utcfromtimestamp(entry["dt"]).date()
        bucket = days[stamp]
        bucket["temps"].append(entry["main"]["temp"])
        condition = entry["weather"][0]["main"].lower()
        bucket["conditions"].append(condition)
        if condition in ("rain", "drizzle", "thunderstorm", "snow"):
            bucket["rain"] = True

    summary = []
    for date in sorted(days):
        bucket = days[date]
        commonest = max(set(bucket["conditions"]), key=bucket["conditions"].count)
        summary.append({
            "date": date,
            "label": date.strftime("%a %d %b"),
            "low": round(min(bucket["temps"])),
            "high": round(max(bucket["temps"])),
            "condition": commonest,
            "rain": bucket["rain"],
        })
    return summary


def requirements_for(days):
    """Turn a forecast into the capabilities a bag has to cover."""
    needs = set()
    if not days:
        return needs
    coldest = min(d["low"] for d in days)
    hottest = max(d["high"] for d in days)

    needs.add("core")                       # tops and bottoms, always
    if coldest < WARM_BELOW:
        needs.add("warm")
        needs.add("covering")               # long cuts, not shorts
    if hottest > BREATHABLE_ABOVE:
        needs.add("breathable")
        needs.add("cooling")
    if any(d["rain"] for d in days):
        needs.add("shell")
    # A wide swing only calls for layers if the bottom of it is actually
    # cool. Dallas swinging 82->103 needs shade, not a jacket.
    if hottest - coldest >= 20 and coldest < 65:
        needs.add("layering")
    return needs


# How much skin a garment leaves out, read from its name. Material can't
# tell you this: "synthetic shorts" and "synthetic trousers" look identical
# on the fabric field but are not interchangeable at 48°F.
CUT_EXPOSED = r"\bshorts\b|sleeveless|tank\b|\bvest\b|sandal|flip.?flop|short.?sleeve"
CUT_COVERED = r"trouser|\bpant|jean|chino|slack|legging|jogger|long.?sleeve|full.?sleeve|maxi"


def _capabilities(item):
    """What one garment can do."""
    material = (item.get("material") or "").lower()
    name = (item.get("type") or "").lower()
    slot = categorise(item)
    caps = set()

    if slot in ("top", "bottom", "full"):
        caps.add("core")
    if slot == "outerwear":
        caps.add("layering")
    if re.search(MATERIAL_WARM, material) or slot == "outerwear":
        caps.add("warm")
    if re.search(MATERIAL_BREATHABLE, material):
        caps.add("breathable")
    if re.search(MATERIAL_SHELL, material) and slot == "outerwear":
        caps.add("shell")

    if re.search(CUT_EXPOSED, name):
        caps.add("cooling")
    elif re.search(CUT_COVERED, name) or slot == "outerwear":
        caps.add("covering")
    return caps


def build_capsule(items, days, max_pieces=12):
    """Greedy set cover, tie-broken by how well a piece pairs with the bag.

    Guarantees the slots an outfit needs (tops, bottoms, one outer layer if
    it's cold), then keeps adding whichever piece closes the most remaining
    requirements until everything is covered or the bag is full.
    """
    items = [i for i in (items or []) if i]
    if not items:
        return {"pieces": [], "covered": set(), "missing": set(), "outfits": 0}

    needs = requirements_for(days)
    by_slot = defaultdict(list)
    for item in items:
        by_slot[categorise(item)].append(item)

    bag = []

    def bag_fit(candidate):
        """Mean harmony against what's already packed. Ties go to cohesion."""
        if not bag:
            return 100
        candidate_hex = hex_for(candidate)
        scores = [harmony(candidate_hex, hex_for(p))["score"] for p in bag]
        return sum(scores) / len(scores)

    # Seed the core slots. Weather first, cohesion second: sorting on
    # colour alone packed shorts for a 48°F trip because they happened to
    # go with everything.
    def suitability(candidate):
        caps = _capabilities(candidate)
        wanted = len(caps & needs)
        # Actively penalise a piece whose only strength is the season
        # you're not travelling in.
        wrong = 0
        if "covering" in needs and "cooling" in caps:
            wrong += 2                      # shorts on a cold trip
        if "cooling" in needs and "warm" in caps and "breathable" not in caps:
            wrong += 1                      # fleece on a hot one
        return (wanted - wrong, bag_fit(candidate))

    for slot, want in (("top", 3), ("bottom", 2), ("footwear", 1)):
        pool = sorted(by_slot.get(slot, []), key=suitability, reverse=True)
        for piece in pool[:want]:
            if len(bag) < max_pieces:
                bag.append(piece)

    covered = set()
    for piece in bag:
        covered |= _capabilities(piece)

    remaining = [i for i in items if i not in bag]
    while needs - covered and len(bag) < max_pieces and remaining:
        def value(candidate):
            gained = len(_capabilities(candidate) & (needs - covered))
            return (gained, bag_fit(candidate))

        best = max(remaining, key=value)
        if value(best)[0] == 0:
            break
        bag.append(best)
        covered |= _capabilities(best)
        remaining.remove(best)

    return {
        "pieces": bag,
        "covered": covered,
        "missing": needs - covered,
        "needs": needs,
        "outfits": count_outfits(bag),
    }


def count_outfits(pieces):
    """Distinct wearable combinations from a bag: top x bottom x footwear."""
    grouped = defaultdict(list)
    for piece in pieces:
        grouped[categorise(piece)].append(piece)

    tops = grouped.get("top", []) + grouped.get("full", [])
    bottoms = grouped.get("bottom", [])
    shoes = grouped.get("footwear", []) or [None]
    if not tops:
        return 0

    total = 0
    for top in tops:
        for bottom in (bottoms or [None]):
            for shoe in shoes:
                colours = [hex_for(top)]
                if bottom:
                    colours.append(hex_for(bottom))
                if shoe:
                    colours.append(hex_for(shoe))
                if len(colours) < 2:
                    continue
                worst = min(harmony(colours[i], colours[j])["score"]
                            for i in range(len(colours))
                            for j in range(i + 1, len(colours)))
                if worst >= 60:
                    total += 1
    return total


def plan_trip(items, city, nights=3):
    """The whole thing: forecast, requirements, capsule, per-day notes."""
    forecast = get_forecast(city)
    if not forecast:
        return {"error": "No forecast for that city. Check the spelling and try again."}

    days = forecast[:max(1, min(int(nights or 1), FORECAST_DAYS))]
    capsule = build_capsule(items, days)

    for day in days:
        notes = []
        if day["low"] < WARM_BELOW:
            notes.append("layer up")
        if day["high"] > BREATHABLE_ABOVE:
            notes.append("keep it breathable")
        if day["rain"]:
            notes.append("expect rain")
        day["notes"] = notes

    return {
        "city": city,
        "days": days,
        "truncated": (nights or 0) > FORECAST_DAYS,
        "capsule": capsule,
        "ratio": round(capsule["outfits"] / len(capsule["pieces"]), 1) if capsule["pieces"] else 0,
    }
