"""Check that the configured model and provider actually answer.

Run this after changing OPENAI_BASE_URL, OPENAI_MODEL or the API key:

    python -m scripts.check_llm

It reports the resolved configuration, then makes two small calls -- a text
one and an image one -- so you find out here rather than mid-upload whether
the provider serves the model and whether it accepts images.
"""

import base64
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from utils.llm import base_url, chat, chat_model, vision_model  # noqa: E402


def _tiny_png():
    """A 2x2 PNG, built in memory, so the vision probe costs almost nothing."""
    try:
        from PIL import Image
    except ImportError:
        return None
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), (31, 42, 68)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def main():
    key = os.getenv("OPENAI_API_KEY") or ""
    print("configuration")
    print("  base_url      :", base_url() or "api.openai.com (OpenAI direct)")
    print("  chat model    :", chat_model())
    print("  vision model  :", vision_model())
    print("  api key       :", f"set, {len(key)} chars, starts {key[:6]!r}" if key else "MISSING")
    print()

    ok = True

    print("1. text call ...", end=" ", flush=True)
    try:
        reply = chat(
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            max_output_tokens=16,
        )
        print("OK ->", repr((reply or "").strip()))
    except Exception as error:                          # noqa: BLE001
        ok = False
        print("FAILED")
        print("   ", type(error).__name__, str(error)[:400])

    print("2. image call ...", end=" ", flush=True)
    encoded = _tiny_png()
    if not encoded:
        print("skipped (Pillow not installed)")
    else:
        try:
            reply = chat(
                model=vision_model(),
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Name the dominant colour. One word."},
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/png;base64,{encoded}"}},
                    ],
                }],
                max_output_tokens=16,
            )
            print("OK ->", repr((reply or "").strip()))
        except Exception as error:                      # noqa: BLE001
            ok = False
            print("FAILED")
            print("   ", type(error).__name__, str(error)[:400])
            print("    If only this one failed, the model has no vision support.")
            print("    Set OPENAI_VISION_MODEL in .env to a model that does.")

    print()
    print("all good — uploads and the stylist will work." if ok
          else "something failed above; the app will error on those calls.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
