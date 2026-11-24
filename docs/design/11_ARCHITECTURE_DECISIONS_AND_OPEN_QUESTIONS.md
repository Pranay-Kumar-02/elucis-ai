# 11 · Architecture Decisions, Audit and Open Questions

Status: design for mentor review. Nothing here has been implemented, measured or approved by the mentor.

## 1. Research method and limitations

| Step | What was done |
|---|---|
| Source reading | Project brief, Final SRS v1.0 (253 requirements), Technical Architecture v1.0, Mentor Summary, Audit Register, mentor transcript |
| Independent research | Official documentation for each runtime, library and external API used in the design, read on 20 November 2026 (§2) |
| Evaluation | Alternatives compared per decision against the project constraints: zero cost, local-first on the reference laptop, no LLM orchestration framework, traceable evidence, 40-hour scope |
| Audit | The 18 issues in the master prompt examined one by one (§4), plus the gap register G-01 to G-18 (doc 00 §3) |

Labels used throughout the package: **[V]** verified in official documentation, **[3P]** third-party or community source, **[D]** design decision, **[E]** estimate that must be measured, **[C]** calculated from stated assumptions.

Limitations:

- No benchmark was run. Every speed, memory and quality figure marked [E] is an estimate; experiments in §6 replace them with measurements.
- Vendor connector APIs were checked in documentation only; no account was used. Access policies (for example Atlassian admin enablement) can differ per organisation.
- Third-party model sizes (for example `qwen3:8b`) come from listings rather than a pull on the laptop.
- The mentor transcript is auto-generated; only clear passages were used. The advice to avoid LLM orchestration frameworks was relayed by the team and is still awaiting confirmation (B-04).

## 2. Sources

All accessed 20 November 2026.

| ID | Source | URL | Used for |
|---|---|---|---|
| S-01 | Ollama structured outputs | https://docs.ollama.com/capabilities/structured-outputs | `format` with JSON schema (CP-01 to CP-10) |
| S-02 | Ollama thinking | https://docs.ollama.com/capabilities/thinking | `think` on or off (EXP-07) |
| S-03 | Ollama tool calling | https://docs.ollama.com/capabilities/tool-calling | Assistant tool loop |
| S-04 | Ollama embed API | https://docs.ollama.com/api/embed | `/api/embed` with array input |
| S-05 | Ollama chat API | https://docs.ollama.com/api/chat | `logprobs`, `top_logprobs`, options |
| S-06 | Ollama context length | https://docs.ollama.com/context-length | `num_ctx`, default context |
| S-07 | Ollama FAQ | https://docs.ollama.com/faq | Keep-alive 5 min default, `OLLAMA_NUM_PARALLEL` default 1, `OLLAMA_MAX_LOADED_MODELS` default 3 per GPU, KV cache types and Flash Attention, 4,096 default context |
| S-08 | Ollama GPU | https://docs.ollama.com/gpu | NVIDIA support, RTX 4060 compute capability |
| S-09 | Ollama on Windows | https://docs.ollama.com/windows | Native Windows install, driver requirement |
| S-10 | Ollama issue 15260 | https://github.com/ollama/ollama/issues/15260 | Reported conflict between thinking and `format` for another model family (reason for EXP-07) [3P] |
| S-11 | `qwen3:4b` | https://ollama.com/library/qwen3:4b | 2.5 GB, Apache 2.0, tools, thinking |
| S-12 | `qwen3.5:4b` | https://ollama.com/library/qwen3.5:4b | 4.0 GB including vision projector (why not default) |
| S-13 | `qwen3-embedding` | https://ollama.com/library/qwen3-embedding | 0.6b at 639 MB, 4b at 2.5 GB, 32K context |
| S-14 | pgvector 0.8.7 README | https://github.com/pgvector/pgvector/blob/v0.8.7/README.md | HNSW, `vector_cosine_ops`, iterative scans, 2,000-dimension HNSW limit, Windows build with `nmake`, Docker image tags |
| S-15 | PostgreSQL versioning | https://www.postgresql.org/support/versioning/ | PostgreSQL 18 support window |
| S-16 | PostgreSQL row security | https://www.postgresql.org/docs/18/ddl-rowsecurity.html | RLS, `FORCE ROW LEVEL SECURITY`, owner bypass |
| S-17 | PostgreSQL CREATE POLICY | https://www.postgresql.org/docs/18/sql-createpolicy.html | `USING`, `WITH CHECK` |
| S-18 | PostgreSQL SKIP LOCKED | https://www.postgresql.org/about/featurematrix/detail/skip-locked-clause/ | Job claiming |
| S-19 | FastAPI on PyPI | https://pypi.org/project/fastapi/ | Version, OpenAPI generation |
| S-20 | React versions | https://react.dev/versions | React 19 line |
| S-21 | Vite 8 announcement | https://vite.dev/blog/announcing-vite8 | Vite 8 and Node requirements |
| S-22 | Node.js releases | https://nodejs.org/en/about/previous-releases | Node 24 LTS |
| S-23 | shadcn/ui with Vite | https://ui.shadcn.com/docs/installation/vite | Tailwind v4 Vite setup |
| S-24 | scikit-learn HDBSCAN | https://scikit-learn.org/1.9/modules/generated/sklearn.cluster.HDBSCAN.html | `min_cluster_size`, `min_samples`, `cluster_selection_method` |
| S-25 | scikit-learn calibration | https://scikit-learn.org/stable/modules/calibration | `CalibratedClassifierCV`, sigmoid (Platt) and isotonic |
| S-26 | Presidio installation | https://microsoft.github.io/presidio/installation | Supported Python versions, spaCy models |
| S-27 | MCP Python SDK | https://github.com/modelcontextprotocol/python-sdk | Client for streamable HTTP and stdio |
| S-28 | Atlassian Rovo MCP server | https://github.com/atlassian/atlassian-mcp-server | Remote endpoint, scope |
| S-29 | Rovo MCP supported tools | https://support.atlassian.com/atlassian-rovo-mcp-server/docs/supported-tools/ | Jira tool names |
| S-30 | Rovo MCP authentication | https://support.atlassian.com/atlassian-rovo-mcp-server/docs/authentication-and-authorization/ | OAuth 2.1 |
| S-31 | Rovo MCP API token | https://support.atlassian.com/atlassian-rovo-mcp-server/docs/configuring-authentication-via-api-token | API-token login enabled by an admin |
| S-32 | `mcp-atlassian` | https://github.com/sooperset/mcp-atlassian | Self-hosted fallback server (MIT) |
| S-33 | Google Play reviews | https://developers.google.com/android-publisher/reply-to-reviews | 7-day window, comments only, quota |
| S-34 | App Store Connect reviews | https://developer.apple.com/documentation/appstoreconnectapi/customer-reviews | Customer reviews resource |
| S-35 | Zendesk incremental exports | https://developer.zendesk.com/api-reference/ticketing/ticket-management/incremental_exports/ | Cursor-based ticket export |
| S-36 | Zendesk rate limits | https://developer.zendesk.com/api-reference/introduction/rate-limits/ | Export limits |
| S-37 | Mixpanel raw event export | https://developer.mixpanel.com/reference/raw-event-export | Export endpoint and limits |
| S-38 | Amplitude Export API | https://amplitude.com/docs/apis/analytics/export | Export endpoint, time format, limits |
| S-39 | Microsoft Graph transcripts | https://learn.microsoft.com/en-us/graph/api/calltranscript-get | Transcript content, permissions |
| S-40 | OWASP Password Storage | https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html | Argon2id parameters |
| S-41 | WSL configuration | https://learn.microsoft.com/en-us/windows/wsl/wsl-config | WSL memory default and cap |
| S-42 | Intercom: RICE prioritisation | https://www.intercom.com/blog/rice/ | Reach per period, Impact scale 3/2/1/0.5/0.25, Confidence 100/80/50%, Effort in person-months |

Methods cited by name rather than URL: Reciprocal Rank Fusion (Cormack, Clarke and Büttcher, SIGIR 2009), maximal marginal relevance (Carbonell and Goldstein, SIGIR 1998), Platt scaling (Platt, 1999).

## 3. Architecture decision records

Each record: context, decision, alternatives, consequences, validation. "Mentor" says whether mentor approval is needed.

| ADR | Decision | Alternatives rejected (why) | Consequences | Validation | Mentor |
|---|---|---|---|---|---|
| ADR-01 | **Modular monolith** (one FastAPI app, one package per module) plus **one worker** process | Microservices (operational cost, RAM, no team benefit at this scale); serverless (not local, not zero cost); single process without worker (long jobs block requests, lost on restart) | Clear module boundaries; one deployable; shared transaction for multi-module writes | Package dependency check in CI; NFR-07 service count | No |
| ADR-02 | **Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2** | Node/NestJS (ML libraries are Python); Django (heavier, ORM-centric admin not needed); Flask (no built-in validation or OpenAPI) | Same language for API, pipeline and ML; OpenAPI generated (IR-05) | EXP-12 installs all packages on Python 3.12 on Windows | No |
| ADR-03 | **React 19 + TypeScript + Vite 8 + Tailwind v4 + shadcn/ui**, built to static files served by FastAPI | Next.js (server rendering not needed; adds a Node server, a fifth service); Streamlit (insufficient for drill-down, roles and editing) | Single origin, simple cookies and CSRF; no extra running service | Build on Node 24 LTS | No |
| ADR-04 | **File import is the MVP source**; live sources through a `SourceAdapter` interface with designed connectors (doc 01 §3) | Building live connectors now (needs accounts, credentials and approval; quotas such as Google Play's 7-day window) | Mentor's question about data origin answered without scope blow-up | One connector spike only if AR-05 approves | Yes (AR-05) |
| ADR-05 | **Durable jobs in a PostgreSQL table** with `FOR UPDATE SKIP LOCKED`, heartbeat and step cursor; the assistant runs in-request | Celery + Redis (extra services, against NFR-07); generic workflow engine (more tables and code for the same guarantees); Temporal (heavy) | Restartable, idempotent jobs; one mechanism for all long work | TC-08 kill-and-restart tests | No |
| ADR-06 | **Deterministic orchestrator + specialised schema-constrained LLM tasks + one bounded read-only assistant loop**; no LLM orchestration framework; no multi-agent | LangChain or LangGraph (mentor advice; abstraction churn; hides prompts); multi-agent (more model calls on a laptop GPU, harder to test, no task needs negotiation between agents) | Every model call is explicit, versioned and testable; loop limits enforced in code | TC-05, TC-14, TC-20 | Yes (B-04) |
| ADR-07 | **Classification cascade**: calibrated embedding + logistic regression first; batched LLM (CP-02) for records the classifier does not accept; review queue below threshold | LLM per record (estimated hours for 5,000 records, doc 06 §8); classifier only (weaker on sarcasm and mixed records); LLM batched only (no calibrated probabilities) | Throughput and calibration improve; requires labelled training data (CR-08) | EXP-01, EXP-09 | No |
| ADR-08 | **Models**: `qwen3:4b` default for all CP calls; `qwen3:8b` candidate for CP-06, CP-08 and CP-09; `qwen3-embedding:0.6b` for embeddings; all through Ollama | Paid APIs (violates NFR-06); `qwen3.5:4b` (4.0 GB with vision projector, larger for no needed capability); Llama or Gemma families (benchmark alternates, licence and tooling checks needed); bigger embedding models (VRAM) | Fits 8 GB VRAM with headroom; quality is the main risk (RK-01) | EXP-01 to EXP-04 | Yes (AR-01) |
| ADR-09 | **Clustering**: PCA 50 → scikit-learn HDBSCAN, `eom` vs `leaf` and several `min_cluster_size` values compared; second pass on noise with minimum 3 for small themes | k-means (needs k, forces every record into a cluster); BERTopic (adds UMAP and many dependencies; similar core); LLM-only theming (non-reproducible, AIR-04) | Small themes can surface; parameters chosen by measurement | EXP-06 | No |
| ADR-10 | **Stable theme identity and overrides as data**: match new clusters to previous themes (Jaccard ≥ 0.5 or centroid cosine ≥ 0.85); re-apply overrides each run | Recompute from scratch (loses names and corrections); freeze themes (misses new issues) | PM corrections survive re-runs (FR-THM-12, CR-05) | TC-16 re-run tests | No |
| ADR-11 | **Row-level security from Phase 1**, plus composite tenant foreign keys and repository filtering | Application filtering only (one bug exposes data); schema or database per tenant (migration and connection cost) | Three independent isolation layers | TC-10, TC-11 | No |
| ADR-12 | **PostgreSQL + pgvector as the single store** with hybrid retrieval (vector + full-text via RRF, then MMR and per-customer cap) | Separate vector database such as Qdrant or Chroma (extra service, cross-store consistency, against NFR-07); vector only (misses exact product terms); full-text only (misses paraphrases) | One SQL query applies workspace, filters and ranking | EXP-05 | No |
| ADR-13 | **Evidence-first generation**: typed claims, numbers as placeholders filled by SQL, deterministic citation, quotation and number checks, advisory model support check, human approval with acknowledgement | Free-text generation with post-hoc citation (unverifiable numbers); model-only verification (unreliable, RK-02) | Citation validity and numeric accuracy can be 100% by construction | TC-03, TC-04, EXP-08 | No |
| ADR-14 | **Presidio + spaCy small model + custom recognisers**, fail closed | Regex only (poor recall on names); large spaCy model (more RAM); cloud PII services (cost, data leaves the laptop) | Masking before any model call (NFR-21) | EXP-10, TC-13 | No |
| ADR-15 | **Jira through `JiraPort`**: Rovo MCP adapter primary, self-hosted `mcp-atlassian` adapter fallback; deterministic code after approval only; idempotent by story link and marker | Direct Jira REST (mentor asked for MCP); LLM-driven MCP tool use (unsafe, AGR-13) | Works whether or not API-token access is enabled by the org admin | EXP-12, TC-21 | Yes (AR-04, B-03) |
| ADR-16 | **Server-side sessions** in an HttpOnly cookie with CSRF token | JWT in local storage (XSS-exposed, hard to revoke); OAuth provider (external dependency, not needed for a local demo) | Immediate logout (FR-AUTH-03), simple CSRF | TC-12 | No |
| ADR-17 | **Server-Sent Events** for job progress and assistant status; final assistant answer sent only after verification | WebSockets (bidirectional not needed); polling only (slower feedback, NFR-04); token streaming (would show unverified text) | Simple, proxy-friendly progress | TC-24 for NFR-01 and NFR-04 | No |
| ADR-18 | **RICE Confidence**: standard levels (100%, 80%, 50%) [V S-42]; a labelled project-specific rubric suggests a level from evidence quality (sufficiency, identity coverage, label uncertainty, behaviour conflict, unconfirmed AI inputs); a person can override; Reach stays separate; Effort in person-weeks as a labelled adaptation | Confidence derived from customer counts (mixes Reach into Confidence, double counting); AI-chosen Confidence (opaque, AIR-08) | Transparent, explainable confidence with full history | TC-01 | Yes (AR-10) |

## 4. Independent design audit (18 issues)

Each issue: existing proposal → concern → impact → research → recommendation → alternatives → what to validate → mentor approval.

### DA-01 Import reconciliation mismatch (AC-ING-01 vs DR-40)

| Aspect | Finding |
|---|---|
| Existing | AC-ING-01: received = imported + rejected + duplicates + filtered. DR-40: received = imported + rejected + duplicates + filtered + failed |
| Concern | AC-ING-01 omits failed rows. Both formulas double count, because duplicates and filtered records are stored (DR-15, DR-18), so they are also "imported" |
| Impact | NFR-08 (100% reconciliation) cannot be tested against an ambiguous identity |
| Research | Standard accounting separates row fate (rejected at validation, failed in processing, stored) from record status of stored rows |
| Recommendation | Keep DR-40's terms but define each one so the categories are disjoint (doc 06 §10.1): received = imported (analysable) + rejected (failed validation, not stored) + duplicates (exact, same customer) + filtered (noise, PII failed, non-English, spam, awaiting spam review) + failed (stored, processing failed). Analysis-run outcomes (embedding failures, near duplicates, unclassified) are reported per run, not in the import identity. AC-ING-01 gains "+ failed". **CR-01** |
| Alternatives | Keep DR-40 and define "imported" as analysable only (still ambiguous for transcripts split into segments) |
| Validate | TC-07, TC-08 with seeded files containing every row fate |
| Mentor | Yes, via CR-01 |

### DA-02 Short-feedback filter discarding useful comments

| Aspect | Finding |
|---|---|
| Existing | A-09: fewer than 3 words is noise |
| Concern | "App crashes", "login broken", "crashes on login" are short but valuable bug reports |
| Impact | Under-counts exactly the terse bug reports PMs care about |
| Research | Word-count filters are crude; noise is better defined by absence of content (no letters, only emoji or punctuation, filler-only strings) |
| Recommendation | Noise if no alphabetic word remains, or the text matches a boilerplate list ("test", "n/a", "ok", "."), or it has fewer than 3 words **and** no signal term (problem, product, feature or emotion lexicon such as "crash", "login", "slow", "refund", "love", "hate"). "app crashes" and "nice" are kept. **CR-02**; examples in doc 06 §5, rule in doc 03 SVC-05 |
| Alternatives | Lower the limit to 2 words (still drops "crashes"); model-based noise detection (cost per record) |
| Validate | Noise precision and recall on the labelled set (TC-02, TC-15) |
| Mentor | Yes, via CR-02 |

### DA-03 Minimum distinct-customer rule hiding critical single-customer incidents

| Aspect | Finding |
|---|---|
| Existing | A-13: a claim like "users report" needs at least 3 distinct customers |
| Concern | One report of data loss, a security issue or payment failure may need immediate attention |
| Impact | Critical issues could be suppressed in PRDs, summaries and assistant answers |
| Research | Severity and frequency are separate axes in triage practice; a frequency rule should not gate severity |
| Recommendation | Keep A-13 for generalised claims. Add a `critical_signal` flag (category `bug_report` or `performance_issue`, negative sentiment, and a severity term such as data loss, security, charged twice, cannot log in). Such records can be cited as "an individual report" with that exact wording, and the dashboard lists them separately. **CR-03** |
| Alternatives | Drop A-13 (invites over-generalisation); manual flagging only (depends on someone noticing) |
| Validate | Seeded critical single reports must appear in the dashboard and in executive summaries with individual-report wording |
| Mentor | Yes, via CR-03 |

### DA-04 Are model confidence values calibrated?

| Aspect | Finding |
|---|---|
| Existing | A-12: threshold 0.6 on model confidence; no method to obtain or calibrate it |
| Concern | Verbalised confidence from LLMs is not a probability; uncalibrated thresholds route the wrong records to review |
| Impact | Review queue either floods or misses errors |
| Research | scikit-learn's `CalibratedClassifierCV` provides sigmoid (Platt) and isotonic calibration [V S-25]; Ollama can return token log-probabilities [V S-05], usable as a raw score that is then Platt-scaled |
| Recommendation | Stage A: calibrated classifier probabilities. Stage B: first-token log-probability of the label, Platt-scaled on validation data. Report ECE; set the threshold by validation to hit a target error-capture rate. **CR-04** (doc 04 §6) |
| Alternatives | Self-reported confidence (unreliable); self-consistency over several samples (3× cost) |
| Validate | ECE and error capture rate (doc 10 §8.2) in EXP-09 |
| Mentor | Yes, via CR-04 |

### DA-05 HDBSCAN settings hiding smaller themes

| Aspect | Finding |
|---|---|
| Existing | `min_cluster_size` = max(5, n/200), `eom` |
| Concern | About 25 records minimum at 5,000 records; `eom` favours large clusters |
| Impact | Emerging or niche problems disappear into noise |
| Research | scikit-learn's HDBSCAN offers `cluster_selection_method` `eom` and `leaf`, where `leaf` yields more, smaller, homogeneous clusters [V S-24] |
| Recommendation | Compare `eom` and `leaf` with `min_cluster_size` in {10, 15, max(5, n/200)}; run a second pass on noise with minimum 3 and mark results `small`; show the unassigned group (FR-THM-07); add a spike rule for emerging themes (CR-06). ADR-09 |
| Alternatives | Agglomerative clustering with a distance threshold; BERTopic |
| Validate | ARI and small-theme recall (EXP-06) |
| Mentor | No |

### DA-06 Is per-record LLM classification practical?

| Aspect | Finding |
|---|---|
| Existing | One LLM call per record |
| Concern | Each call pays prompt processing plus generation; at an assumed 1 to 3 s per call, 5,000 records take about 1.5 to 4 hours [E] (doc 06 §8) |
| Impact | Analysis becomes an overnight task; demo risk |
| Research | Ollama caches matching prompt prefixes and reports token counts and durations, so the real cost per call can be measured [V S-05, S-07] |
| Recommendation | Not as the default. Use the cascade (ADR-07) |
| Alternatives | Smaller model for classification only; CPU classifier only |
| Validate | EXP-01 measures per-record and batched cost |
| Mentor | No |

### DA-07 Is batch inference preferable?

| Aspect | Finding |
|---|---|
| Existing | Not specified |
| Concern | Batching amortises the fixed prompt but risks misaligned or dropped items and cross-record influence |
| Impact | Throughput versus accuracy |
| Research | Structured outputs with a JSON schema constrain item shape [V S-01]; validation can detect missing IDs |
| Recommendation | Batches of 10 to 20 records with short record keys (`r1`…`r10`) and the CP-02 schema `{key, category, sentiment, sarcasm}`, schema-enforced; any batch with missing or duplicate IDs falls back to per-record calls; batch size chosen in EXP-01 by accuracy and speed |
| Alternatives | Ollama parallel requests (`OLLAMA_NUM_PARALLEL` > 1) raise VRAM use; rejected for the laptop |
| Validate | EXP-01: accuracy difference between batch sizes 1, 5, 10, 20 on the validation split |
| Mentor | No |

### DA-08 Is the hardware sufficient for the selected models?

| Aspect | Finding |
|---|---|
| Existing | `qwen3:4b` on RTX 4060 8 GB |
| Concern | VRAM is sufficient for 4B models; system RAM (16 GB, about 3.9 GB free in the observed snapshot) is the tighter constraint |
| Impact | Swapping and slowdowns during the demo (NFR-05) |
| Research | `qwen3:4b` is 2.5 GB [V S-11]; `qwen3-embedding:0.6b` 639 MB [V S-13]; default context 4,096 tokens; KV cache quantisation needs Flash Attention [V S-07] |
| Recommendation | Keep 4B default; 8B only where EXP-02 or EXP-03 shows a real gain; `OLLAMA_MAX_LOADED_MODELS=2`; per-call `num_ctx`; demo mode closes other applications; readiness check reports free memory (doc 10 §9) |
| Alternatives | CPU inference (much slower); smaller models (quality) |
| Validate | EXP-01 peak RAM and VRAM during a full analysis and a PRD generation |
| Mentor | No |

### DA-09 PostgreSQL and pgvector on Windows

| Aspect | Finding |
|---|---|
| Existing | Native PostgreSQL on Windows with pgvector built locally (AR-02) |
| Concern | pgvector has no Windows installer in the README; it must be built |
| Impact | Setup time on five laptops |
| Research | Windows build needs Visual Studio C++ support and `nmake` in the x64 Native Tools prompt [V S-14]; official Docker image `pgvector/pgvector:pg18` exists [V S-14]; WSL 2 takes up to 50% of RAM by default unless capped [V S-41] |
| Recommendation | EXP-12 on the reference laptop: try the native build first (no VM overhead); fall back to the Docker image with a WSL memory cap. Both are the same PostgreSQL 18 + pgvector 0.8.7, so the design does not change |
| Alternatives | A managed cloud database (cost, data leaves the laptop) |
| Validate | EXP-12: install time, memory overhead, `CREATE EXTENSION vector` and HNSW index build |
| Mentor | Yes (AR-02) |

### DA-10 Python 3.12 package compatibility

| Aspect | Finding |
|---|---|
| Existing | Python 3.12 for all backend code |
| Concern | ML and NLP packages sometimes lag Python releases |
| Impact | Blocked installs |
| Research | Presidio supports Python 3.11 to 3.14 [V S-26]; FastAPI, Pydantic v2, SQLAlchemy 2 and scikit-learn publish wheels for current Python versions (checked on PyPI pages for FastAPI [V S-19]; others to confirm in EXP-12) |
| Recommendation | Pin all versions in a lock file; EXP-12 installs the full set on Windows with Python 3.12 before Milestone 1 coding |
| Alternatives | Python 3.11 if any package fails |
| Validate | EXP-12 |
| Mentor | No |

### DA-11 Are local models good enough for classification and generation?

| Aspect | Finding |
|---|---|
| Existing | Qwen3 4B or 8B locally |
| Concern | Smaller models make more label errors and write vaguer PRDs |
| Impact | Credibility of insights (RK-01) |
| Research | No benchmark on our data exists; published model cards are not evidence for this task |
| Recommendation | Measure, do not assume: baseline at Milestone 2 on the frozen test split; mitigate with the cascade, evidence-first generation, verification and mandatory review; report results honestly |
| Alternatives | Paid API models (excluded by NFR-06) |
| Validate | EXP-02, EXP-03, EXP-09; TC-15, TC-19, TC-20 |
| Mentor | Yes (AR-01; targets agreed after baseline per SRS §11.3) |

### DA-12 Jira authentication and permissions

| Aspect | Finding |
|---|---|
| Existing | Rovo MCP server |
| Concern | OAuth 2.1 needs an interactive consent flow; API-token login must be enabled by an organisation admin [V S-30, S-31]; the token user needs permission to create issues in the project |
| Impact | Jira step may not work on the demo site |
| Research | Self-hosted `mcp-atlassian` supports API tokens against Jira Cloud [3P S-32] |
| Recommendation | ADR-15 dual adapter; connection test (API-79) lists projects and issue types before any preview; least-privilege test user |
| Alternatives | Direct REST (not MCP; contradicts mentor direction) |
| Validate | EXP-12 on a free Jira Cloud test site |
| Mentor | Yes (B-03, AR-04) |

### DA-13 Evidence citation reliability

| Aspect | Finding |
|---|---|
| Existing | Model cites evidence IDs |
| Concern | Models invent or misplace IDs and numbers |
| Impact | False claims with real-looking citations |
| Research | Short opaque codes are easier for models to copy than UUIDs; deterministic checks can validate IDs, quotes and numbers |
| Recommendation | E-codes mapped to record IDs per evidence pack; reject IDs outside the pack; exact-quote check; numbers only through placeholders; support check advisory; approval acknowledges failures (doc 05 §6 to §8, ADR-13) |
| Alternatives | Post-hoc retrieval for each sentence (slower, still model-dependent) |
| Validate | TC-03, TC-04, EXP-08 |
| Mentor | No |

### DA-14 Human override preservation after re-analysis

| Aspect | Finding |
|---|---|
| Existing | FR-THM-12 is Could |
| Concern | If re-runs discard renames, merges and moves, PMs stop trusting and using corrections |
| Impact | Core trust feature missing |
| Research | Storing corrections as data and re-applying them is the standard pattern for human-in-the-loop labelling |
| Recommendation | Overrides as rows (theme_overrides, person-origin score inputs, review resolutions), re-applied each run after identity matching (ADR-10); raise FR-THM-12 to Should (**CR-05**) |
| Alternatives | Lock themes after first edit (stale); ask PM again each run (tedious) |
| Validate | TC-16 re-run with overrides |
| Mentor | Yes, via CR-05 |

### DA-15 Tool-call loop safety and termination

| Aspect | Finding |
|---|---|
| Existing | A-16: 6 tool calls, 5 minutes |
| Concern | Models can repeat tools, loop or call tools with invalid arguments |
| Impact | Hung requests, GPU monopolised |
| Research | Ollama tool calling returns tool calls that the application executes [V S-03]; all control stays in our code |
| Recommendation | Strict 5-minute deadline measured from request start; every model call (cap 90 s), tool call (cap 10 s) and verification uses `min(cap, remaining − 15 s)`; ≤ 4 model turns, ≤ 6 tool calls, duplicate call detection, argument validation; after the tool budget the next turn has no tools; at the deadline only verified content is returned, marked incomplete (doc 04 §5.2) |
| Alternatives | Unbounded ReAct loop (unsafe); no tools, single retrieval (cannot answer counts) |
| Validate | TC-05, TC-14, TC-20 termination rate |
| Mentor | No |

### DA-16 Model call cost in memory, latency and processing time

| Aspect | Finding |
|---|---|
| Existing | Not budgeted |
| Concern | Large contexts increase KV-cache memory and latency |
| Impact | Out-of-memory offloading and slow demos |
| Research | Context is set per request with `num_ctx`; default 4,096 [V S-06, S-07] |
| Recommendation | Per call point budgets for context, output tokens and timeout (doc 04 §3.1); evidence packs capped by tokens; caching of identical inputs (AIR-25); metrics in `llm_call_records` |
| Alternatives | One large context for everything (memory) |
| Validate | EXP-01 per-call measurements |
| Mentor | No |

### DA-17 Unnecessary complexity

| Aspect | Finding |
|---|---|
| Existing | Generic workflow engine, optional components |
| Concern | More moving parts than 40 hours allow |
| Impact | Unfinished modules |
| Research | Every requirement checked against the minimal component that satisfies it |
| Recommendation | Removed the generic workflow engine (ADR-05), no broker, no vector database, no framework, no multi-agent; connectors and Jira behind interfaces; Could items can be skipped without design changes |
| Alternatives | – |
| Validate | Milestone reviews against the Must list |
| Mentor | Yes (B-02 scope) |

### DA-18 Missing system responsibilities

| Aspect | Finding |
|---|---|
| Existing | – |
| Concern | Responsibilities with no owner |
| Findings and fixes | Emerging-issue detection (CR-06, SVC-13); product context for generation (CR-07); evaluation dataset management (CR-08, SVC-22); effort suggestion call point (CR-09, CP-10); reconciliation search for Jira (CR-11); backups (SEC-20, doc 10 §6.3); readiness check (NFR-11); retention of call logs (doc 07 §8); in v1.1: unknown customer identity (CR-18), spam-check failure state (CR-19), assistant priority over background model calls (doc 04 §5.2) |
| Validate | Traceability in §7 |
| Mentor | Yes, via the listed CRs |

## 5. SRS change register

**Status of every item: proposed, not approved.** The SRS is unchanged until the mentor accepts an item; all existing IDs are preserved. CR-17 to CR-19 were added in v1.1.

| CR | Affects | Current | Proposed | Reason | Design dependency |
|---|---|---|---|---|---|
| CR-01 | AC-ING-01, DR-31 | AC-ING-01 omits failed rows; terms overlap because duplicates and filtered records are stored | Keep DR-40's identity and define its terms as disjoint outcomes (doc 06 §10.1); AC-ING-01 becomes received = imported + rejected + duplicates + filtered + failed = N; DR-31's report adds "awaiting spam review" | DA-01 | doc 06 §10 |
| CR-02 | A-09, DR-12 | Fewer than 3 words is noise | Noise = no alphabetic word, or boilerplate match, or fewer than 3 words with no signal term; short problem reports are kept | DA-02 | doc 03 SVC-05, doc 06 §5 |
| CR-03 | A-13, FR-DOC-09 | Generalised claims need ≥ 3 customers | Keep; add exception: a `critical_signal` record (bug report or performance issue, negative, severity term) may be cited as "an individual report", and critical reports are listed on the dashboard | DA-03 | SVC-10, SVC-17 |
| CR-04 | A-12, AIR-02, FR-THM-08 | Threshold 0.6 on unspecified confidence | Confidence = calibrated classifier probability or Platt-scaled label log-probability; threshold set on validation data; ECE reported | DA-04 | doc 04 §6 |
| CR-05 | FR-THM-12 | Could | Should | DA-14 | ADR-10 |
| CR-06 | New FR-DSH-10 (Should) | – | "The system shall flag a theme as emerging when its weekly count exceeds its prior 8-week mean plus 3 standard deviations and is at least 5 records." | G-18 | SVC-13, theme_run_stats.emerging |
| CR-07 | New FR-AUTH-13 (Should) | – | "The system shall let an Owner record a product profile (name, description, target users, glossary) used as context for generated documents." | G-09 | workspaces columns, CP-06 |
| CR-08 | New AIR-26 (Should) | – | "The system shall store labelled evaluation datasets with frozen train, validation and test splits, and keep prompt examples out of the test split." | G-12 | SVC-22, evaluation tables |
| CR-09 | SRS §5.9 call points, FR-RMP-02 | No call point for suggested effort | Add call point CP-10 (effort suggestion, labelled as an estimate) | G-08 | doc 04 §3 |
| CR-10 | New FR-ING-13 (Could) | – | "The system shall support adding a data source through a connector that implements the source adapter interface." | G-14 | doc 01 §3.2 |
| CR-11 | AGR-15 | Jira allow-list: list projects and issue types, read fields, create issues | Add "search issues by the application's marker" for reconciliation of unknown outcomes | DA-12 | SVC-20 |
| CR-12 | FR-ING-09, DR-30 | FR-ING-09 shows original text to any user; DR-30 limits raw text with PII to Owners | FR-ING-09 applies to Owners; other roles see processed (masked) text beside the original structure | Contradiction found in design | API-27 |
| CR-13 | NFR-07 | No more than four continuously running services | Clarify that on-demand helpers (self-hosted MCP server, started only during a Jira operation) are not continuously running | ADR-15 | doc 01 §2 |
| CR-14 | A-16, AGR-03 | Any AI workflow stops after 5 minutes | Per job type limits: assistant 5 minutes as a strict deadline from request start, document generation 15 min, analysis 120 min, ingestion 60 min, score suggestions 10 min, Jira batch 5 min | G-10 | SVC-21, doc 04 §5.2 |
| CR-15 | A-15, AIR-11 | 120 s for every model call | Per call point: 120 s default, 300 s for long generation (CP-06 sections, CP-08), 90 s per assistant turn | G-11 | doc 04 §3.1 |
| CR-16 | DR-16, DR-18 | Exact duplicate = identical standardised text in the workspace | Identical text from the same customer, or from records with no customer key in the same source within 24 hours, is a duplicate; identical text from different customers is corroboration and counts each customer (many identical texts across customers feed the spam score instead) | Otherwise "app crashes" from 40 people counts as 1 | SVC-07 |
| CR-17 | SRS §4.2 lifecycle table, DR-03, DR-17 | L1 to L10 listed in an order with de-duplication before standardisation and masking, and near duplicates in ingestion | State that L1 to L10 are logical stages; the physical order is the design's canonical order (doc 06 §1); exact duplicates are detected after masking, near duplicates in each analysis run after embedding | v1.1 correction: masked hash and customer scope need this order; vectors exist only in analysis | doc 06 §1 |
| CR-18 | A-11, A-13, FR-THM-05, FR-AGG-04, FR-DSH-01, FR-PRI-02 | "Unique customers" undefined when records have no customer identifier | Unique-customer counts and Reach use known identities only; records without an identifier are shown as "unknown identity" with identity coverage; vocal flag shown as "not assessable" below 50% coverage; A-13 counts known customers only, and 3 or more unknown-identity records may support only the wording "N separate reports (customer identity unknown)" | v1.1 correction: the earlier LLD counted each unidentified record as a customer, inflating Reach | SVC-05, SVC-10, SVC-15, SVC-17 |
| CR-19 | DR-13, DR-31 | Spam flagged or not; no state for a failed check | Add "awaiting spam review": a record whose spam check could not complete is excluded from analysis, statistics, retrieval and generation until an Editor resolves it or a retry succeeds; counted separately in the import report | v1.1 correction: a failed check was previously treated as "not spam" | doc 06 §3.1 |

## 6. Experiments

None has been run; all are **pending**. Each will produce an `evaluation_runs` row and replace the [E] values it covers.

| EXP | Question | Method | Success criterion | Decides | When | Status |
|---|---|---|---|---|---|---|
| EXP-01 | Real speed and memory of CP-02 per record vs batch sizes 5, 10, 20; peak RAM and VRAM during analysis and PRD generation | 500 validation records on the reference laptop; record Ollama durations and `nvidia-smi` samples | Batch accuracy within 2 points of per-record; no CPU offload at chosen `num_ctx` | Batch size, context sizes, analysis-time estimate | M1 | Pending |
| EXP-02 | Is `qwen3:8b` better than `qwen3:4b` for PRDs and summaries? | 5 opportunities, both models, blind rubric by three reviewers, automatic checks, timings | 8B chosen only if rubric gain is clear and generation fits CR-14 limits | ADR-08 generation model | M3 | Pending |
| EXP-03 | Assistant model, tool reliability and deadline behaviour | 30 questions with 4B and 8B; measure turn times, whether Ollama stops generating when the gateway abandons a call, and waiting time behind worker model calls with the advisory lock | Higher grounded-answer and termination rates within NFR-04; 100% of replies within the 5-minute deadline | Assistant model; deadline reserve; interactive priority | M3 | Pending |
| EXP-04 | Embedding model and batch size; vector dimension | `qwen3-embedding:0.6b` vs `nomic-embed-text` vs `qwen3-embedding:4b` on duplicates, themes, retrieval; confirm 1,024 dimensions | Best quality that fits memory | Embedding model, near-duplicate threshold (A-10) | M2 | Pending |
| EXP-05 | Retrieval configuration | Vector, full-text, RRF, RRF+MMR; exact scan vs HNSW with iterative scan | Best recall@10 and nDCG@10; latency acceptable | Retrieval defaults, RRF score floor | M3 | Pending |
| EXP-06 | Clustering parameters | `eom` vs `leaf`, `min_cluster_size` grid, second pass on/off; stability across 2 runs | Best ARI with small-theme recall reported | Clustering config | M2 | Pending |
| EXP-07 | Thinking on or off for CP-03 and CP-05 | Same inputs both ways, quality and latency; check schema compliance with thinking | Thinking used only if quality gain justifies time and output stays valid | `think` setting | M2 | Pending |
| EXP-08 | Agreement of CP-07 support check with humans | 100 claim–evidence pairs labelled by two reviewers | κ reported; statuses stay "advisory" unless agreement is substantial | How CP-07 is displayed | M3 | Pending |
| EXP-09 | Classification cascade | Classifier alone, LLM alone, cascade; ECE and error capture | Cascade macro-F1 not below LLM alone, with lower time | Acceptance threshold for Stage A, A-12 value | M2 | Pending |
| EXP-10 | PII masking recall and speed | Seeded PII set (e-mail, phone formats, cards, IDs, names) | 0 seeded structured PII leaks; name recall reported | Recogniser set, model size | M1 | Pending |
| EXP-11 | Language detection on short texts | Labelled short and long texts in several languages | Error rate reported; `und` handling decided | Detector and minimum length | M1 | Pending |
| EXP-12 | Environment and integration spike | Install Python 3.12 packages on Windows; pgvector native build vs Docker; Rovo MCP with OAuth and API token, and `mcp-atlassian`, on a test Jira site | All packages install; one PostgreSQL option works; at least one Jira adapter creates and finds an issue | AR-02, ADR-15 adapter, setup guide | M1 | Pending |

## 7. Traceability and coverage

### 7.1 Brief objectives to modules and design

| Brief module | SRS | Components | Services | Workflow | Main tables | Main APIs | AI calls | Tests |
|---|---|---|---|---|---|---|---|---|
| 1 Authentication and workspaces | FR-AUTH | CMP-02, CMP-03 | SVC-01 | WF-A | users, sessions, workspaces, workspace_memberships | API-01 to API-13 | – | TST-02, TST-11, TST-12 |
| 2 Feedback and ticket ingestion | FR-ING, DR | CMP-04 to CMP-09 | SVC-02 to SVC-08 | WF-B, WF-C | source_files, import_jobs, feedback_records | API-14 to API-25, API-88 | CP-01, EMBED | TST-04, TST-14, TST-19 |
| 3 Product analytics | FR-ANA | CMP-16 | SVC-13 | WF-E | metric_definitions, metric_observations, product_releases, theme_metric_links | API-42 to API-46 | – | TST-01, TST-04 |
| 4 Classification and themes | FR-THM, AIR-01 to AIR-04 | CMP-13, CMP-14 | SVC-09 to SVC-11 | WF-D | record_classifications, themes, theme_memberships, theme_overrides, theme_run_stats | API-29 to API-36 | CP-02, CP-03 | TST-05 |
| 5 Feature request aggregation | FR-AGG | CMP-15 | SVC-12 | WF-D | aggregated_requests, request_memberships | API-37 to API-41 | CP-04 | TST-06 |
| 6 Prioritisation and impact | FR-PRI | CMP-18 | SVC-15 | WF-F | opportunities, scoring_configs, score_inputs, score_snapshots | API-49 to API-57 | CP-05, CP-10 | TST-07 |
| 7 PRD and user stories | FR-DOC, AIR-13 to AIR-19 | CMP-19, CMP-20 | SVC-16, SVC-17 | WF-G | documents, document_versions, user_stories, acceptance_criteria, claims, verification_results, approvals | API-58 to API-67 | CP-06, CP-07 | TST-08 |
| 8 Roadmap | FR-RMP | CMP-26 | SVC-18 | WF-H | roadmaps, roadmap_items, roadmap_dependencies | API-68 to API-73 | CP-10 | TST-01 |
| 9 Conversational assistant | FR-AST, AGR-06 to AGR-11 | CMP-21, CMP-17 | SVC-19, SVC-14 | WF-I | chat_sessions, chat_messages, tool_call_records | API-74 to API-77 | CP-09, CP-07 | TST-10, TST-13 |
| 10 Reporting and dashboard | FR-DSH | CMP-27 | SVC-23 | WF-D, WF-G | theme_run_stats, score_snapshots, documents | API-47, API-48, API-59 | CP-08 | TST-01, TST-08 |
| Cross-cutting: Jira | AGR-12 to AGR-27 | CMP-23 | SVC-20 | WF-J | integration_configs, integration_actions, external_item_links | API-78 to API-83 | – | TST-16 |

### 7.2 Coverage summary

| Status | Count | Meaning |
|---|---|---|
| Covered | 216 | Component, service, data, interface and test identified |
| Covered; needs an experiment | 12 | Design complete; parameter or feasibility confirmed by the named EXP |
| Covered as proposed in a CR | 22 | Design implements the CR's proposed wording; mentor decision needed |
| Partial | 0 | The screen-level gaps of v1.0 (IR-01, IR-02, NFR-16, NFR-19, NFR-20) are covered by doc 12 |
| Deferred (Future) | 3 | FR-AUTH-12, AGR-26, AGR-27: extension points only, as the SRS priority says |
| Unsupported | 0 | – |
| **Total** | **253** | Every SRS requirement appears below |

### 7.3 Requirement-level traceability

AI call "all CP" means the requirement governs every model call point. Test column lists SRS test activities; concrete test cases are in doc 10 §8.4. Screens are in doc 12 §8.

| ID | Pri | Components | Services | Tables | API | AI call | Workflow | Test | Status |
|---|---|---|---|---|---|---|---|---|---|
| FR-AUTH-01 | Must | CMP-02, CMP-03 | SVC-01 | users, sessions, login_attempts | API-01 to API-04 | – | WF-A | TST-02, TST-11 | Covered |
| FR-AUTH-02 | Must | CMP-02, CMP-03 | SVC-01 | users, sessions, login_attempts | API-01 to API-04 | – | WF-A | TST-02, TST-11 | Covered |
| FR-AUTH-03 | Must | CMP-02, CMP-03 | SVC-01 | users, sessions, login_attempts | API-01 to API-04 | – | WF-A | TST-02, TST-11 | Covered |
| FR-AUTH-04 | Should | CMP-02, CMP-03 | SVC-01 | users, sessions, login_attempts | API-01 to API-04 | – | WF-A | TST-02, TST-11 | Covered |
| FR-AUTH-05 | Must | CMP-02, CMP-24 | SVC-01 | workspaces, workspace_memberships; workspace_id on all tenant tables | API-05 to API-07 | – | WF-A | TST-03, TST-12 | Covered |
| FR-AUTH-06 | Must | CMP-02, CMP-24 | SVC-01 | workspaces, workspace_memberships; workspace_id on all tenant tables | API-05 to API-07 | – | WF-A | TST-03, TST-12 | Covered |
| FR-AUTH-07 | Must | CMP-02, CMP-24 | SVC-01 | workspaces, workspace_memberships; workspace_id on all tenant tables | API-05 to API-07 | – | WF-A | TST-03, TST-12 | Covered |
| FR-AUTH-08 | Should | CMP-02 | SVC-01 | workspace_memberships | API-04, API-10 to API-13 | – | WF-A | TST-01, TST-02 | Covered |
| FR-AUTH-09 | Should | CMP-02 | SVC-01 | workspace_memberships | API-04, API-10 to API-13 | – | WF-A | TST-01, TST-02 | Covered |
| FR-AUTH-10 | Should | CMP-02 | SVC-01 | workspace_memberships | API-04, API-10 to API-13 | – | WF-A | TST-01, TST-02 | Covered |
| FR-AUTH-11 | Could | CMP-02, CMP-22 | SVC-01, SVC-21 | workspaces (cascade) | API-09 | – | WF-A | TST-01 | Covered |
| FR-AUTH-12 | Future | CMP-02 | SVC-01 | users | – | – | – | – | Deferred (Future): extension point only |
| FR-ING-01 | Must | CMP-04, CMP-05, CMP-06 | SVC-02, SVC-03, SVC-04 | source_files, data_sources, import_jobs | API-14, API-15 | – | WF-B | TST-04 | Covered |
| FR-ING-02 | Must | CMP-05 | SVC-03 | import_jobs, feedback_records.source_type | API-15 | – | WF-B | TST-04 | Covered |
| FR-ING-03 | Must | CMP-04, CMP-05, CMP-06 | SVC-02, SVC-03, SVC-04 | source_files, data_sources, import_jobs | API-14, API-15 | – | WF-B | TST-04 | Covered |
| FR-ING-04 | Must | CMP-05, CMP-10, CMP-22 | SVC-03, SVC-21 | import_jobs, jobs | API-16, API-17, API-23, API-24 | – | WF-B | TST-04, TST-18 | Covered |
| FR-ING-05 | Must | CMP-05, CMP-10, CMP-22 | SVC-03, SVC-21 | import_jobs, jobs | API-16, API-17, API-23, API-24 | – | WF-B | TST-04, TST-18 | Covered |
| FR-ING-06 | Must | CMP-07, CMP-24 | SVC-03, SVC-14 | feedback_records.id (E-codes map to it) | API-26, API-27 | – | WF-B | TST-03 | Covered |
| FR-ING-07 | Should | CMP-05, CMP-22 | SVC-03, SVC-21 | feedback_records unique key, jobs.cursor | API-88 | – | WF-B | TST-19 | Covered |
| FR-ING-08 | Should | CMP-05, CMP-10, CMP-22 | SVC-03, SVC-21 | import_jobs, jobs | API-16, API-17, API-23, API-24 | – | WF-B | TST-04, TST-18 | Covered |
| FR-ING-09 | Should | CMP-01, CMP-07 | SVC-06 | feedback_records.raw_text, processed_text | API-27 | – | WF-C | TST-14 | Covered as proposed in CR-12 |
| FR-ING-10 | Could | CMP-05 | SVC-03 | source_files | API-14 | – | WF-B | TST-01 | Covered |
| FR-ING-11 | Could | CMP-05 | SVC-03 | column_mappings | API-20 | – | WF-B | TST-01 | Covered |
| FR-ING-12 | Could | CMP-05, CMP-22 | SVC-03, SVC-21 | import_jobs and dependants | API-19 | – | WF-B | TST-01 | Covered |
| FR-ANA-01 | Must | CMP-05, CMP-16 | SVC-03, SVC-13 | metric_definitions, metric_observations | API-15, API-42 | – | WF-E | TST-04 | Covered |
| FR-ANA-02 | Must | CMP-16, CMP-01 | SVC-13 | product_releases, metric_observations | API-43, API-44 | – | WF-E | TST-01 | Covered |
| FR-ANA-03 | Should | CMP-16, CMP-01 | SVC-13 | product_releases, metric_observations | API-43, API-44 | – | WF-E | TST-01 | Covered |
| FR-ANA-04 | Should | CMP-16 | SVC-13 | theme_metric_links | API-45 | – | WF-E | TST-01 | Covered |
| FR-ANA-05 | Should | CMP-16 | SVC-13 | theme_run_stats, metric_observations, theme_metric_links | API-46 | – | WF-E | TST-01 | Covered |
| FR-ANA-06 | Could | CMP-16 | SVC-13 | theme_metric_links | API-45 | – | WF-E | TST-01 | Covered |
| FR-THM-01 | Must | CMP-13 | SVC-09 | record_classifications | API-31 | CP-02 | WF-D | TST-05 | Covered |
| FR-THM-02 | Must | CMP-13 | SVC-09 | record_classifications | API-31 | CP-02 | WF-D | TST-05 | Covered |
| FR-THM-03 | Must | CMP-14 | SVC-10, SVC-11 | themes, theme_memberships | API-31, API-33 | CP-03 | WF-D | TST-05 | Covered |
| FR-THM-04 | Must | CMP-14, CMP-27 | SVC-11, SVC-23 | theme_run_stats, theme_memberships | API-26, API-33, API-34 | – | WF-D | TST-05, TST-01 | Covered |
| FR-THM-05 | Must | CMP-14, CMP-27 | SVC-11, SVC-23 | theme_run_stats, theme_memberships | API-26, API-33, API-34 | – | WF-D | TST-05, TST-01 | Covered as proposed in CR-18 |
| FR-THM-06 | Must | CMP-14 | SVC-11 | theme_run_stats.vocal_flag | API-34 | – | WF-D | TST-05 | Covered as proposed in CR-18 |
| FR-THM-07 | Should | CMP-14, CMP-27 | SVC-11, SVC-23 | theme_run_stats, theme_memberships | API-26, API-33, API-34 | – | WF-D | TST-05, TST-01 | Covered |
| FR-THM-08 | Should | CMP-13 | SVC-09 | review_items, record_classifications | API-29, API-30 | CP-02 | WF-D | TST-05 | Covered as proposed in CR-04 |
| FR-THM-09 | Should | CMP-14 | SVC-11 | theme_overrides, themes | API-35, API-36 | – | WF-D | TST-05, TST-01 | Covered |
| FR-THM-10 | Should | CMP-13 | SVC-09 | review_items, record_classifications | API-29, API-30 | CP-02 | WF-D | TST-05 | Covered |
| FR-THM-11 | Could | CMP-14 | SVC-11 | theme_overrides, themes | API-35, API-36 | – | WF-D | TST-05, TST-01 | Covered |
| FR-THM-12 | Could | CMP-14 | SVC-11 | theme_overrides, themes | API-35, API-36 | – | WF-D | TST-05, TST-01 | Covered as proposed in CR-05 |
| FR-AGG-01 | Must | CMP-15 | SVC-12 | aggregated_requests, request_memberships | API-31, API-37, API-38 | CP-04 | WF-D | TST-06 | Covered |
| FR-AGG-02 | Should | CMP-15 | SVC-12 | aggregated_requests, request_memberships | API-31, API-37, API-38 | CP-04 | WF-D | TST-06 | Covered |
| FR-AGG-03 | Must | CMP-15 | SVC-12 | aggregated_requests, request_memberships | API-31, API-37, API-38 | CP-04 | WF-D | TST-06 | Covered |
| FR-AGG-04 | Must | CMP-15, CMP-27 | SVC-12, SVC-23 | request_memberships, feedback_records | API-37 | – | WF-D | TST-06 | Covered as proposed in CR-18 |
| FR-AGG-05 | Should | CMP-15 | SVC-12 | aggregated_requests, request_memberships | API-39 to API-41 | – | WF-D | TST-01 | Covered |
| FR-AGG-06 | Could | CMP-15 | SVC-12 | request_memberships.low_confidence, review_items | API-29, API-37 | CP-04 | WF-D | TST-06 | Covered |
| FR-AGG-07 | Could | CMP-15, CMP-27 | SVC-12, SVC-23 | request_memberships, feedback_records | API-37 | – | WF-D | TST-06 | Covered |
| FR-PRI-01 | Must | CMP-18 | SVC-15 | opportunities | API-50, API-51 | – | WF-F | TST-07 | Covered |
| FR-PRI-02 | Must | CMP-18 | SVC-15 | scoring_configs, score_inputs, score_snapshots | API-49, API-52, API-53, API-55, API-56 | – | WF-F | TST-07 | Covered as proposed in CR-18 |
| FR-PRI-03 | Must | CMP-18 | SVC-15 | scoring_configs, score_inputs, score_snapshots | API-49, API-52, API-53, API-55, API-56 | – | WF-F | TST-07 | Covered |
| FR-PRI-04 | Must | CMP-18 | SVC-15 | scoring_configs, score_inputs, score_snapshots | API-49, API-52, API-53, API-55, API-56 | – | WF-F | TST-07 | Covered |
| FR-PRI-05 | Must | CMP-18 | SVC-15 | scoring_configs, score_inputs, score_snapshots | API-49, API-52, API-53, API-55, API-56 | – | WF-F | TST-07 | Covered |
| FR-PRI-06 | Should | CMP-18 | SVC-15 | scoring_configs, score_inputs, score_snapshots | API-49, API-52, API-53, API-55, API-56 | – | WF-F | TST-07 | Covered |
| FR-PRI-07 | Should | CMP-18, CMP-20 | SVC-15, SVC-17 | score_inputs, claims, claim_evidence | API-52, API-54 | CP-05, CP-07 | WF-F | TST-07, TST-08 | Covered |
| FR-PRI-08 | Should | CMP-18 | SVC-15, SVC-13 | score_inputs, score_snapshots, theme_metric_links | API-52, API-56 | – | WF-F | TST-07 | Covered |
| FR-PRI-09 | Should | CMP-18, CMP-20 | SVC-15, SVC-17 | score_inputs, claims, claim_evidence | API-52, API-54 | CP-05, CP-07 | WF-F | TST-07, TST-08 | Covered |
| FR-PRI-10 | Could | CMP-18 | SVC-15, SVC-13 | score_inputs, score_snapshots, theme_metric_links | API-52, API-56 | – | WF-F | TST-07 | Covered |
| FR-PRI-11 | Could | CMP-18 | SVC-15 | opportunities.status, decision_reason | API-57 | – | WF-F | TST-01 | Covered |
| FR-DOC-01 | Must | CMP-19, CMP-17 | SVC-16, SVC-14 | documents, document_versions | API-58 | CP-06 | WF-G | TST-08 | Covered |
| FR-DOC-02 | Must | CMP-19, CMP-17 | SVC-16, SVC-14 | documents, document_versions | API-58 | CP-06 | WF-G | TST-08 | Covered |
| FR-DOC-03 | Must | CMP-20 | SVC-17 | claims, claim_evidence, verification_results | API-61, API-64 | CP-06, CP-07 | WF-G | TST-08 | Covered |
| FR-DOC-04 | Must | CMP-20 | SVC-17 | claims, claim_evidence, verification_results | API-61, API-64 | CP-06, CP-07 | WF-G | TST-08 | Covered |
| FR-DOC-05 | Must | CMP-19 | SVC-16 | user_stories, acceptance_criteria | API-58, API-63 | CP-06 | WF-G | TST-08 | Covered |
| FR-DOC-06 | Must | CMP-19 | SVC-16 | user_stories, acceptance_criteria | API-58, API-63 | CP-06 | WF-G | TST-08 | Covered |
| FR-DOC-07 | Must | CMP-01, CMP-20 | SVC-17 | claim_evidence, feedback_records | API-65 | – | WF-G | TST-08 | Covered |
| FR-DOC-08 | Must | CMP-20 | SVC-17 | approvals, documents.status | API-66 | – | WF-G | TST-08, TST-01 | Covered |
| FR-DOC-09 | Should | CMP-20 | SVC-17 | claims, claim_evidence, verification_results | API-61, API-64 | CP-06, CP-07 | WF-G | TST-08 | Covered as proposed in CR-03, CR-18 |
| FR-DOC-10 | Should | CMP-19 | SVC-16 | document_versions | API-62, API-67 | – | WF-G | TST-01 | Covered |
| FR-DOC-11 | Should | CMP-19 | SVC-16 | document_versions | API-62, API-67 | – | WF-G | TST-01 | Covered |
| FR-DOC-12 | Could | CMP-19, CMP-17 | SVC-16, SVC-14 | documents, document_versions | API-58 | CP-06 | WF-G | TST-08 | Covered |
| FR-RMP-01 | Must | CMP-26 | SVC-18 | roadmaps, roadmap_items, roadmap_dependencies | API-68 to API-73 | – | WF-H | TST-01 | Covered |
| FR-RMP-02 | Must | CMP-26, CMP-18 | SVC-18, SVC-15 | roadmap_items.effort_weeks, effort_origin; score_inputs | API-54, API-70 | CP-10 | WF-H | TST-01 | Covered as proposed in CR-09 |
| FR-RMP-03 | Must | CMP-26 | SVC-18 | roadmaps, roadmap_items, roadmap_dependencies | API-68 to API-73 | – | WF-H | TST-01 | Covered |
| FR-RMP-04 | Should | CMP-26 | SVC-18 | roadmaps, roadmap_items, roadmap_dependencies | API-68 to API-73 | – | WF-H | TST-01 | Covered |
| FR-RMP-05 | Should | CMP-26 | SVC-18 | roadmaps, roadmap_items, roadmap_dependencies | API-68 to API-73 | – | WF-H | TST-01 | Covered |
| FR-RMP-06 | Should | CMP-26 | SVC-18 | roadmaps, roadmap_items, roadmap_dependencies | API-68 to API-73 | – | WF-H | TST-01 | Covered |
| FR-RMP-07 | Could | CMP-26 | SVC-18 | roadmaps, roadmap_items, roadmap_dependencies | API-68 to API-73 | – | WF-H | TST-01 | Covered |
| FR-AST-01 | Must | CMP-21, CMP-17 | SVC-19, SVC-14, SVC-17 | chat_messages, tool_call_records, claims | API-76 | CP-09 | WF-I | TST-10 | Covered |
| FR-AST-02 | Must | CMP-21, CMP-17 | SVC-19, SVC-14, SVC-17 | chat_messages, tool_call_records, claims | API-76 | CP-09 | WF-I | TST-10 | Covered |
| FR-AST-03 | Must | CMP-21, CMP-17 | SVC-19, SVC-14, SVC-17 | chat_messages, tool_call_records, claims | API-76 | CP-09 | WF-I | TST-10 | Covered |
| FR-AST-04 | Must | CMP-21, CMP-17 | SVC-19, SVC-14, SVC-17 | chat_messages, tool_call_records, claims | API-76 | CP-09 | WF-I | TST-10 | Covered |
| FR-AST-05 | Must | CMP-21, CMP-17 | SVC-19, SVC-14, SVC-17 | chat_messages, tool_call_records, claims | API-76 | CP-09 | WF-I | TST-10 | Covered |
| FR-AST-06 | Should | CMP-21, CMP-17 | SVC-19, SVC-14, SVC-17 | chat_messages, tool_call_records, claims | API-76 | CP-09 | WF-I | TST-10 | Covered |
| FR-AST-07 | Should | CMP-21, CMP-17 | SVC-19, SVC-14, SVC-17 | chat_messages, tool_call_records, claims | API-76 | CP-09 | WF-I | TST-10 | Covered |
| FR-AST-08 | Could | CMP-21, CMP-17 | SVC-19, SVC-14, SVC-17 | chat_messages, tool_call_records, claims | API-76 | CP-09 | WF-I | TST-10 | Covered |
| FR-AST-09 | Could | CMP-21 | SVC-19 | chat_sessions, chat_messages | API-74, API-75, API-77 | – | WF-I | TST-01 | Covered |
| FR-AST-10 | Could | CMP-21 | SVC-19 | chat_sessions, chat_messages | API-74, API-75, API-77 | – | WF-I | TST-01 | Covered |
| FR-DSH-01 | Must | CMP-27, CMP-01 | SVC-23 | theme_run_stats, score_snapshots, import_jobs, analysis_runs | API-26, API-47 | – | WF-D, WF-F | TST-01, TST-18 | Covered as proposed in CR-18 |
| FR-DSH-02 | Must | CMP-27, CMP-01 | SVC-23 | theme_run_stats, score_snapshots, import_jobs, analysis_runs | API-26, API-47 | – | WF-D, WF-F | TST-01, TST-18 | Covered |
| FR-DSH-03 | Must | CMP-19, CMP-20 | SVC-16, SVC-17 | documents (executive_summary), claims | API-59 | CP-08, CP-07 | WF-G | TST-08 | Covered |
| FR-DSH-04 | Should | CMP-27, CMP-01 | SVC-23 | theme_run_stats, score_snapshots, import_jobs, analysis_runs | API-26, API-47 | – | WF-D, WF-F | TST-01, TST-18 | Covered |
| FR-DSH-05 | Should | CMP-27, CMP-01 | SVC-23 | theme_run_stats, score_snapshots, import_jobs, analysis_runs | API-26, API-47 | – | WF-D, WF-F | TST-01, TST-18 | Covered |
| FR-DSH-06 | Should | CMP-27, CMP-01 | SVC-23 | theme_run_stats, score_snapshots, import_jobs, analysis_runs | API-26, API-47 | – | WF-D, WF-F | TST-01, TST-18 | Covered |
| FR-DSH-07 | Should | CMP-27, CMP-01 | SVC-23 | theme_run_stats, score_snapshots, import_jobs, analysis_runs | API-26, API-47 | – | WF-D, WF-F | TST-01, TST-18 | Covered |
| FR-DSH-08 | Could | CMP-16, CMP-27 | SVC-13 | theme_metric_links, metric_observations | API-46 | – | WF-E | TST-01 | Covered |
| FR-DSH-09 | Could | CMP-27 | SVC-23 | documents, theme_run_stats | API-48, API-67 | – | WF-G | TST-01 | Covered |
| DR-01 | Must | CMP-05 | SVC-03 | import_jobs, feedback_records | API-15 | – | WF-B | TST-04 | Covered |
| DR-02 | Must | CMP-05 | SVC-03 | import_jobs, feedback_records | API-15 | – | WF-B | TST-04 | Covered |
| DR-03 | Should | CMP-08, CMP-22 | SVC-05, SVC-21 | feedback_records.stage, jobs (reprocess) | API-31 | – | WF-C | TST-04 | Covered as proposed in CR-17 |
| DR-04 | Should | CMP-08, CMP-22 | SVC-05, SVC-21 | feedback_records.stage, jobs (reprocess) | API-31 | – | WF-C | TST-04 | Covered |
| DR-05 | Must | CMP-06 | SVC-04 | source_files, import_row_errors, feedback_records | API-14, API-18 | – | WF-B | TST-04 | Covered |
| DR-06 | Must | CMP-06 | SVC-04 | source_files, import_row_errors, feedback_records | API-14, API-18 | – | WF-B | TST-04 | Covered |
| DR-07 | Should | CMP-06 | SVC-04 | source_files, import_row_errors, feedback_records | API-14, API-18 | – | WF-B | TST-04 | Covered |
| DR-08 | Should | CMP-06 | SVC-04 | source_files, import_row_errors, feedback_records | API-14, API-18 | – | WF-B | TST-04 | Covered |
| DR-09 | Should | CMP-06 | SVC-04 | source_files, import_row_errors, feedback_records | API-14, API-18 | – | WF-B | TST-04 | Covered |
| DR-10 | Should | CMP-06 | SVC-04 | source_files, import_row_errors, feedback_records | API-14, API-18 | – | WF-B | TST-04 | Covered |
| DR-11 | Must | CMP-08 | SVC-05 | feedback_records (exclusion_reason, spam_status, spam_score), review_items | API-28, API-30 | CP-01 | WF-C | TST-04 | Covered |
| DR-12 | Should | CMP-08 | SVC-05 | feedback_records (exclusion_reason, spam_status, spam_score), review_items | API-28, API-30 | CP-01 | WF-C | TST-04 | Covered as proposed in CR-02 |
| DR-13 | Should | CMP-08 | SVC-05 | feedback_records (exclusion_reason, spam_status, spam_score), review_items | API-28, API-30 | CP-01 | WF-C | TST-04 | Covered as proposed in CR-19 |
| DR-14 | Could | CMP-08 | SVC-05 | feedback_records (exclusion_reason, spam_status, spam_score), review_items | API-28, API-30 | CP-01 | WF-C | TST-04 | Covered |
| DR-15 | Should | CMP-08 | SVC-05 | feedback_records (exclusion_reason, spam_status, spam_score), review_items | API-28, API-30 | CP-01 | WF-C | TST-04 | Covered |
| DR-16 | Must | CMP-08 | SVC-07 | feedback_records (content_hash, duplicate_of), record_classifications (near_duplicate_of) | API-27 | – | WF-C, WF-D | TST-04 | Covered as proposed in CR-16 |
| DR-17 | Should | CMP-08, CMP-11 | SVC-07 (analysis step 2) | record_classifications (status, near_duplicate_of), record_embeddings | API-31 | – | WF-D | TST-04 | Covered as proposed in CR-17 |
| DR-18 | Must | CMP-08 | SVC-07 | feedback_records (content_hash, duplicate_of), record_classifications (near_duplicate_of) | API-27 | – | WF-C, WF-D | TST-04 | Covered |
| DR-19 | Must | CMP-08 | SVC-05 | feedback_records, customers | – | – | WF-C | TST-04 | Covered |
| DR-20 | Must | CMP-08 | SVC-05 | feedback_records, customers | – | – | WF-C | TST-04 | Covered |
| DR-21 | Must | CMP-08 | SVC-05 | feedback_records, customers | – | – | WF-C | TST-04 | Covered |
| DR-22 | Should | CMP-08 | SVC-05 | feedback_records, customers | – | – | WF-C | TST-04 | Covered |
| DR-23 | Must | CMP-08 | SVC-05 | feedback_records, customers | – | – | WF-C | TST-04 | Covered |
| DR-24 | Should | CMP-08 | SVC-05 | feedback_records, customers | – | – | WF-C | TST-04 | Covered; needs EXP-11 |
| DR-25 | Should | CMP-08 | SVC-05 | feedback_records, customers | – | – | WF-C | TST-04 | Covered; needs EXP-11 |
| DR-26 | Must | CMP-11 | SVC-08 (analysis step 1) | record_embeddings | API-31 | EMBED | WF-D | TST-04, TST-09 | Covered |
| DR-27 | Could | CMP-08 | SVC-05 | feedback_records (segment_index, parent_record_id) | – | – | WF-C | TST-04 | Covered |
| DR-28 | Must | CMP-09 | SVC-06 | feedback_records (processed_text, pii_counts) | API-27 | – | WF-C | TST-14 | Covered; needs EXP-10 |
| DR-29 | Must | CMP-09 | SVC-06 | feedback_records (processed_text, pii_counts) | API-27 | – | WF-C | TST-14 | Covered |
| DR-30 | Should | CMP-09 | SVC-06 | feedback_records (processed_text, pii_counts) | API-27 | – | WF-C | TST-14 | Covered as proposed in CR-12 |
| DR-31 | Must | CMP-05 | SVC-03 | import_jobs.report | API-17 | – | WF-B | TST-04 | Covered as proposed in CR-01, CR-19 |
| DR-32 | Should | CMP-05 | SVC-03 | import_jobs.report | API-17 | – | WF-B | TST-04 | Covered |
| DR-33 | Should | CMP-07, CMP-24 | SVC-03, SVC-22 | feedback_records, analysis_runs, llm_call_records, prompt_versions | API-27, API-32 | – | WF-B, WF-D | TST-03 | Covered |
| DR-34 | Must | CMP-07, CMP-24 | SVC-03, SVC-22 | feedback_records, analysis_runs, llm_call_records, prompt_versions | API-27, API-32 | – | WF-B, WF-D | TST-03 | Covered |
| DR-35 | Should | CMP-07, CMP-24 | SVC-03, SVC-22 | feedback_records, analysis_runs, llm_call_records, prompt_versions | API-27, API-32 | – | WF-B, WF-D | TST-03 | Covered |
| DR-36 | Should | CMP-10, CMP-22 | SVC-21 | jobs, import_row_errors | API-18, API-88 | – | WF-B | TST-19 | Covered |
| DR-37 | Should | CMP-10, CMP-22 | SVC-21 | jobs, import_row_errors | API-18, API-88 | – | WF-B | TST-19 | Covered |
| DR-38 | Should | CMP-10, CMP-22 | SVC-21 | jobs, import_row_errors | API-18, API-88 | – | WF-B | TST-19 | Covered |
| DR-39 | Should | CMP-10, CMP-22 | SVC-21 | jobs, import_row_errors | API-18, API-88 | – | WF-B | TST-19 | Covered |
| DR-40 | Must | CMP-05 | SVC-03 | import_jobs.report | API-17 | – | WF-B | TST-04, TST-19 | Covered |
| DR-41 | Must | CMP-16 | SVC-13 | metric_observations | API-15 | – | WF-E | TST-04 | Covered |
| AIR-01 | Must | CMP-13 | SVC-09 | record_classifications, evaluation_runs | API-31, API-86 | CP-02 | WF-D | TST-05 | Covered |
| AIR-02 | Should | CMP-13 | SVC-09 | record_classifications, evaluation_runs | API-31, API-86 | CP-02 | WF-D | TST-05 | Covered as proposed in CR-04 |
| AIR-03 | Must | CMP-14 | SVC-11 | themes, theme_memberships, theme_run_stats, analysis_runs.config | API-31 | – | WF-D | TST-05 | Covered |
| AIR-04 | Should | CMP-14 | SVC-11 | themes, theme_memberships, theme_run_stats, analysis_runs.config | API-31 | – | WF-D | TST-05 | Covered; needs EXP-06 |
| AIR-05 | Must | CMP-17 | SVC-14 | feedback_records, record_embeddings | API-76, API-58 | CP-06, CP-09 | WF-G, WF-I | TST-09 | Covered |
| AIR-06 | Must | CMP-17 | SVC-14 | feedback_records, record_embeddings | API-76, API-58 | CP-06, CP-09 | WF-G, WF-I | TST-09 | Covered |
| AIR-07 | Must | CMP-17 | SVC-14 | feedback_records, record_embeddings | API-76, API-58 | CP-06, CP-09 | WF-G, WF-I | TST-09 | Covered |
| AIR-08 | Must | CMP-12, CMP-20 | SVC-17, SVC-15 | claims, score_inputs | – | all CP | WF-D, WF-F, WF-G | TST-08 | Covered |
| AIR-09 | Must | CMP-12 | LLM gateway | llm_call_records, prompt_versions | – | all CP | all | TST-15 | Covered |
| AIR-10 | Should | CMP-12 | LLM gateway | llm_call_records, prompt_versions | – | all CP | all | TST-15 | Covered |
| AIR-11 | Should | CMP-12 | LLM gateway | llm_call_records, prompt_versions | – | all CP | all | TST-15 | Covered as proposed in CR-15 |
| AIR-12 | Should | CMP-12 | LLM gateway | llm_call_records, prompt_versions | – | all CP | all | TST-15 | Covered |
| AIR-13 | Must | CMP-20 | SVC-17 | claims, claim_evidence, verification_results | API-61, API-64, API-65 | CP-07 | WF-G, WF-I | TST-08 | Covered |
| AIR-14 | Must | CMP-20 | SVC-17 | claims, claim_evidence, verification_results | API-61, API-64, API-65 | CP-07 | WF-G, WF-I | TST-08 | Covered |
| AIR-15 | Should | CMP-20 | SVC-17 | claims, claim_evidence, verification_results | API-61, API-64, API-65 | CP-07 | WF-G, WF-I | TST-08 | Covered |
| AIR-16 | Must | CMP-20 | SVC-17 | claims, claim_evidence, verification_results | API-61, API-64, API-65 | CP-07 | WF-G, WF-I | TST-08 | Covered |
| AIR-17 | Should | CMP-20 | SVC-17 | claims, claim_evidence, verification_results | API-61, API-64, API-65 | CP-07 | WF-G, WF-I | TST-08 | Covered; needs EXP-08 |
| AIR-18 | Should | CMP-20 | SVC-17 | claims, claim_evidence, verification_results | API-61, API-64, API-65 | CP-07 | WF-G, WF-I | TST-08 | Covered |
| AIR-19 | Should | CMP-20 | SVC-17 | claims, claim_evidence, verification_results | API-61, API-64, API-65 | CP-07 | WF-G, WF-I | TST-08 | Covered |
| AIR-20 | Must | CMP-25 | SVC-22 | evaluation_runs, prompt_versions, analysis_runs.config | API-85, API-86 | – | – | TST-22 | Covered |
| AIR-21 | Should | CMP-25 | SVC-22 | evaluation_runs, prompt_versions, analysis_runs.config | API-85, API-86 | – | – | TST-22 | Covered |
| AIR-22 | Should | CMP-12, CMP-03 | LLM gateway | – | API-87 | – | all | TST-15 | Covered |
| AIR-23 | Should | CMP-13 | SVC-09 | record_classifications, evaluation_runs | API-31, API-86 | CP-02 | WF-D | TST-05 | Covered |
| AIR-24 | Could | CMP-25 | SVC-22, SVC-09 | review_items.resolution, theme_overrides | API-30, API-35 | – | WF-D | TST-05 | Covered |
| AIR-25 | Could | CMP-12 | LLM gateway | llm_call_records, prompt_versions | – | all CP | all | TST-15 | Covered |
| AGR-01 | Must | CMP-22 | SVC-21 | jobs | API-23 to API-25 | – | all | TST-19, TST-15 | Covered |
| AGR-02 | Should | CMP-22 | SVC-21 | jobs | API-23 to API-25 | – | all | TST-19, TST-15 | Covered |
| AGR-03 | Must | CMP-22 | SVC-21 | jobs | API-23 to API-25 | – | all | TST-19, TST-15 | Covered as proposed in CR-14 |
| AGR-04 | Should | CMP-22 | SVC-21 | jobs | API-23 to API-25 | – | all | TST-19, TST-15 | Covered |
| AGR-05 | Should | CMP-22 | SVC-21 | jobs | API-23 to API-25 | – | all | TST-19, TST-15 | Covered |
| AGR-06 | Must | CMP-21 | SVC-19 | tool_call_records, chat_messages | API-76 | CP-09 | WF-I | TST-13, TST-10 | Covered |
| AGR-07 | Must | CMP-21 | SVC-19 | tool_call_records, chat_messages | API-76 | CP-09 | WF-I | TST-13, TST-10 | Covered |
| AGR-08 | Must | CMP-21 | SVC-19 | tool_call_records, chat_messages | API-76 | CP-09 | WF-I | TST-13, TST-10 | Covered |
| AGR-09 | Must | CMP-21 | SVC-19 | tool_call_records, chat_messages | API-76 | CP-09 | WF-I | TST-13, TST-10 | Covered |
| AGR-10 | Should | CMP-21 | SVC-19 | tool_call_records, chat_messages | API-76 | CP-09 | WF-I | TST-13, TST-10 | Covered |
| AGR-11 | Must | CMP-21 | SVC-19 | tool_call_records, chat_messages | API-76 | CP-09 | WF-I | TST-13, TST-10 | Covered |
| AGR-12 | Should | CMP-23 | SVC-20 | integration_configs, integration_actions, external_item_links, approvals | API-78 to API-83 | – | WF-J | TST-16 | Covered; needs EXP-12 |
| AGR-13 | Should | CMP-23 | SVC-20 | integration_configs, integration_actions, external_item_links, approvals | API-78 to API-83 | – | WF-J | TST-16 | Covered |
| AGR-14 | Should | CMP-23 | SVC-20 | integration_configs, integration_actions, external_item_links, approvals | API-78 to API-83 | – | WF-J | TST-16 | Covered; needs EXP-12 |
| AGR-15 | Should | CMP-23 | SVC-20 | integration_configs, integration_actions, external_item_links, approvals | API-78 to API-83 | – | WF-J | TST-16 | Covered as proposed in CR-11 |
| AGR-16 | Should | CMP-23 | SVC-20 | integration_configs, integration_actions, external_item_links, approvals | API-78 to API-83 | – | WF-J | TST-16 | Covered |
| AGR-17 | Should | CMP-23 | SVC-20 | integration_configs, integration_actions, external_item_links, approvals | API-78 to API-83 | – | WF-J | TST-16 | Covered |
| AGR-18 | Should | CMP-23 | SVC-20 | integration_configs, integration_actions, external_item_links, approvals | API-78 to API-83 | – | WF-J | TST-16 | Covered |
| AGR-19 | Should | CMP-23 | SVC-20 | integration_configs, integration_actions, external_item_links, approvals | API-78 to API-83 | – | WF-J | TST-16 | Covered |
| AGR-20 | Should | CMP-23 | SVC-20 | integration_configs, integration_actions, external_item_links, approvals | API-78 to API-83 | – | WF-J | TST-16 | Covered |
| AGR-21 | Should | CMP-23 | SVC-20 | integration_configs, integration_actions, external_item_links, approvals | API-78 to API-83 | – | WF-J | TST-16 | Covered |
| AGR-22 | Should | CMP-23 | SVC-20 | integration_configs, integration_actions, external_item_links, approvals | API-78 to API-83 | – | WF-J | TST-16 | Covered |
| AGR-23 | Should | CMP-23 | SVC-20 | integration_configs, integration_actions, external_item_links, approvals | API-78 to API-83 | – | WF-J | TST-16 | Covered |
| AGR-24 | Should | CMP-23 | SVC-20 | integration_configs, integration_actions, external_item_links, approvals | API-78 to API-83 | – | WF-J | TST-16 | Covered |
| AGR-25 | Should | CMP-23 | SVC-20 | integration_configs, integration_actions, external_item_links, approvals | API-78 to API-83 | – | WF-J | TST-16 | Covered |
| AGR-26 | Future | CMP-23 | SVC-20 | external_item_links | – | – | WF-J | – | Deferred (Future): extension point only |
| AGR-27 | Future | CMP-23 | SVC-20 | external_item_links | – | – | WF-J | – | Deferred (Future): extension point only |
| NFR-01 | Should | CMP-01, CMP-03, CMP-27 | SVC-21, SVC-23 | jobs, evaluation_runs (performance) | API-17, API-24, API-47, API-76 | – | WF-B, WF-I | TST-18 | Covered; needs EXP-01 |
| NFR-02 | Should | CMP-01, CMP-03, CMP-27 | SVC-21, SVC-23 | jobs, evaluation_runs (performance) | API-17, API-24, API-47, API-76 | – | WF-B, WF-I | TST-18 | Covered; needs EXP-01 |
| NFR-03 | Should | CMP-01, CMP-03, CMP-27 | SVC-21, SVC-23 | jobs, evaluation_runs (performance) | API-17, API-24, API-47, API-76 | – | WF-B, WF-I | TST-18 | Covered; needs EXP-01 |
| NFR-04 | Should | CMP-01, CMP-03, CMP-27 | SVC-21, SVC-23 | jobs, evaluation_runs (performance) | API-17, API-24, API-47, API-76 | – | WF-B, WF-I | TST-18 | Covered; needs EXP-03 |
| NFR-05 | Must | All (deployment) | – | – | API-87 | – | – | TST-18, TST-20 | Covered; needs EXP-01 |
| NFR-06 | Must | All (deployment) | – | – | API-87 | – | – | TST-18, TST-20 | Covered |
| NFR-07 | Should | All (deployment) | – | – | API-87 | – | – | TST-18, TST-20 | Covered as proposed in CR-13 |
| NFR-08 | Must | CMP-22, CMP-24 | SVC-21 | jobs, import_jobs.report | API-23 | – | WF-B | TST-19 | Covered |
| NFR-09 | Should | CMP-22, CMP-24 | SVC-21 | jobs, import_jobs.report | API-23 | – | WF-B | TST-19 | Covered |
| NFR-10 | Should | CMP-22, CMP-24 | SVC-21 | jobs, import_jobs.report | API-23 | – | WF-B | TST-19 | Covered |
| NFR-11 | Should | CMP-03 | SVC-21 | jobs | API-87 | – | – | TST-20 | Covered |
| NFR-12 | Should | CMP-12, CMP-18, CMP-23 | LLM gateway, SVC-15, SVC-20 | prompt_versions, scoring_configs, analysis_runs.config | API-49 | – | – | TST-22 | Covered |
| NFR-13 | Must | CMP-25 | SVC-22 | evaluation_runs | – | – | – | TST-22 | Covered |
| NFR-14 | Should | CMP-12, CMP-18, CMP-23 | LLM gateway, SVC-15, SVC-20 | prompt_versions, scoring_configs, analysis_runs.config | API-49 | – | – | TST-22 | Covered |
| NFR-15 | Should | CMP-25 | SVC-22 | evaluation_runs | – | – | – | TST-22 | Covered |
| NFR-16 | Should | CMP-01 (doc 12 §1, §4, §6) | – | – | All (error envelope) | – | all | TST-17 | Covered |
| NFR-17 | Must | CMP-01, CMP-17 | SVC-17 | claim_evidence | API-65, API-26 | – | WF-G | TST-17 | Covered |
| NFR-18 | Should | CMP-01 (doc 12 §1, §4, §6) | – | – | All (error envelope) | – | all | TST-17 | Covered |
| NFR-19 | Should | CMP-01 (doc 12 §1, §4, §6) | – | – | All (error envelope) | – | all | TST-17 | Covered |
| NFR-20 | Should | CMP-01 (doc 12 §1, §4, §6) | – | – | All (error envelope) | – | all | TST-17 | Covered |
| NFR-21 | Must | CMP-09, CMP-12 | SVC-06, LLM gateway | feedback_records.processed_text | – | all CP | WF-C | TST-14 | Covered |
| NFR-22 | Must | CMP-24, CMP-02 | SVC-01 | all tenant tables (RLS) | All | – | – | TST-12 | Covered |
| NFR-23 | Should | CMP-19, CMP-25 | SVC-16, SVC-22 | document_versions (model_tags, prompt_versions) | API-61 | – | WF-G | TST-21 | Covered |
| NFR-24 | Should | CMP-25, CMP-12 | SVC-22 | llm_call_records, audit_logs | – | – | – | TST-21 | Covered |
| NFR-25 | Should | CMP-25, CMP-12 | SVC-22 | llm_call_records, audit_logs | – | – | – | TST-21 | Covered |
| NFR-26 | Must | CMP-20 | SVC-17 | verification_results | API-61 | CP-07 | WF-G | TST-08 | Covered |
| NFR-27 | Must | CMP-20 | SVC-17 | verification_results | API-61 | CP-07 | WF-G | TST-08 | Covered |
| NFR-28 | Must | CMP-25 | SVC-22 | evaluation_datasets, evaluation_items, evaluation_runs | API-85, API-86 | – | – | TST-05 to TST-10 | Covered |
| NFR-29 | Should | CMP-20 | SVC-17 | verification_results | API-61 | CP-07 | WF-G | TST-08 | Covered |
| NFR-30 | Should | CMP-25 | SVC-22 | evaluation_datasets, evaluation_items, evaluation_runs | API-85, API-86 | – | – | TST-05 to TST-10 | Covered |
| IR-01 | Must | CMP-01 (doc 12 UI-01 to UI-12) | – | – | API-14, API-26, API-65 | – | all | TST-17, TST-01 | Covered |
| IR-02 | Should | CMP-01 (doc 12 UI-01 to UI-12) | – | – | API-14, API-26, API-65 | – | all | TST-17, TST-01 | Covered |
| IR-03 | Must | CMP-01 (doc 12 UI-01 to UI-12) | – | – | API-14, API-26, API-65 | – | all | TST-17, TST-01 | Covered |
| IR-04 | Must | CMP-03 | All routers | – | All | – | all | TST-02 | Covered |
| IR-05 | Should | CMP-03 | All routers | – | All | – | all | TST-02 | Covered |
| IR-06 | Should | CMP-03 | All routers | – | All | – | all | TST-02 | Covered |
| IR-07 | Should | CMP-03 | All routers | – | All | – | all | TST-02 | Covered |
| IR-08 | Must | CMP-12 | LLM gateway | llm_call_records | – | all CP | all | TST-15 | Covered |
| IR-09 | Should | CMP-01 (doc 12 UI-01 to UI-12) | – | – | API-14, API-26, API-65 | – | all | TST-17, TST-01 | Covered |
| IR-10 | Should | CMP-23 | SVC-20 | integration_actions | API-79 to API-83 | – | WF-J | TST-16 | Covered |
| IR-11 | Must | CMP-24 | Repositories | all tenant tables | All | – | all | TST-03 | Covered |
| SEC-01 | Must | CMP-02, CMP-03 | SVC-01 | users, login_attempts, sessions | API-01, API-02 | – | WF-A | TST-11 | Covered |
| SEC-02 | Should | CMP-02, CMP-03 | SVC-01 | users, login_attempts, sessions | API-01, API-02 | – | WF-A | TST-11 | Covered |
| SEC-03 | Must | CMP-02, CMP-03, CMP-24 | SVC-01 | workspace_memberships; RLS | All | – | WF-A | TST-12, TST-02 | Covered |
| SEC-04 | Must | CMP-02, CMP-03, CMP-24 | SVC-01 | workspace_memberships; RLS | All | – | WF-A | TST-12, TST-02 | Covered |
| SEC-05 | Should | CMP-02, CMP-03 | SVC-01 | users, login_attempts, sessions | API-01, API-02 | – | WF-A | TST-11 | Covered |
| SEC-06 | Must | CMP-02, CMP-03, CMP-24 | SVC-01 | workspace_memberships; RLS | All | – | WF-A | TST-12, TST-02 | Covered |
| SEC-07 | Must | CMP-12, CMP-21 | LLM gateway, SVC-19 | tool_call_records | API-76 | all CP | WF-D, WF-G, WF-I | TST-13 | Covered |
| SEC-08 | Must | CMP-12, CMP-21 | LLM gateway, SVC-19 | tool_call_records | API-76 | all CP | WF-D, WF-G, WF-I | TST-13 | Covered |
| SEC-09 | Must | CMP-12, CMP-21 | LLM gateway, SVC-19 | tool_call_records | API-76 | all CP | WF-D, WF-G, WF-I | TST-13 | Covered |
| SEC-10 | Should | CMP-01, CMP-05 | SVC-02, SVC-03 | source_files | API-14, API-18 | – | WF-B | TST-11 | Covered |
| SEC-11 | Should | CMP-01, CMP-05 | SVC-02, SVC-03 | source_files | API-14, API-18 | – | WF-B | TST-11 | Covered |
| SEC-12 | Should | CMP-01, CMP-05 | SVC-02, SVC-03 | source_files | API-14, API-18 | – | WF-B | TST-11 | Covered |
| SEC-13 | Must | CMP-20 | SVC-17 | approvals.acknowledged_claim_ids | API-66 | – | WF-G | TST-08 | Covered |
| SEC-14 | Should | CMP-25 | SVC-22 | audit_logs | API-84 | – | all | TST-21 | Covered |
| SEC-15 | Should | CMP-25 | SVC-22 | audit_logs | API-84 | – | all | TST-21 | Covered |
| SEC-16 | Could | CMP-25 | SVC-22 | audit_logs | API-84 | – | all | TST-21 | Covered |
| SEC-17 | Should | All | – | – | – | – | – | TST-11 | Covered |
| SEC-18 | Must | All | – | – | – | – | – | TST-11 | Covered |
| SEC-19 | Should | All | – | – | – | – | – | TST-11 | Covered |
| SEC-20 | Should | CMP-24 | – | all (backup) | – | – | – | TST-19 | Covered |
| SEC-21 | Could | CMP-02, CMP-03, CMP-24 | SVC-01 | workspace_memberships; RLS | All | – | WF-A | TST-12, TST-02 | Covered |

## 8. Risks

RK-01 to RK-11 come from the Audit Register (re-assessed); RK-12 onwards are new.

| RK | Risk | Likelihood | Impact | Mitigation | Experiment or test |
|---|---|---|---|---|---|
| RK-01 | Local models produce weaker PRDs than hoped | Medium | High | Evidence-first generation, verification, 8B where it helps, honest reporting | EXP-02, TC-19 |
| RK-02 | Model support check unreliable | Medium | Medium | Deterministic checks gate; support check advisory | EXP-08 |
| RK-03 | pgvector build on Windows fails or is slow | Medium | Medium | Docker image fallback (S-14) | EXP-12 |
| RK-04 | Presidio or language detector install problems | Low to medium | Medium | Presidio supports 3.11–3.14 (S-26); regex-only fallback with lower name recall | EXP-10, EXP-12 |
| RK-05 | System RAM pressure | Medium | High | Demo mode, loaded-model cap, readiness check, WSL cap if Docker used | EXP-01, TC-24 |
| RK-06 | No Jira Cloud test site | Medium | Low to medium | Preview works without Jira; creation is Should | B-03 |
| RK-07 | Labelling takes longer than planned | Medium | High | Start in Milestone 1; split across five members; guideline with examples | – |
| RK-08 | Scope exceeds hours | Medium | High | Must-first plan; Could items skippable without design change | B-02, B-05 |
| RK-09 | Ollama behaviour changes between versions | Low to medium | Medium | Pin Ollama version for the demo; re-run EXP-07 after upgrades | TC-27 |
| RK-10 | Teammates' laptops lack a capable GPU | Unknown | Medium | Develop with small models or CPU; evaluations and demos on the reference laptop | – |
| RK-11 | Transcript misread | Low | Medium | Only clear passages used; questions listed for the mentor | §9 |
| RK-12 | Batched classification loses accuracy or mixes records | Medium | Medium | Schema-enforced IDs; fallback to per-record; batch size measured | EXP-01 |
| RK-13 | Calibration data too small for reliable thresholds | Medium | Medium | Stratified validation split; report confidence intervals; conservative threshold | EXP-09 |
| RK-14 | Small-theme pass creates noisy micro-themes | Medium | Low to medium | Marked `small`; PM can merge or dismiss; minimum 3 records | EXP-06 |
| RK-15 | Rovo MCP needs admin enablement or consumes credits | Medium | Medium | Self-hosted adapter (ADR-15) | EXP-12 |
| RK-16 | Ambiguous Jira outcome causes duplicate issues | Low | Medium | Marker search before retry; unique link per story | TC-21 |
| RK-17 | Prompt injection alters labels or draft wording | Medium | Low to medium | Delimiting, no tools on text calls, human approval, injection suite | TC-14 |
| RK-18 | RLS misconfiguration (for example a superuser or owner connection) silently bypasses policies | Low | High | Non-owner roles, `FORCE ROW LEVEL SECURITY`, automated RLS tests per table (S-16) | TC-10 |
| RK-19 | PRD generation exceeds the proposed 15-minute job limit on 8B | Medium | Medium | Section-by-section calls, 4B fallback, per-section regeneration | EXP-02 |
| RK-20 | Public dataset licence does not permit use | Low | Medium | Check licence before labelling; synthetic data fallback | B-01 |
| RK-21 | Embedding dimension differs from 1,024 after a model change | Low | Medium | Dimension checked at setup; new column and re-embed job | EXP-04 |
| RK-22 | Assistant questions wait behind background model calls (one request at a time in Ollama) | Medium | Medium | Advisory-lock priority; deadline; incomplete-answer path | EXP-03 |
| RK-23 | Chosen dataset has low customer-identity coverage, so Reach and A-13 claims are weak | Medium | Medium | Coverage shown everywhere; CR-18 wording; prefer datasets with reviewer IDs | B-01 |
| RK-24 | Jira search lags behind creation, so reconciliation misses a created issue | Low | Medium | Repeated marker searches over 2 minutes; Editor decision if still unknown | TC-21 |

## 9. Questions for the mentor

B-01 to B-06 are carried over from the SRS (§14.1) and Mentor Summary; AR-01 and AR-02 from the Audit Register; AR-03 onwards are new. Each has a proposed default so work can continue.

| ID | Question | Proposed default |
|---|---|---|
| B-01 | Will datasets be provided, or should we use public or synthetic data? | Public review or support-ticket dataset with a suitable licence |
| B-02 | Is our Must/Should/Could split acceptable? | SRS §12.1 |
| B-03 | Is Jira creation through MCP mandatory for the final demo, and who provides the Jira Cloud test site? | Should priority; team creates a free test site if permitted |
| B-04 | Please confirm: no LLM orchestration framework; local-first and zero cost | Proceed as designed (ADR-06) |
| B-05 | What must Milestone 1 deliver beyond the SRS? | SRS, this design package, working ingestion of one source |
| B-06 | Is a local demo on the team laptop acceptable? | Yes |
| AR-01 | Accept local Qwen3 models through Ollama, chosen by benchmark? | Yes (ADR-08) |
| AR-02 | Accept PostgreSQL with pgvector either natively built on Windows or from the official Docker image, decided by EXP-12? | Yes |
| AR-03 | Do you accept the change requests CR-01 to CR-19 (§5), in full or individually? | Design proceeds on the proposed wording, marked as such |
| AR-04 | For Jira MCP, is the self-hosted MCP server acceptable as a fallback if Atlassian's Rovo MCP server needs admin enablement or credits we do not have? | Yes (ADR-15) |
| AR-05 | Should any live connector (for example Google Play or Zendesk) be built, and can credentials be provided? | No live connector in the MVP; adapter interface only |
| AR-06 | Is a classification cascade (trained classifier plus LLM) acceptable, or must every label come from the LLM? | Cascade, if EXP-09 shows no quality loss |
| AR-07 | Is citing a single critical report as "an individual report" acceptable (CR-03)? | Yes |
| AR-08 | What evaluation targets do you expect after the Milestone 2 baseline? | Baseline plus an improvement goal agreed then (SRS §11.3) |
| AR-09 | Is the compact UI scope in doc 12 (12 screens, one shared evidence viewer) appropriate for the internship? | Yes |
| AR-10 | Is the RICE Confidence rubric (standard levels, project-specific suggestion rubric, PM override) acceptable? | Yes (ADR-18) |

## 10. Alternatives considered and rejected (summary)

| Area | Rejected | Main reason |
|---|---|---|
| Architecture | Microservices; serverless | RAM, operational cost, not local or zero cost |
| Orchestration | LangChain, LangGraph, LlamaIndex agents | Mentor advice (to confirm), abstraction churn, hidden prompts; our flows are fixed and short |
| Agents | Multi-agent systems | More model calls on one 8 GB GPU; no task needs agent negotiation; harder to test |
| Queue | Celery + Redis, RabbitMQ, Temporal | Extra services against NFR-07; PostgreSQL job table suffices |
| Vector store | Qdrant, Chroma, FAISS files | Extra service or files outside transactions; pgvector keeps one store |
| Retrieval | Vector-only; reranker model | Misses exact terms; no rerank endpoint identified in Ollama docs consulted, extra model memory |
| Models | Paid APIs; `qwen3.5:4b`; larger local models | Cost; size with unused vision; VRAM |
| Classification | LLM per record | Estimated hours for 5,000 records |
| Clustering | k-means; BERTopic; LLM-only themes | Needs k and forces membership; dependency weight; not reproducible |
| Auth | JWT in local storage; external identity provider | Revocation and XSS exposure; unnecessary dependency |
| Realtime | WebSockets | One-way updates only |
| Frontend | Next.js; Streamlit | Extra server process; insufficient for roles, editing and drill-down |
| Jira | Direct REST; letting the LLM call Jira tools | Mentor asked for MCP; unsafe and against AGR-13 |
| PII | Regex only; cloud PII services | Low name recall; cost and data leaving the laptop |

## 11. Correction log (v1.1, 21 November 2026)

A consistency audit of v1.0 found the problems below. Each fix was applied to every affected document; no requirement ID was removed and the SRS was not changed.

| # | Problem in v1.0 | Fix | Documents |
|---|---|---|---|
| 1 | Three different preprocessing orders (WF-C, doc 06 diagram, LLD); exact-duplicate hash computed on `processed_text` before masking had run in one order | One canonical order (doc 06 §1); masking before the duplicate hash; the others refer to it | 00, 01, 02, 03, 04, 06 |
| 2 | Embedding ran in both ingestion and analysis | Embedding only in the analysis job (step 1); near duplicates moved to analysis step 2 and stored per run | 01, 02, 03, 05, 06, 07, 08 |
| 3 | Exclusion precedence differed (WF-C: duplicate, spam, noise, non-English; doc 06: noise first) | Single rule: first applicable reason in pipeline order (noise, pii_failed, non_english, duplicate, spam, spam_review), with per-reason accounting (doc 06 §3.1) | 02, 03, 06, 07 |
| 4 | `embedding_failed` (an analysis outcome) appeared as an ingestion outcome; reconciliation identity did not use DR-40's terms | Import identity in DR-40's own terms with disjoint definitions; analysis-run outcomes counted separately in `record_classifications.status` and `analysis_runs.report` | 06, 07, 09, 10, 11 |
| 5 | CP-05 and CP-10 drawn as synchronous in the orchestration diagram, asynchronous in API-54 | One model: `suggest_inputs` worker job; scoring and ranking stay synchronous | 01, 02, 03, 04, 09, 12 |
| 6 | Assistant: 4 turns × 90 s could exceed the 5-minute limit ("total ≤ 6 minutes") | Strict 5-minute deadline from request start; every call uses the remaining budget; defined expiry behaviour; priority over background model calls | 02, 03, 04, 09, 10, 11 |
| 7 | "Exactly-once processing" claimed | Replaced by restartable jobs, idempotent steps, transactional checkpoints, unique constraints, idempotency keys (`jobs.idempotency_key`, previously undocumented in the schema) and reconciliation of uncertain Jira outcomes | 03, 04, 07, 10 |
| 8 | Jira sequence showed the API creating issues in-request, while API-81 was asynchronous | Sequence now: approval → `jira_batch` job → `sending` committed before each call → `unknown` and marker search on timeout or crash | 02, 03 |
| 9 | Records without a customer ID were counted as one customer each for Reach | Known customers, unknown-identity records and identity coverage reported separately everywhere (CR-18) | 02, 03, 04, 05, 07, 08, 09, 12 |
| 10 | RICE Confidence derived from customer counts (mixing Reach into Confidence) | Standard RICE levels with a labelled project rubric based on evidence quality and assumptions, PM override, full history (ADR-18) | 02, 03, 07, 09, 11, 12 |
| 11 | A failed CP-01 spam check was treated as "not spam" | `review_required` state, excluded from statistics until resolved, counted in the import report (CR-19) | 03, 04, 06, 07, 09, 12 |
| 12 | Category values in the schema (`bug`, `usability`, `performance`) did not match the SRS taxonomy | Values now `bug_report`, `usability_issue`, `performance_issue` etc.; no intent field anywhere | 03, 04, 07, 09, 10 |
| 13 | CP-10 described as "needs no SRS change" while CR-09 proposed one | Wording aligned: FR-RMP-02 allows it; CR-09 lists it in SRS §5.9 | 04 |
| 14 | Noise rule worded differently in DA-02 and CR-02 than in SVC-05 | All use the SVC-05 rule | 11 |
| 15 | Password minimum 10 characters in SVC-01, 12 elsewhere | 12 to 128 everywhere | 03 |
| 16 | Job claim query in SVC-21 ignored `retry_wait` jobs | Claim covers `queued` and due `retry_wait` | 03 |
| 17 | Retry backoffs differed (2 s/6 s vs 10 s/40 s) without explanation | Gateway call retries vs job-step retries distinguished | 10 |
| 18 | CP-02 batch output described with compact keys (`id`, `c`, `s`, `x`) in DA-07 and doc 06, but a full schema in doc 04 | One schema: `{key, category, sentiment, sarcasm}` with keys `r1`…`r10` | 06, 11 |
| 19 | Screen-level UI design missing (5 requirements partial) | New doc 12 with 12 screens, shared components and states | 12, README, 11 §7 |
| 20 | API diagram had the worker using the API process's gateway; ingestion's CP-01 call was missing from the HLD diagram | Worker has its own gateway instance; CP-01 edge added | 01, 09 |

### 11.1 Validation after the correction pass

Automated checks run on 21 November 2026 over all 14 files. They check consistency of the documents, not the behaviour of a system, which does not exist yet.

| Check | Result |
|---|---|
| Mermaid diagrams | 24 of 24 rendered at v1.1; after the v1.2 split of the ER diagrams, 33 of 33 render (re-checked 23 November 2026); all 16 required diagrams present (guide index) |
| Identifier references | 4,428 references to SRS IDs and package IDs (CMP, SVC, CP, API, UI, TC, WF, ADR, DA, CR, EXP, RK, AR, G, S) checked; all resolve except AIR-26, FR-AUTH-13, FR-DSH-10 and FR-ING-13, which are new IDs proposed in CR-06 to CR-08 and CR-10 |
| ID ranges ("X to Y") | Every ID inside every range exists |
| Cross-document section references | 106 "doc NN §N" references resolve to existing headings; README links resolve |
| Requirements | 253 of 253 traced; none partial or unsupported; the SRS file is unchanged |
| Database relationships | New columns (`record_classifications.status`, `near_duplicate_of`; `feedback_records.spam_status`; `theme_run_stats` identity columns; `jobs.idempotency_key`; `analysis_runs.report`; nullable `score_inputs.framework` for effort) reflected in doc 08 ER diagrams and cardinality table; table count unchanged at 54 |
| Execution model | Every model call except the assistant's runs in a worker job; scoring, ranking, roadmap edits and approvals are synchronous; API modes, workflows, LLD and diagrams agree |
| Limits and timeouts | Per-call caps (doc 04 §3.1), job limits (SVC-21, CR-14) and the assistant deadline agree in docs 02, 03, 04, 09, 10 and 11 |
| Unapproved and pending items | CR-01 to CR-19 marked "proposed, not approved"; EXP-01 to EXP-12 marked "pending"; no measurement or approval is claimed |

### 11.2 Submission pass (v1.2, 23 November 2026)

No requirement, decision or design behaviour changed in v1.2. The changes concern presentation and two small inconsistencies:

| # | Change | Documents |
|---|---|---|
| 21 | Overall architecture diagram redrawn left-to-right with workspace-scoped repository nodes, so all 27 components stay legible when printed (same components and flows) | 01 |
| 22 | Diagram directions changed for print (orchestration, retrieval, preprocessing, API communication); content unchanged | 04, 05, 06, 09 |
| 23 | The five domain ER diagrams split into 14 smaller diagrams covering all 54 tables, so columns are legible; relationships unchanged | 08 |
| 24 | `import_jobs.status` mapping to the `ingest` job status documented | 07 |
| 25 | Team ownership table aligned with the pipeline split (embedding belongs to analysis) | 10 |
| 26 | Services heading added in the LLD for a correct table of contents | 03 |
| 27 | Document state diagram: the self-transition label "Editor edits (new version)" was clipped by the renderer; replaced by a note on the `draft` state with the same meaning | 02 |
