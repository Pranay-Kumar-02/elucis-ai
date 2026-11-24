# 12 · UI and Interaction Design

Screen-level design for the React app (React, TypeScript, Vite, Tailwind CSS, shadcn/ui). This document only describes screens. It contains no visual design system and no production code. It is sized for five people over eight weeks: 12 screens, one app shell, and a small set of shared components that every screen reuses.

## 1. Principles

| Principle | What it means on screen |
|---|---|
| Evidence one click away | Every number, theme, claim and score input opens the same **Evidence drawer** (IR-03, NFR-17) |
| AI output is labelled | AI-generated text carries an "AI-generated" label (AIR-19); score inputs show an origin badge: Data, AI or Person (FR-PRI-04) |
| Honest numbers | Customer figures always show known customers, unknown-identity records and identity coverage (CR-18); the UI never adds them together |
| Long work never blocks | Imports, analysis, document generation and suggestions show a progress panel fed by SSE (API-24); the user can leave and come back |
| Roles enforced twice | The server enforces roles. The UI hides actions the role cannot perform and explains why on hover, so Viewers are not shown buttons that fail |
| Same three states everywhere | Every data view has defined loading, empty and error states (NFR-19), described in §4 |

## 2. App shell and navigation (IR-02)

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ [Workspace ▾ Acme Mobile]   Analysis: run #7 · 2 h ago · ⚠ out of date   [User ▾] │
├────────────┬─────────────────────────────────────────────────────────────┤
│ Dashboard  │                                                             │
│ Imports    │                   Page content                              │
│ Themes     │                                                             │
│ Requests   │                                                             │
│ Review (4) │                                    ┌──────────────────────┐ │
│ Opportun.  │                                    │ Evidence drawer      │ │
│ Documents  │                                    │ (opens from any      │ │
│ Roadmap    │                                    │  figure or citation) │ │
│ Assistant  │                                    └──────────────────────┘ │
│ Settings   │  [Job progress panel: Importing reviews.csv · 62% · Cancel] │
└────────────┴─────────────────────────────────────────────────────────────┘
```

- The header shows the active workspace (switcher, FR-AUTH-10) and data freshness: last import, last successful analysis run, and "out of date" when newer imports exist (FR-DSH-07).
- A banner appears when the model runtime is unavailable: "AI features are paused; everything else works" (AIR-22).
- The Review badge shows open review items.

## 3. Shared components

| Component | Used by | Behaviour | API |
|---|---|---|---|
| Evidence drawer | All screens with figures or citations | Lists records behind a figure or claim, using the same filters that produced the figure; shows masked text, date, source, rating, labels, theme; Owners can toggle original text (A-22); paginated | API-26, API-27, API-65 |
| Job progress panel | Imports, analysis, documents, suggestions, Jira | Shows step, done/total, warnings and the final status; reconnects by reading API-23 after a dropped stream; Cancel for Editors | API-23, API-24, API-25 |
| Origin badge | Opportunities, roadmap | Data / AI / Person; hover shows rationale, evidence and history | API-52 |
| Verification badge | PRD editor, assistant | Pass, failed, supported, partly, unsupported, not checked; links to the reason | API-61 |
| Identity coverage chip | Themes, requests, dashboard, opportunities | "168 customers · 31 unknown identity · 85% coverage" | API-33, API-37, API-47 |
| Data table | Lists | Server-side cursor pagination, filters and sort from the API (IR-07); keyboard navigable | All list APIs |
| Confirm dialog | Deletes, approvals | Type-to-confirm for destructive actions (FR-AUTH-11, FR-ING-12) | API-09, API-19 |
| State views | All | Skeleton, empty-with-next-step, error-with-request-ID (§4) | – |

## 4. Global states

| State | Rule |
|---|---|
| Loading | Skeleton of the final layout appears immediately; long jobs use the progress panel, never a spinner over the whole page |
| Empty | Explains why it is empty and offers the next action (for example "No feedback yet → Import a file" for Editors; "Ask an Editor to import data" for Viewers) |
| Error | Shows the API message from the error envelope (doc 09 §2), what the user can do next (NFR-18), and the `request_id` for support. 401 → sign-in page with return path; 403 → "Your role (Viewer) cannot do this"; 404 → "Not found or no access"; 503 model or integration → feature-level banner, rest of the page usable |
| Partial | Incomplete assistant answers, failed PRD sections and `completed_with_errors` imports are shown with what succeeded and what did not, never hidden |

## 5. Screens

Roles: O = Owner, E = Editor, V = Viewer. "V+" means every member.

### UI-01 Sign-in and workspace management

| Aspect | Design |
|---|---|
| Role | Visitor (sign in, register); V+ (switch); O (members, settings, delete) |
| Main components | Sign-in and register forms; workspace list with "Create workspace"; Settings → General (name, description, product profile and glossary, CR-07), Members table with role selector, Danger zone (delete) |
| User actions | Register, sign in, sign out; create and switch workspace; edit product profile; add member by e-mail with role (default Viewer, SEC-21), change role, remove member; delete workspace (type the name) |
| Data displayed | User, memberships and roles; workspace profile; member list |
| APIs | API-01 to API-13 |
| States | Loading: form disabled while submitting. Empty: "Create your first workspace". Error: generic "invalid e-mail or password"; 429 shows the wait time; last Owner cannot be removed (409) |
| Permissions | Settings, members and delete: Owner only. Others see Settings read-only |

### UI-02 Data source selection and upload

| Aspect | Design |
|---|---|
| Role | E, O (upload); V (view history) |
| Main components | Source cards: "File upload" (active), connector cards marked "Extension, not enabled" (AR-05); drop zone with limits ("CSV, JSON or TXT, up to 20 MB", IR-09); "Paste text" tab (FR-ING-10); source-type selector (review, ticket, feature request, transcript, other, metrics) (FR-ING-02); import history table |
| User actions | Choose source type; drop or pick a file; paste text; continue to mapping; open a past import |
| Data displayed | Upload progress; detected format and encoding; duplicate-file warning (DR-10); history with status and counts |
| APIs | API-14, API-16, API-21 |
| States | Loading: upload progress bar. Empty history: "No imports yet". Error: 413 "File is larger than 20 MB", 415 "Only CSV, JSON or TXT", undecodable file reason |
| Permissions | Viewers see history only; upload controls hidden |

### UI-03 Column mapping and import preview

| Aspect | Design |
|---|---|
| Role | E, O |
| Main components | Preview table of the first 20 rows; one dropdown per standard field (text required; time, customer ID, rating, version, source record ID, speaker optional; metric fields for metrics files); "Use saved mapping" and "Save mapping as"; validation summary |
| User actions | Map columns; load or save a mapping (FR-ING-11); start import |
| Data displayed | Sample values under each mapping; warnings: no customer ID column → "Customer identity will be unknown; Reach and some claims will be limited" (CR-18); unparseable dates in the preview |
| APIs | API-14 (preview), API-15, API-20 |
| States | Loading: preview skeleton. Empty: file with headers only → "No data rows found". Error: missing text column blocks Start with the reason |
| Permissions | Editors and Owners only |

```text
Preview (first 20 rows)             Map to standard fields
┌───────────┬────────────┬───────┐  Text *          [ review_body ▾ ]
│review_body│ date       │ stars │  Time            [ date ▾ ]
│App crash… │ 2026-10-02 │ 1     │  Customer ID     [ — none — ▾ ]  ⚠ identity unknown
│Love the…  │ 2026-10-03 │ 5     │  Rating          [ stars ▾ ]
└───────────┴────────────┴───────┘  [Use saved mapping ▾]  [Save as…]  [Start import]
```

### UI-04 Import report and progress

| Aspect | Design |
|---|---|
| Role | V+ (view); E (retry); O (remove import) |
| Main components | Progress panel; reconciliation card using DR-40's terms (received = imported + rejected + duplicates + filtered + failed) with an "identity holds" tick (doc 06 §10.1); filtered breakdown (noise, PII failed, non-English, spam, awaiting spam review); PII masked by type; languages; row-error table with CSV download |
| User actions | Watch progress; filter errors by kind and stage; download errors (formula-safe, SEC-12); retry failed and awaiting-review records (API-88); open excluded records in the Evidence drawer; remove the import (Owner) |
| Data displayed | Snapshot at completion beside current counts (after later reviews); status `completed`, `completed_with_errors` or `failed` with reason |
| APIs | API-17, API-18, API-19, API-23, API-24, API-25, API-88 |
| States | Loading: progress panel. Empty errors: "No rejected or failed rows". Error: "Reconciliation error" shown as a failed import with the mismatching counts |
| Permissions | Retry: Editor; remove: Owner; others read-only |

### UI-05 Analysis progress and results

| Aspect | Design |
|---|---|
| Role | V+ (view); E (run) |
| Main components | "Run analysis" button with the number of records added since the last run; progress panel with the 10 analysis steps (doc 06 §1); run history; run report card: eligible = classified + near duplicates + unclassified + embedding failed (doc 06 §10.2); category and sentiment distribution |
| User actions | Start a run; watch steps; open run history; jump to Themes or Review |
| Data displayed | Current run, its configuration (models, prompt versions), counts, timings; previous run stays visible while a new one runs or if it fails |
| APIs | API-31, API-32, API-23, API-24 |
| States | Loading: progress panel. Empty: "No analysable records; import data first". Error: 409 "A run is already in progress"; 503 "Model runtime unavailable; previous results still shown" |
| Permissions | Run: Editor; others view |

### UI-06 Theme explorer with evidence drill-down

| Aspect | Design |
|---|---|
| Role | V+ (view); E (correct) |
| Main components | Theme list (name, records, identity coverage chip, share, trend sparkline, vocal flag or "not assessable", emerging and small badges); an "Unassigned" group (FR-THM-07); critical reports list (CR-03); theme detail: description, weekly chart, sentiment bar (sarcasm excluded), representative evidence, override history |
| User actions | Sort and filter (period, source, version); open evidence from any figure; rename, merge, split, move or exclude records (Editor); withdraw an override; accept a merge suggestion |
| Data displayed | Statistics from the current run; overrides marked "Edited by …" |
| APIs | API-33, API-34, API-35, API-36, API-26 |
| States | Loading: list skeleton. Empty: "No themes yet; run analysis". Error: override conflict (409) explains which theme changed |
| Permissions | Correction controls hidden for Viewers |

```text
Themes (run #7)                                    Checkout stalls at payment   ▲ emerging
┌────────────────────────────┬──────┬──────────┐   212 records · 168 customers · 31 unknown identity (85%)
│ Checkout stalls at payment │ 212  │ ▲  85%   │   Sentiment ████████░░ 78% negative (sarcasm excluded)
│ Login loop after update    │ 140  │ ▲  92%   │   Weekly ▁▂▂▃▅▇   [Evidence (212)] [Rename] [Merge] [Split]
│ Unassigned                 │  57  │  –       │   "Spins forever after I tap Pay…" E-3f2a  · 2 Oct · ★1
└────────────────────────────┴──────┴──────────┘
```

### UI-07 Review queue

| Aspect | Design |
|---|---|
| Role | V+ (view); E (resolve) |
| Main components | Tabs by kind: low-confidence labels, sarcasm, borderline request pairs, spam reviews; item card with masked text, suggested label, calibrated or "uncalibrated" confidence, reason |
| User actions | Accept, change label, mark sarcasm, decide same/different, mark spam or clean; keyboard shortcuts for fast review |
| Data displayed | Open counts per tab; resolved history |
| APIs | API-29, API-30 |
| States | Loading: card skeleton. Empty: "Nothing to review". Error: 409 when someone else resolved the item first |
| Permissions | Resolve: Editor; Viewers read-only |

### UI-08 Opportunity prioritisation

| Aspect | Design |
|---|---|
| Role | V+ (view); E (edit, suggest, decide) |
| Main components | Framework switch (RICE, ICE) and scoring settings; ranked table with score, rank change, completeness; input cells with origin badges; detail panel: Reach with identity coverage, Confidence with rubric reasons ("lowered: identity coverage 42%; Impact is an unconfirmed AI suggestion"), rationale with citations, history; "Why A above B" explanation |
| User actions | Create opportunity from a theme or request; edit any input (becomes Person); click "Suggest Impact / Effort" (starts a job, shows progress, AI values arrive labelled); accept a pending suggestion; recompute; record a decision with reason |
| Data displayed | Scores computed by code; incomplete items listed separately; moved items highlighted after recompute |
| APIs | API-49 to API-57, API-23, API-24 |
| States | Loading: table skeleton. Empty: "Create opportunities from themes or requests". Error: out-of-range input (422) shows the allowed range; suggestion job failed → "Suggestion failed; enter a value" |
| Permissions | Editing, suggesting and decisions: Editor; Viewers see values, origins and evidence |

### UI-09 PRD editor and claim verification

| Aspect | Design |
|---|---|
| Role | V+ (view, export); E (generate, edit, approve) |
| Main components | Generate dialog; progress panel; editor with sections; claims highlighted with verification badges; claim side panel (type, checks, cited evidence); user stories with Given/When/Then criteria; version history and diff; approval dialog listing failed or unsupported claims with checkboxes |
| User actions | Generate; regenerate a section; edit (saves a new version; re-verification queued); open evidence for any claim; approve an exact version after acknowledging flagged claims (SEC-13); export Markdown; send stories to Jira (UI-12) |
| Data displayed | AI-generated label; recommendations shown apart from evidence (AIR-18); "individual report" wording marked; model and prompt versions (NFR-23) |
| APIs | API-58, API-60 to API-67 |
| States | Loading: progress panel during generation. Empty: "No documents; generate one from an opportunity". Error: 409 version conflict offers reload and merge; failed sections shown with "Regenerate"; 422 approval blocked until claims acknowledged |
| Permissions | Generate, edit, approve: Editor; Viewers read and export (drafts watermarked) |

```text
Problem                                                     Claim ▸ qualitative · ✓ IDs ✓ quote · ◐ partly supported
Customers abandon checkout when payment stalls [E3][E7].    Cited: E3 "Spins forever after I tap Pay…"
{{168}} customers reported it since 3.2 [E12] ✓             [Open evidence]  [Acknowledge on approval]
──────────────────────────────────────────────────────────
User story 1  As a shopper, I want …  Given … When … Then …
[Versions ▾ v3]   [Regenerate section]   [Approve v3…]   [Export .md]
```

### UI-10 Roadmap

| Aspect | Design |
|---|---|
| Role | V+ (view, export); E (edit, approve) |
| Main components | Now / Next / Later / Unscheduled lanes as columns (FR-RMP-03); cards with title, score, effort (labelled "estimate" when AI), evidence count; capacity bar per lane; dependency lines and violation warnings |
| User actions | Propose a roadmap from the ranking; drag cards between lanes (keyboard alternative: "Move to…"); set effort; add or remove dependencies (cycles rejected with the path); change capacity; approve; export Markdown; request an Effort suggestion (async) |
| Data displayed | Capacity assumption (FR-RMP-07); manual positions marked; violations listed |
| APIs | API-68 to API-73, API-54 |
| States | Loading: lane skeleton. Empty: "Rank opportunities first". Error: 422 cycle shows the cycle path; 409 version conflict |
| Permissions | Editing: Editor; Viewers read |

### UI-11 Dashboard and conversational assistant

| Aspect | Design |
|---|---|
| Role | V+ |
| Main components | Dashboard: top pain points (records, identity coverage chip, trend), sentiment and theme trends, emerging themes, critical reports, top opportunities with one-line reasons, feedback-versus-behaviour conflicts, a Metrics tab (metric trends with release markers, release list, theme–metric links with suggested links marked "suggestion"), freshness; filters (period, source, theme, version); "Generate executive summary" and export. Assistant: chat panel with message list, citations as chips, "Tools used" disclosure, status line during work, incomplete-answer label, helpful/incorrect buttons |
| User actions | Filter; drill down from any figure; register a release and link or accept a metric link (Editor); generate an executive summary (Editor); export; ask questions; open citations; give feedback on answers |
| Data displayed | Figures from the current run; assistant answers only after verification; "Incomplete: time limit reached" when the deadline hits |
| APIs | API-42 to API-48, API-59, API-74 to API-77, API-26 |
| States | Loading: card skeletons; assistant shows "Planning…", "Looking up themes…", "Verifying…" within 2 s (NFR-04). Empty: "Import and analyse feedback to see insights". Error: 503 assistant "AI is unavailable right now"; 409 "Previous question still running" |
| Permissions | All members ask questions and view; executive summary generation: Editor |

### UI-12 Jira preview and approval

| Aspect | Design |
|---|---|
| Role | O (configure); E (preview, approve); V (view results) |
| Main components | Settings → Integrations: adapter (Rovo MCP or self-hosted), site, project, issue type, write-only credentials, "Test connection". Preview table: one row per story with the exact summary, description, type and labels; per-row approve, edit or reject; results table with keys, links, and failed or unknown rows |
| User actions | Configure and test (Owner); select approved stories; review exact payloads; approve the batch; reconcile an unknown result or link an existing key manually |
| Data displayed | Payload hash per item; approval record; created keys with links; reason for failures |
| APIs | API-78 to API-83, API-23, API-24 |
| States | Loading: connection test spinner; job progress while sending. Empty: "No approved stories" or "Jira not configured" (rest of the product unaffected, AGR-25). Error: 409 payload changed since preview (re-preview required); 503 integration unavailable |
| Permissions | Configuration: Owner; approval and sending: Editor; Viewers see results |

## 6. Accessibility (NFR-20)

- shadcn/ui components are built on Radix primitives, which provide keyboard interaction and focus management; custom components (lanes, review cards) get explicit keyboard paths ("Move to…", shortcuts).
- WCAG 2.2 AA colour contrast checked with an automated scanner in TC-23; status is never shown by colour alone (badges carry text).
- Progress and assistant status use an `aria-live="polite"` region.

## 7. Build scope

| Priority | Screens | Notes |
|---|---|---|
| Must | UI-01 to UI-06, UI-08, UI-09, UI-10, UI-11 | All ten modules reachable |
| Should | UI-07 (review queue), UI-12 (Jira) | Review is needed for calibration quality; Jira depends on B-03 |
| Shared first | App shell, Evidence drawer, Job progress panel, Data table, State views | Built in Milestone 1 so every later screen reuses them |

## 8. Traceability

| Screen | Main requirements |
|---|---|
| UI-01 | FR-AUTH-01 to FR-AUTH-11, SEC-21 |
| UI-02, UI-03 | FR-ING-01 to FR-ING-03, FR-ING-10, FR-ING-11, DR-10, IR-09 |
| UI-04 | FR-ING-04, FR-ING-05, FR-ING-07, FR-ING-08, FR-ING-12, DR-31, DR-37, DR-40, SEC-12 |
| UI-05 | FR-THM-01 to FR-THM-03, FR-DSH-07, AIR-22 |
| UI-06 | FR-THM-04 to FR-THM-07, FR-THM-09, FR-THM-11, FR-THM-12, FR-AGG-03 to FR-AGG-05 (requests use the same list and detail layout) |
| UI-07 | FR-THM-08, FR-THM-10, FR-AGG-06, DR-13, AIR-24 |
| UI-08 | FR-PRI-01 to FR-PRI-11 |
| UI-09 | FR-DOC-01 to FR-DOC-12, SEC-13, AIR-18, AIR-19, NFR-23 |
| UI-10 | FR-RMP-01 to FR-RMP-07 |
| UI-11 | FR-DSH-01 to FR-DSH-09, FR-ANA-01 to FR-ANA-06, FR-AST-01 to FR-AST-10, NFR-04 |
| UI-12 | AGR-14, AGR-17 to AGR-25 |
| All | IR-01 to IR-03, NFR-16 to NFR-20 |
