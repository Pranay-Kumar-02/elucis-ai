# Model benchmark: CP-02, CP-03, CP-04 (F-01, milestone 2 step 7)

Measured 28 Nov 2026 14:32 UTC on the team laptop (RTX 4060 8 GB), Ollama 0.40.4, with `scripts/benchmark_models.py`.

**Input:** 50 records of the validation split of the approved evaluation dataset (Farah, Kabir, Ahmed, Zenodo, DOI 10.5281/zenodo.15852840, CC BY 4.0): 20 labelled bug report, 20 feature request, 10 irrelevant, chosen with a fixed seed, cleaned and PII-masked like any import. The prompts, schemas and limits are the production ones; `think: false`, temperature 0. Each model ran 2 passes of 5 CP-02 batches of 10, 4 CP-03 namings of 8 records and 2 CP-04 batches of 10, after one uncounted warm-up call.

| Model | Valid output | Thinking leakage | Latency p50 | Latency p95 | Output tokens/s | CP-02 agrees with dataset labels |
|---|---|---|---|---|---|---|
| `qwen3:4b` | 100% of 22 calls | 0 calls | 3.7 s | 4.3 s | 72 | 88% of 40 |
| `qwen3:4b-instruct` | 91% of 22 calls | 0 calls | 3.4 s | 4.4 s | 72 | 82% of 40 |

Per call:

| Model | Call | Valid | Latency p50 | Errors |
|---|---|---|---|---|
| `qwen3:4b` | CP-02 | 10/10 | 4.3 s | - |
| `qwen3:4b` | CP-03 | 8/8 | 0.9 s | - |
| `qwen3:4b` | CP-04 | 4/4 | 3.6 s | - |
| `qwen3:4b-instruct` | CP-02 | 8/10 | 4.3 s | OutputRuleError |
| `qwen3:4b-instruct` | CP-03 | 8/8 | 1.1 s | - |
| `qwen3:4b-instruct` | CP-04 | 4/4 | 3.3 s | - |

**Decision rule** (fixed before running): highest valid-output rate, then least leakage, then lowest p50 latency. **Result: `qwen3:4b`.**

Caveats: 50 records and 22 calls per model is a small sample, enough to compare two models on the same inputs, not to quote absolute rates; the agreement column compares CP-02 with the dataset's privacy-domain labels and is a signal only (see ACCURACY_REPORT.md).

## Decision (28 Nov 2026)

`qwen3:4b` stays the chat model (`OLLAMA_CHAT_MODEL`, unchanged). It produced valid output on every call and agreed more often with the dataset's labels. `qwen3:4b-instruct` was slightly faster but twice broke CP-02's "every key exactly once" rule; the job would have retried those batches. Neither model leaked reasoning text into schema-constrained replies, so F-01 does not affect CP-02, CP-03 or CP-04. It still affects free-text replies: the strict smoke test in `40-setup-ollama.ps1` keeps reporting it until a free-text call exists.

These timings were measured after the GPU power cap was removed (F-11): before that, both models ran at 1.7 output tokens per second.
