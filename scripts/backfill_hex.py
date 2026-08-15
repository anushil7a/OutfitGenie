"""Fill color_hex for garments read before the column existed.

Every ClothingItem already carries a colour *name*. This resolves those names
to hex in a single model call over the distinct set -- roughly forty requests'
worth of work for the price of one -- so the wardrobe spectrum is populated
before anyone uploads anything new.

Run from the project root, with the virtualenv active:

    python -m scripts.backfill_hex           # write the changes
    python -m scripts.backfill_hex --dry-run # show what would change

Safe to run more than once: rows that already have a hex are skipped.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app                                  # noqa: E402
from models import db, ClothingItem                  # noqa: E402
from utils.color_utils import normalize_hex, hex_from_name  # noqa: E402

BATCH_PROMPT = """You are converting garment colour descriptions into hex.

For each name below, return the single hex that best represents how that
fabric photographs. Judge the garment, not a screen primary: never return
#000000 or #FFFFFF -- a black tee is nearer #232428, a white shirt nearer
#F2F1EC. For a multi-colour name ("gray and white", "blue with pink
accents"), return the dominant colour only.

Return nothing but a JSON object mapping each input name, verbatim, to its
hex string.

Names:
{names}
"""


def ask_model_for_hex(names):
    """One request for every distinct colour name. Returns {name: hex}."""
    from utils.llm import chat

    raw = chat(
        response_format={"type": "json_object"},
        messages=[
            {"role": "system",
             "content": "You answer only with valid JSON. No prose, no code fences."},
            {"role": "user",
             "content": BATCH_PROMPT.format(names=json.dumps(sorted(names), indent=2))},
        ],
        max_output_tokens=2000,
    )
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("  ! model did not return usable JSON; falling back to the name map")
        print(f"  ! got: {raw[:200]}")
        return {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change without writing")
    parser.add_argument("--offline", action="store_true",
                        help="skip the model and use the built-in name map only")
    args = parser.parse_args()

    with app.app_context():
        pending = (ClothingItem.query
                   .filter(ClothingItem.color_hex.is_(None))
                   .filter(ClothingItem.color.isnot(None))
                   .all())

        if not pending:
            print("Nothing to backfill -- every garment already has a hex.")
            return

        names = sorted({item.color.strip() for item in pending if item.color and item.color.strip()})
        print(f"{len(pending)} garments carrying {len(names)} distinct colour names.")

        mapping = {}
        if not args.offline:
            if not os.getenv("OPENAI_API_KEY"):
                print("No OPENAI_API_KEY set -- using the built-in name map instead.")
            else:
                print("Asking the model to resolve them (one request)...")
                mapping = ask_model_for_hex(names)

        resolved, guessed, skipped = 0, 0, 0
        for item in pending:
            name = (item.color or "").strip()
            value = normalize_hex(mapping.get(name))
            if value:
                resolved += 1
            else:
                value = hex_from_name(name)
                if value:
                    guessed += 1
            if not value:
                skipped += 1
                continue
            if args.dry_run:
                print(f"  {name!r:36} -> {value}")
            else:
                item.color_hex = value

        if args.dry_run:
            print(f"\nDry run: {resolved} from the model, {guessed} from the name map, "
                  f"{skipped} unresolved (these render neutral).")
            return

        db.session.commit()
        print(f"\nDone. {resolved} from the model, {guessed} from the name map, "
              f"{skipped} left neutral.")


if __name__ == "__main__":
    main()
