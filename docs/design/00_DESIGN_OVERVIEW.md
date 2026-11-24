# 00 · Design Overview

AI Product Manager Copilot · Infosys Springboard Virtual Internship 7.0 · Batch 5 · Project #Z-5-1 · Group 2
Version 1.2 · 23 November 2026 (submission pass; change log in doc 11 §11) · **Design for mentor review. Not implemented, not tested, not mentor-approved.**

## 1. Purpose and scope

This package is the system design that follows the Final SRS (v1.0). It says how the system will be built: components, workflows, service internals, AI orchestration, retrieval, data pipeline, database schema, APIs, security, testing, and the decisions behind them.

It does not contain production code, migrations or deployment. Pseudocode, schemas and example payloads appear only to remove ambiguity.

## 2. Sources and how they were used

| Source | Used for | Notes |
|---|---|---|
| Project brief (`AI_Product_Manager_Copilot_Project_Brief.md`) | Vision, ten modules, design questions, success and evaluation criteria | Primary authority on scope |
| Final SRS v1.0 | Requirements baseline; all IDs preserved | Any change is proposed in the change register (doc 11 §5), never made silently |
| Technical Architecture v1.0 | Starting proposals, re-evaluated independently | Changes recorded as decisions in doc 11 §3 |
| Mentor Summary | Questions B-01 to B-06 | Unchanged; new questions added as AR-03 onwards |
| Audit Register | Risks RK-01 to RK-11 and earlier findings | Revisited; new risks continue from RK-12 |
| Mentor transcript | Instructions on data sources, pipeline, LLM calls, agent architecture, MCP and Jira | Auto-generated text; only clear passages used |
| Independent research, 20 Nov 2026 | Integrations, libraries, runtime capabilities | Sources and access dates in doc 11 §2 |

## 3. Source analysis and gap register

Contradictions, missing information and unsupported assumptions found before designing.

| ID | Finding | Type | Where handled |
|---|---|---|---|
| G-01 | AC-ING-01 omits "failed" while DR-40 includes it; "imported" and "duplicates" overlap because duplicates are stored (DR-18) | Contradiction | CR-01; accounting identity in doc 06 §10 |
| G-02 | A-09 (fewer than 3 words is noise) would flag useful short reports such as "app crashes" | Weak assumption | CR-02; doc 06 §5 |
| G-03 | A-13 (3 distinct customers before "users report") could hide a critical single-customer incident such as data loss or a security problem | Weak assumption | CR-03; doc 03 SVC-10 |
| G-04 | A-12 treats model confidence as usable after recalibration but no calibration method is defined | Missing method | CR-04; doc 04 §6 |
| G-05 | HDBSCAN minimum cluster size of max(5, n/200) means about 25 records at 5,000, hiding smaller themes | Design weakness | ADR-09; doc 03 SVC-11 |
| G-06 | Per-record LLM classification of 5,000 records may take hours on the laptop | Feasibility | ADR-07; doc 06 §8 |
| G-07 | FR-THM-12 (preserve corrections on re-run) is Could, but losing a PM's corrections on every re-run would undermine trust | Priority gap | CR-05; doc 03 SVC-11 |
| G-08 | FR-RMP-02 allows system-suggested effort, but no LLM call point exists for it | Missing call point | CP-10 added (doc 04 §3) |
| G-09 | No product context (product name, description, users, glossary) exists for generation, yet the brief requires PRDs specific to this product | Missing data | CR-07 |
| G-10 | A-16 stops any workflow after 5 minutes; generating a multi-section PRD locally may exceed this | Feasibility | CR-14 |
| G-11 | A-15 uses one 120-second time limit for all calls; long generation calls may exceed it | Feasibility | CR-15 |
| G-12 | No requirement or tool supports creating and storing the hand-labelled evaluation set | Missing responsibility | CR-08; doc 10 §8 |
| G-13 | The master prompt lists "intent" separately; the SRS has no intent field (Audit Register N-05 merged intent into the category taxonomy) | Inconsistency between inputs | No change: category taxonomy covers intent; no intent field in the LLM schema, database, API or evaluation data (doc 04 §3, doc 07 `record_classifications`) |
| G-14 | Mentor asks where data could be fetched from (APIs); SRS keeps file import as MVP | Scope reconciliation | Adapter architecture with file import in MVP and verified connectors as extensions (doc 01 §3, CR-10) |
| G-15 | Atlassian's MCP server: API-token login needs an org admin to enable it; some tools may consume Rovo credits | New external constraint | ADR-15; fallback self-hosted MCP server; AR-04 |
| G-16 | Previous architecture used a generic persisted workflow engine for both document generation and the assistant | Unnecessary complexity | ADR-05: one job mechanism; the assistant runs in-request with hard limits |
| G-17 | Row-level security was "optional" in the previous architecture although isolation is a core requirement | Under-specified control | ADR-11: enable from Phase 1 as defence in depth |
| G-18 | No component owns emerging-issue detection (sudden spikes) | Missing responsibility | Analytics service trend checks (doc 03 SVC-13); CR-06 |

## 4. Recommended architecture in one page

- **Style.** A modular monolith (one FastAPI backend with one package per module) plus one background worker. Long work runs as durable jobs in PostgreSQL. No microservices, no message broker. See ADR-01 and ADR-05.
- **Data path (canonical order, doc 06 §1).** Ingest job: upload → validation → cleaning → noise → standardisation and customer key → PII masking → language → exact duplicates (on masked text) → spam → prepared. Analysis job: run creation → embedding → near duplicates → classification cascade → clustering → identity matching → overrides → naming → request aggregation → SQL statistics → activation. All counts and statistics come from SQL; records without a customer ID are reported as unknown identity, never as customers.
- **AI shape.** A deterministic workflow orchestrator calls specialised, schema-constrained LLM tasks (CP-01 to CP-10), all inside worker jobs. Only the conversational assistant runs a tool-calling loop in the API process; it is read-only, workspace-scoped and held to a strict 5-minute deadline. No multi-agent system. Jobs are restartable with idempotent steps; exactly-once execution is not claimed. See ADR-06.
- **Models.** Ollama on the RTX 4060. `qwen3:4b` is the default and `qwen3:8b` is a benchmark candidate for generation. `qwen3-embedding:0.6b` handles embeddings. A calibrated embedding-plus-logistic-regression classifier is a benchmark candidate for the first classification pass. See ADR-07 and ADR-08.
- **Retrieval.** One feedback record is one retrieval unit; transcripts are segmented. Hybrid retrieval combines pgvector and PostgreSQL full-text search through Reciprocal Rank Fusion, then diversity selection and a per-customer cap. Quantitative questions go to SQL tools, never retrieval. See doc 05.
- **Trust.** Typed claims, number placeholders filled by code, deterministic citation, quotation and number checks, an advisory support check, and mandatory PM approval. See doc 04 §7.
- **Database.** PostgreSQL 18 with pgvector 0.8.7: 54 tables, third normal form with documented derived tables, composite workspace foreign keys, row-level security, an insert-only audit log, and versioned AI outputs. See docs 07 and 08.
- **Jira.** Approval-gated deterministic code acts as an MCP client. The primary server is Atlassian's Rovo MCP server; the fallback is a self-hosted MCP server. The LLM never calls Jira. See ADR-15.
- **Frontend.** React, TypeScript, Vite, Tailwind CSS and shadcn/ui, served as static files by FastAPI in demo mode.

## 5. Changes from the previous Technical Architecture

| Area | Previous | Now | Why |
|---|---|---|---|
| Orchestration | Generic workflow engine (`workflow_runs`, `workflow_steps`) | One job mechanism with step cursors; document approval as a state machine; assistant runs in-request | Less code, same guarantees (ADR-05) |
| Classification | LLM per record | Cascade: calibrated classifier where confident, batched LLM for the rest; benchmark decides | Throughput and calibration (ADR-07, ADR-08) |
| Clustering | HDBSCAN `eom`, min size max(5, n/200) | `eom` and `leaf` compared; second pass on noise; small-theme surfacing; stable theme identity across runs | Small themes and override preservation (ADR-09, ADR-10) |
| Row-level security | Optional, Milestone 4 | Enabled from Phase 1 | Isolation is core; retrofitting is harder (ADR-11) |
| Jira MCP | Rovo MCP only | Rovo MCP primary; self-hosted MCP fallback behind the same interface | Admin enablement and credit uncertainty (ADR-15) |
| Data sources | File import only | File import in MVP; adapter interface plus verified connector designs | Mentor asked where data comes from (ADR-04) |

## 6. Readiness

| Area | State |
|---|---|
| Requirements coverage | 253 of 253 SRS requirements traced (doc 11 §7): 216 covered, 12 covered pending an experiment, 22 covered as proposed in an unapproved change request (CR-01 to CR-19, doc 11 §5), 3 deferred as Future; none partial or unsupported |
| Design completeness | 27 components, 10 workflows, 23 services, 10 AI call points, 54 tables, 88 endpoints, 12 screens, 18 decisions; all 16 required diagrams present |
| Verified facts | Versions, APIs and limits checked 20 Nov 2026 (doc 11 §2) |
| Not yet validated | Model quality, throughput, memory, assistant deadline behaviour, pgvector on Windows, MCP authentication: experiments EXP-01 to EXP-12 (doc 11 §6), none run yet |
