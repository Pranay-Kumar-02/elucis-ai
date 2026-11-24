# AI Product Manager Copilot · System Design Package

Infosys Springboard Virtual Internship 7.0 · Batch 5 · Project #Z-5-1 · Group 2 (Varshini, Lalitha, Monika, Pranay, Prasunabhika)
Version 1.2 · 23 November 2026 (submission pass, doc 11 §11) · **Design for mentor review. Not implemented, not tested, not mentor-approved.**

This package describes how the system in the Final SRS v1.0 will be built. It contains no production code, migrations or deployment. The canonical processing order is defined once, in doc 06 §1.

## Documents

| File | Contents | Read it when |
|---|---|---|
| [00_DESIGN_OVERVIEW.md](00_DESIGN_OVERVIEW.md) | Scope, sources, gap register (G-01 to G-18), one-page architecture, changes from v1.0 architecture, readiness | First |
| [01_HIGH_LEVEL_DESIGN.md](01_HIGH_LEVEL_DESIGN.md) | Architectural style, deployment view, external data sources and adapters, overall architecture, components CMP-01 to CMP-27 | You need the big picture |
| [02_END_TO_END_WORKFLOW.md](02_END_TO_END_WORKFLOW.md) | End-to-end flow, state machines, workflows WF-A to WF-J, run-analysis and Jira sequences | You need user and system flows |
| [03_LOW_LEVEL_DESIGN.md](03_LOW_LEVEL_DESIGN.md) | Services SVC-01 to SVC-23: purpose, inputs, outputs, algorithms, failures, tables, requirements | You implement a service |
| [04_AI_AGENT_ORCHESTRATION.md](04_AI_AGENT_ORCHESTRATION.md) | AI shape decision, call points CP-01 to CP-10, budgets, orchestration, tools, loop limits, calibration, PRD generation, context engineering | You touch any model call |
| [05_RAG_AND_EVIDENCE_DESIGN.md](05_RAG_AND_EVIDENCE_DESIGN.md) | Retrieval units, embeddings, hybrid search, evidence IDs, citation validation, insufficient evidence | You build retrieval or verification |
| [06_DATA_PIPELINE_DESIGN.md](06_DATA_PIPELINE_DESIGN.md) | **Canonical processing order**, ingestion and preprocessing stages, exclusion precedence, noise and spam, feasibility, batched inference, recovery, import and analysis-run accounting | You build the pipeline |
| [07_DATABASE_SCHEMA.md](07_DATABASE_SCHEMA.md) | Data dictionary for 54 tables, indexes, RLS, table-to-service mapping, examples, retention | You write models or queries |
| [08_DATABASE_ER_DIAGRAM.md](08_DATABASE_ER_DIAGRAM.md) | ER diagrams (whole model and by domain), cardinality, rationale | You need relationships |
| [09_API_AND_SERVICE_CONTRACTS.md](09_API_AND_SERVICE_CONTRACTS.md) | Conventions, error envelope, endpoints API-01 to API-88, schemas, roles, sync/async/SSE, internal interfaces | You build the API or frontend |
| [10_SECURITY_RELIABILITY_AND_TESTING.md](10_SECURITY_RELIABILITY_AND_TESTING.md) | Security by layer, isolation, prompt injection, PII, reliability, observability, evaluation metrics, test catalogue TC-01 to TC-27, hardware, team plan | You secure, test or plan |
| [11_ARCHITECTURE_DECISIONS_AND_OPEN_QUESTIONS.md](11_ARCHITECTURE_DECISIONS_AND_OPEN_QUESTIONS.md) | Research method, sources S-01 to S-42, ADR-01 to ADR-18, design audit DA-01 to DA-18, change register CR-01 to CR-19 (unapproved), experiments EXP-01 to EXP-12 (pending), traceability of all 253 requirements, risks RK-01 to RK-24, mentor questions, rejected alternatives, v1.1 correction log | You need the "why" |
| [12_UI_AND_INTERACTION_DESIGN.md](12_UI_AND_INTERACTION_DESIGN.md) | App shell, shared components, global states, 12 screens UI-01 to UI-12 (role, components, actions, data, APIs, states, permissions), accessibility, build scope | You build the frontend |

**Reading order.** For the mentor: 00 → 01 → 04 → 11 §3 to §5, §9 and §11. For developers: 00 → 01 → 06 §1 → 02 → the documents for your area → 07, 09 and 12 → 10.

## Diagram index

| # | Required diagram | Location |
|---|---|---|
| 1 | Overall high-level architecture | 01 §4 |
| 2 | External data source integration | 01 §3.3 |
| 3 | End-to-end workflow | 02 §1 (state machines in 02 §2) |
| 4 | Ingestion pipeline | 06 §2 |
| 5 | Preprocessing pipeline | 06 §3 |
| 6 | AI analysis engine | 03, "AI analysis engine (overview)" |
| 7 | AI agent orchestration | 04 §4 |
| 8 | RAG and evidence retrieval | 05 §9 (flowchart and sequence) |
| 9 | Prioritisation | 02 WF-F |
| 10 | PRD generation and verification | 04 §7 (flowchart) |
| 11 | Jira MCP integration | 02 WF-J |
| 12 | Database ER diagram | 08 §1 (whole model), §2 to §6 (14 domain diagrams covering all 54 tables) |
| 13 | API and service communication | 09 §7 |
| 14 | Run analysis sequence | 02 WF-D |
| 15 | PRD generation sequence | 04 §7 (sequence) |
| 16 | Assistant tool-calling sequence | 04 §5.2 |

All 33 Mermaid blocks in the package were re-rendered with Mermaid CLI on 23 November 2026 (v1.2) without errors. Rendering checks syntax only; it does not validate the design.

## ID conventions

| Prefix | Meaning | Defined in |
|---|---|---|
| FR-, DR-, AIR-, AGR-, NFR-, IR-, SEC-, AC-, TST-, A-, C-, B- | SRS identifiers, unchanged | Final SRS v1.0 |
| G- | Gap found in the sources | 00 §3 |
| CMP- | Component | 01 §5 |
| WF- | Workflow | 02 |
| SVC- | Service | 03 |
| CP- | Model call point (EMBED for embedding calls) | 04 §3 |
| API- | Endpoint | 09 §3 |
| TC- | Test case | 10 §8.4 |
| UI- | Screen | 12 §5 |
| S- | Research source | 11 §2 |
| ADR- | Architecture decision | 11 §3 |
| DA- | Design audit issue | 11 §4 |
| CR- | Proposed SRS change | 11 §5 |
| EXP- | Experiment | 11 §6 |
| RK- | Risk | 11 §8 |
| AR- | Mentor question added after the SRS | 11 §9 |
| E-codes (E1, E2 …) | Evidence IDs inside one prompt, mapped to record UUIDs | 05 §6 |

Labels: **[V]** verified in official documentation · **[3P]** third-party source · **[D]** design decision · **[E]** estimate to be measured · **[C]** calculated from stated assumptions.

## Glossary

| Term | Meaning in this package |
|---|---|
| Workspace | Tenant boundary: one product or team; every row belongs to one |
| Record | One feedback item (review, ticket, request, transcript segment) in `feedback_records` |
| Raw text / processed text | Original immutable text / cleaned and PII-masked text used everywhere downstream |
| Analysable | Record eligible for analysis (not excluded as noise, PII failure, non-English, duplicate, spam or awaiting spam review) |
| Unknown identity | A record with no customer identifier; never counted as a customer; shown with identity coverage |
| Identity coverage | Share of a group's records that have a customer identifier |
| Analysis run | One versioned execution of classification, clustering, grouping and statistics |
| Theme | Group of records describing one pain point, stable across runs |
| Aggregated request | Group of equivalent feature requests with a canonical title |
| Opportunity | A theme or request being prioritised |
| Override | A PM's correction stored as data and re-applied on every run |
| Evidence pack | Records selected for a model call, each rendered with an E-code |
| Claim | One typed statement in generated text (quantitative, qualitative, quotation, recommendation) with its evidence |
| Placeholder | `{{theme:<id>.known_customers}}`-style token that code replaces with a SQL value |
| Job | Durable background task in the `jobs` table with steps, cursor and heartbeat |
| Call point (CP) | One defined, schema-constrained model task |
| Cascade | Calibrated classifier first, batched LLM for the rest, review queue last |
| RRF | Reciprocal Rank Fusion: merges vector and keyword rankings by 1 ÷ (k + rank) |
| MMR | Maximal marginal relevance: picks relevant but non-redundant records |
| RLS | PostgreSQL row-level security |
| MCP | Model Context Protocol; used by our deterministic code to reach Jira |
| JiraPort | Internal interface with Rovo MCP and self-hosted MCP adapters |

## Status

| Area | State |
|---|---|
| Design | Complete for review: 27 components, 23 services, 10 call points, 54 tables, 88 endpoints, 12 screens, 18 ADRs |
| Requirements | 253 of 253 traced; 22 depend on proposed, unapproved changes CR-01 to CR-19 |
| Validation | Not started; EXP-01 to EXP-12 are pending (planned for Milestones 1 to 3) |
| Mentor approval | Pending; questions B-01 to B-06 and AR-01 to AR-10 |
