"""One live check of the Gemini backup (IMP-38), for when GEMINI_API_KEY is set in .env.

Sends a single CP-02 call with three short sentences written for this check (no customer
data) to the configured GEMINI_MODEL and prints whether the reply passed the schema and the
key rule, and how long it took. It never prints the key. Usage (from backend/)::

    uv run python scripts/check_gemini.py
"""

from __future__ import annotations

import time

from elucis.ai.gemini import GeminiClient
from elucis.ai.prompts import CP02, Cp02Out, render_records
from elucis.core.config import get_settings
from elucis.modules.analysis.classify import keys_exactly

TEXTS = [
    "The app crashes when I open my cart",
    "Please add a dark mode",
    "Great update, everything is faster",
]


def main() -> int:
    settings = get_settings()
    if not settings.gemini_configured:
        print("GEMINI_API_KEY is not set in .env; nothing was sent.")
        return 1
    keys = [f"r{i + 1}" for i in range(len(TEXTS))]
    content = render_records(list(zip(keys, TEXTS, strict=True)))
    started = time.perf_counter()
    with GeminiClient(settings) as client:
        out, stats = client.chat_json(
            [{"role": "system", "content": CP02.system}, {"role": "user", "content": content}],
            Cp02Out,
            num_predict=CP02.max_output_tokens,
        )
    keys_exactly(keys)(out)
    took = time.perf_counter() - started
    print(
        f"OK: {settings.gemini_model} answered CP-02 in {took:.1f} s ({stats.output_tokens} output tokens)"
    )
    for item in out.items:
        print(f"  {item.key}: {item.category}, {item.sentiment}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
