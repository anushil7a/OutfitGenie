"""Wardrobe insights, colour pairings, and the packing planner.

All measured, no model calls — these pages render instantly and cost nothing.
"""

import logging

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from models import ClothingItem
from utils.color_theory import harmony
from utils.color_utils import hex_for
from utils.packing import FORECAST_DAYS, plan_trip
from utils.wardrobe_insights import (SLOT_LABEL, analyse, categorise,
                                     dedupe_pieces, outfit_capacity, wears_with)

insights_bp = Blueprint('insights', __name__)
logger = logging.getLogger(__name__)

# Order the "wear it with" panels appear in.
SLOT_ORDER = ["top", "bottom", "full", "outerwear", "footwear", "accessory", "other"]


def wardrobe(unique=True):
    """The user's pieces. Deduped by default: the same garment photographed
    in four outfits is four rows, and counting it four times is wrong."""
    items = [item.to_dict()
             for item in ClothingItem.query.filter_by(user_id=current_user.id).all()]
    return dedupe_pieces(items) if unique else items


@insights_bp.route('/insights')
@login_required
def wardrobe_insights():
    items = wardrobe()
    report = analyse(items)
    capacity = outfit_capacity(items)

    chosen_id = request.args.get('piece', type=int)
    chosen = next((i for i in items if i.get('id') == chosen_id), None)
    if chosen is None and items:
        chosen = report['versatile'][0]['item'] if report['versatile'] else items[0]

    # Partners, grouped by the slot they'd fill. Only slots that actually go
    # with the chosen piece — a shirt has no business recommending a shirt.
    groups = []
    chosen_hex = None
    if chosen:
        chosen_hex = hex_for(chosen)
        chosen_slot = categorise(chosen)

        buckets = {}
        for other in items:
            if other.get('id') == chosen.get('id'):
                continue
            slot = categorise(other)
            if not wears_with(chosen_slot, slot):
                continue
            verdict = harmony(chosen_hex, hex_for(other))
            buckets.setdefault(slot, []).append(
                {"item": other, "hex": hex_for(other), **verdict})

        for slot in SLOT_ORDER:
            rows = buckets.get(slot)
            if not rows:
                continue
            rows.sort(key=lambda r: -r["score"])
            groups.append({
                "slot": slot,
                "label": SLOT_LABEL.get(slot, slot.title()),
                "rows": rows[:3],
                "count": len(rows),
            })

    return render_template(
        'insights.html',
        report=report,
        capacity=capacity,
        items=sorted(items, key=lambda i: (categorise(i), (i.get('type') or ''))),
        chosen=chosen,
        chosen_hex=chosen_hex,
        chosen_slot=SLOT_LABEL.get(categorise(chosen), '') if chosen else '',
        groups=groups,
    )


@insights_bp.route('/pack')
@login_required
def pack():
    city = (request.args.get('city') or '').strip()
    nights = request.args.get('nights', type=int) or 3
    nights = max(1, min(nights, FORECAST_DAYS))

    plan = None
    if city:
        try:
            plan = plan_trip(wardrobe(), city, nights)
        except Exception as error:                       # noqa: BLE001
            logger.warning("Trip planning failed for %r: %s", city, error)
            plan = {"error": "Couldn't reach the forecast. Try again."}

    return render_template('pack.html', plan=plan, city=city,
                           nights=nights, max_days=FORECAST_DAYS,
                           categorise=categorise)
