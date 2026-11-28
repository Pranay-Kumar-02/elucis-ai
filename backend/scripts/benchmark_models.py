"""Benchmark chat models on our real prompts (F-01, milestone 2 step 7).

Runs CP-02 (classification), CP-03 (theme naming) and CP-04 (canonical asks) exactly as the
analysis job sends them (same system text, schema, limits, ``think: false``,
temperature 0), on 50 records of the approved evaluation dataset's **validation** split (the
test split is kept for the accuracy report). Texts are cleaned and PII-masked first, like any
import. For each model it measures:

* valid-output rate: the reply parses, matches the schema and passes the call's own rules
  (every key once, cited IDs among those given, at most 12 words...);
* latency per call (p50, p95) and output tokens per second, from Ollama's own timings;
* thinking leakage: reasoning text in the reply (``<think>`` tags, or a non-empty
  ``thinking`` field although thinking was off);
* CP-02 agreement with the dataset's labels on the records labelled bug report (should be an
  issue category) or feature request (should be ``feature_request``) - a quality signal
  only, the accuracy report (step 8) is the real measure.

Writes ``docs/evaluation/MODEL_BENCHMARK.md``. Usage (from backend/)::

    uv run python scripts/benchmark_models.py --models qwen3:4b qwen3:4b-instruct
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from elucis.ai.ollama import OllamaClient
from elucis.ai.prompts import (
    CP02,
    CP03,
    CP04,
    ISSUE_CATEGORIES,
    Cp02Out,
    Cp03Out,
    Cp04Out,
    PromptSpec,
    render_records,
)
from elucis.core.config import REPO_ROOT, get_settings
from elucis.modules.analysis.classify import keys_exactly
from elucis.modules.analysis.requests import ask_rules
from elucis.modules.analysis.tasks import OutputRuleError
from elucis.modules.analysis.themes import naming_rules
from elucis.modules.preprocessing.clean import clean_text
from elucis.modules.preprocessing.pii import mask

DATA = REPO_ROOT / "data" / "evaluation" / "zenodo-15852840"
REPORT = REPO_ROOT / "docs" / "evaluation" / "MODEL_BENCHMARK.md"
PASSES = 2


@dataclass
class Result:
    model: str
    calls: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    agreement: list[bool] = field(default_factory=list)


def load_sample() -> list[tuple[str, str, str]]:
    """(record_id, masked text, dataset label) for 20 bug reports, 20 requests, 10 others."""
    with (DATA / "val-labels.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rng = random.Random(42)
    rng.shuffle(rows)
    picked: list[dict[str, str]] = []
    for category, wanted in (("bug_report", 20), ("feature_request", 20), ("", 10)):
        picked += [r for r in rows if r["category"] == category][:wanted]
    return [(r["record_id"], mask(clean_text(r["text"])).text, r["category"]) for r in picked]


def call(
    client: OllamaClient,
    model: str,
    spec: PromptSpec,
    content: str,
    schema: type[BaseModel],
    check: Any,
) -> tuple[dict[str, Any], BaseModel | None]:
    started = time.perf_counter()
    reply = client.chat(
        [{"role": "system", "content": spec.system}, {"role": "user", "content": content}],
        model=model,
        format_schema=schema.model_json_schema(),
        think=False,
        temperature=0.0,
        num_predict=spec.max_output_tokens,
    )
    wall_ms = (time.perf_counter() - started) * 1000
    leaked = "<think>" in reply.content or "</think>" in reply.content or bool(reply.thinking)
    parsed: BaseModel | None = None
    error = None
    try:
        parsed = schema.model_validate(json.loads(reply.content))
        check(parsed)
    except (json.JSONDecodeError, ValidationError, OutputRuleError) as exc:
        error = type(exc).__name__
        parsed = None
    return (
        {
            "valid": parsed is not None,
            "error": error,
            "leaked": leaked,
            "ms": reply.stats.total_ms or wall_ms,
            "tps": reply.stats.tokens_per_second,
        },
        parsed,
    )


def run_model(client: OllamaClient, model: str, sample: list[tuple[str, str, str]]) -> Result:
    result = Result(model)
    # Warm-up (loads the model into VRAM); not counted.
    call(
        client,
        model,
        CP04,
        render_records([("r1", "Please add a dark mode")]),
        Cp04Out,
        lambda _o: None,
    )
    for _ in range(PASSES):
        for start in range(0, 50, 10):  # CP-02: 5 batches of 10
            batch = sample[start : start + 10]
            keys = [f"r{i + 1}" for i in range(len(batch))]
            rec, out = call(
                client,
                model,
                CP02,
                render_records(list(zip(keys, [t for _, t, _ in batch], strict=True))),
                Cp02Out,
                keys_exactly(keys),
            )
            result.calls.setdefault("CP-02", []).append(rec)
            if isinstance(out, Cp02Out) and _ == 0:
                labels = {i.key: i.category for i in out.items}
                for key, (_rid, _text, dataset) in zip(keys, batch, strict=True):
                    if dataset == "bug_report":
                        result.agreement.append(labels[key] in ISSUE_CATEGORIES)
                    elif dataset == "feature_request":
                        result.agreement.append(labels[key] == "feature_request")
        for group in (sample[0:8], sample[8:16], sample[20:28], sample[28:36]):  # CP-03
            keys = [f"E{i + 1}" for i in range(len(group))]
            content = "Records:\n" + render_records(
                list(zip(keys, [t for _, t, _ in group], strict=True))
            )
            rec, _out = call(client, model, CP03, content, Cp03Out, naming_rules(keys))
            result.calls.setdefault("CP-03", []).append(rec)
        for start in (20, 30):  # CP-04 on the feature requests
            batch = sample[start : start + 10]
            keys = [f"r{i + 1}" for i in range(len(batch))]
            rec, _out = call(
                client,
                model,
                CP04,
                render_records(list(zip(keys, [t for _, t, _ in batch], strict=True))),
                Cp04Out,
                ask_rules(keys),
            )
            result.calls.setdefault("CP-04", []).append(rec)
    return result


def _p(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def summarise(r: Result) -> dict[str, Any]:
    every = [c for calls in r.calls.values() for c in calls]
    tps = [c["tps"] for c in every if c["tps"]]
    out: dict[str, Any] = {
        "valid": sum(c["valid"] for c in every) / len(every),
        "leaked": sum(c["leaked"] for c in every),
        "calls": len(every),
        "p50": statistics.median(c["ms"] for c in every),
        "p95": _p([c["ms"] for c in every], 0.95),
        "tps": statistics.median(tps) if tps else None,
        "agreement": sum(r.agreement) / len(r.agreement) if r.agreement else None,
        "agreement_n": len(r.agreement),
    }
    for name, calls in r.calls.items():
        out[name] = {
            "valid": f"{sum(c['valid'] for c in calls)}/{len(calls)}",
            "p50": statistics.median(c["ms"] for c in calls),
            "errors": sorted({c["error"] for c in calls if c["error"]}),
        }
    return out


def write_report(results: list[Result], versions: dict[str, str]) -> str:
    rows = {r.model: summarise(r) for r in results}
    best = sorted(rows, key=lambda m: (-rows[m]["valid"], rows[m]["leaked"], rows[m]["p50"]))[0]
    lines = [
        "# Model benchmark: CP-02, CP-03, CP-04 (F-01, milestone 2 step 7)",
        "",
        f"Measured {datetime.now(UTC).strftime('%d %b %Y %H:%M UTC')} on the team laptop "
        f"(RTX 4060 8 GB), Ollama {versions.get('ollama', '?')}, with `scripts/benchmark_models.py`.",
        "",
        "**Input:** 50 records of the validation split of the approved evaluation dataset "
        "(Farah, Kabir, Ahmed, Zenodo, DOI 10.5281/zenodo.15852840, CC BY 4.0): 20 labelled bug "
        "report, 20 feature request, 10 irrelevant, chosen with a fixed seed, cleaned and "
        "PII-masked like any import. The prompts, schemas and limits are the production ones; "
        f"`think: false`, temperature 0. Each model ran {PASSES} passes of 5 CP-02 batches of 10, "
        "4 CP-03 namings of 8 records and 2 CP-04 batches of 10, after one uncounted warm-up call.",
        "",
        "| Model | Valid output | Thinking leakage | Latency p50 | Latency p95 | Output tokens/s | CP-02 agrees with dataset labels |",
        "|---|---|---|---|---|---|---|",
    ]
    for model, s in rows.items():
        agree = (
            f"{s['agreement']:.0%} of {s['agreement_n']}" if s["agreement"] is not None else "n/a"
        )
        tps = f"{s['tps']:.0f}" if s["tps"] else "n/a"
        lines.append(
            f"| `{model}` | {s['valid']:.0%} of {s['calls']} calls | {s['leaked']} calls | "
            f"{s['p50'] / 1000:.1f} s | {s['p95'] / 1000:.1f} s | {tps} | {agree} |"
        )
    lines += [
        "",
        "Per call:",
        "",
        "| Model | Call | Valid | Latency p50 | Errors |",
        "|---|---|---|---|---|",
    ]
    for model, s in rows.items():
        for name in ("CP-02", "CP-03", "CP-04"):
            c = s[name]
            lines.append(
                f"| `{model}` | {name} | {c['valid']} | {c['p50'] / 1000:.1f} s | {', '.join(c['errors']) or '-'} |"
            )
    lines += [
        "",
        f"**Decision rule** (fixed before running): highest valid-output rate, then least leakage, then lowest p50 latency. **Result: `{best}`.**",
        "",
        "Caveats: 50 records and 22 calls per model is a small sample, enough to compare two models "
        "on the same inputs, not to quote absolute rates; the agreement column compares CP-02 with "
        "the dataset's privacy-domain labels and is a signal only (see ACCURACY_REPORT.md).",
        "",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", nargs="+", default=["qwen3:4b", "qwen3:4b-instruct"])
    args = parser.parse_args()
    settings = get_settings()
    sample = load_sample()
    results = []
    with OllamaClient(settings) as client:
        versions = {"ollama": client.version()}
        for model in args.models:
            print(f"benchmarking {model} ...", flush=True)
            results.append(run_model(client, model, sample))
            print(json.dumps(summarise(results[-1]), default=str), flush=True)
    best = write_report(results, versions)
    print(f"report: {REPORT}  best: {best}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
