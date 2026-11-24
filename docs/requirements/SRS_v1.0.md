# AI Product Manager Copilot
# Software Requirements Specification (Final Draft for Mentor Review)

| Item | Detail |
|---|---|
| Project | AI Product Manager Copilot: AI-driven product assistant based on customer feedback, with a planning and requirements generation workspace |
| Programme | Infosys Springboard Virtual Internship |
| Team | Group 2, as assigned in the mentor session (Varshini, Lalitha, Monika, Pranay, Prasunabhika; spellings taken from an auto-generated transcript, to be confirmed) |
| Document | Final SRS, version 1.0 (supersedes draft 0.1) |
| Date | 20 November 2026 |
| Status | Ready for mentor review. **Not approved by the mentor.** |
| Companion documents | `AI_Product_Manager_Copilot_Technical_Architecture.md` (how it will be built), `AI_Product_Manager_Copilot_Mentor_Summary.md`, `AI_Product_Manager_Copilot_Audit_Register.md` |

**Reading guide.** This document states **what** the system must do and how each requirement will be verified. It does not choose technologies, models, frameworks or physical database design. Those choices are made and justified in the Technical Architecture document.

---

## 1. Introduction

### 1.1 Purpose

This SRS is Milestone 1's first deliverable, requested by the mentor (SRC-2). It defines the scope, users, functional and non-functional requirements, data and AI behaviour, acceptance criteria and verification approach for the AI Product Manager Copilot. Once the mentor reviews it, it becomes the baseline for system design, implementation and testing.

### 1.2 Scope

The system is a web application in which a Product Manager (PM) works inside a private workspace to:

1. Import customer feedback, support tickets, feature requests, meeting transcripts and product analytics.
2. Clean, filter, standardise and categorise that data into a structured form suitable for analysis.
3. See themes and pain points, each backed by the actual feedback behind it.
4. See differently worded feature requests grouped and counted.
5. Rank opportunities with a scoring framework the PM chooses, with visible reasoning.
6. Generate PRDs, user stories and acceptance criteria whose claims are traceable to evidence.
7. View a proposed roadmap and an executive summary.
8. Ask questions in plain language and receive grounded, cited answers.
9. Optionally create approved user stories in Jira through the Model Context Protocol (MCP).

Section 12 lists out-of-scope items.

### 1.3 Objectives and success criteria

The objectives and success criteria below are taken from the brief (SRC-1, sections 1, 4 and 7) and are preserved unchanged in meaning.

| ID | Objective or success criterion | Source |
|---|---|---|
| OBJ-01 | Read large volumes of feedback and surface what matters, so representative problems are not drowned out by loud customers | SRC-1 §1 |
| OBJ-02 | Make prioritisation explainable, using a framework the PM chooses | SRC-1 §4 |
| OBJ-03 | Draft product documents that are specific to the product and traceable to the evidence | SRC-1 §4 |
| OBJ-04 | Keep the PM in charge of decisions; the system is a copilot | SRC-1 §1 |
| OBJ-05 | Make AI output trustworthy: verifiable against source data, never inventing evidence | SRC-1 §1, §6 |
| SC-01 | A PM can load a body of customer feedback and product data into a workspace | SRC-1 §7 |
| SC-02 | A PM can see the main pain points and trends, with the evidence behind each | SRC-1 §7 |
| SC-03 | A PM can review a ranked set of feature opportunities and understand why they are ranked that way | SRC-1 §7 |
| SC-04 | A PM can generate a PRD, user stories and acceptance criteria for a chosen feature | SRC-1 §7 |
| SC-05 | A PM can view a proposed roadmap and an executive summary | SRC-1 §7 |
| SC-06 | A PM can ask follow-up questions in plain language and get grounded answers | SRC-1 §7 |

### 1.4 Problem statement

PMs receive a constant flood of reviews, tickets, feature requests, analytics, sales calls and meeting transcripts. The volume outgrows what any person can read. As a result, loud customers are heard over representative ones, recurring problems stay hidden in thousands of tickets, and prioritisation becomes opinion. PMs also spend a large share of their time turning decisions into PRDs, user stories, acceptance criteria, roadmaps and executive summaries. The project asks whether generative AI can read everything, surface what matters and draft the documents while the PM keeps the decisions. Whether a PM can trust what the system says is the central challenge (SRC-1 §1).

### 1.5 Intended audience

| Audience | Use of this document |
|---|---|
| Mentor (Infosys) | Review, challenge and approve the requirements |
| Project team | Basis for design, implementation, testing and the demo |
| Evaluators | Check completeness against the brief |

### 1.6 Definitions

| Term | Meaning |
|---|---|
| PM | Product Manager, the primary user |
| Workspace | A private container for one product, team or project; every data record belongs to exactly one workspace |
| Record | One unit of customer text: a review, ticket, feature request or transcript segment |
| Evidence item | A stored record or metric value that supports a statement made by the system |
| Evidence ID | A stable identifier of an evidence item, used for citations |
| Theme | A group of records describing the same problem or topic, with a name, description and statistics |
| Aggregated request | A group of differently worded feature requests expressing the same ask |
| Opportunity | A candidate item to build or fix, derived from a theme or aggregated request |
| Scoring framework | A documented method of scoring opportunities, for example RICE (Reach, Impact, Confidence, Effort) or ICE (Impact, Confidence, Ease) |
| PRD | Product Requirements Document |
| Claim | A single factual statement in AI-generated text that can be checked against evidence |
| Language model | The AI model that produces text and structured output (provider and model chosen in the architecture) |
| Semantic similarity | A measure of how close two texts are in meaning, independent of exact wording |
| Retrieval | Finding workspace records relevant to a question or task |
| Tool | A defined system function the assistant may ask the system to run, with validated arguments |
| MCP | Model Context Protocol, a standard way for an application to call tools exposed by an external server |
| PII | Personally identifiable information |
| Prompt injection | Text inside customer data that tries to make the AI follow instructions instead of treating it as data |
| Human approval | A step where an authorised person must explicitly approve before a result is final or an external action happens |
| Ground truth | A hand-labelled dataset used to measure accuracy |
| Reference laptop | The team's development and demo laptop described in OE-03 |

### 1.7 Source documents

| ID | Source | What it contributes |
|---|---|---|
| SRC-1 | Infosys project brief, "AI Product Manager Copilot: Project Brief for Student Teams" | Product purpose, the ten modules, quality expectations, seven design questions, success and evaluation criteria, milestones |
| SRC-2 | Mentor meeting transcript (auto-generated; some passages are garbled and are not used) | SRS as first deliverable in Markdown; requirement analysis before design; entry point and flow; LLM calls and post-call handling; database schema; data pipeline (import, cleaning, noise filtering, preprocessing, normalisation, categorisation); AI agent architecture; MCP with Jira for user stories; group working; Milestone 1 ends on Friday |
| SRC-3 | Team constraints stated by the team lead in planning discussions | Local-first execution on the reference laptop; no mandatory paid AI services or API keys; preference for no LLM orchestration framework, which the team reports was advised by the mentor verbally. This advice does not appear in SRC-2, so it is listed for confirmation (B-04) |

### 1.8 Conventions

**Requirement language.** Each requirement contains exactly one "shall" and is verifiable by test, demonstration, inspection or analysis.

**Identifier scheme.**

| Prefix | Meaning | Section |
|---|---|---|
| OBJ-, SC- | Objectives and success criteria | 1.3 |
| OE- | Operating environment | 2.5 |
| C- | Constraints | 2.6 |
| A- | Assumptions and proposed default values | 2.6 |
| FR-AUTH-, FR-ING-, FR-ANA-, FR-THM-, FR-AGG-, FR-PRI-, FR-DOC-, FR-RMP-, FR-AST-, FR-DSH- | Functional requirements, one code per module | 3 |
| AC-AUTH-, AC-ING-, ... AC-DSH- | Acceptance criteria per module | 3 |
| DR- | Data and pipeline requirements | 4 |
| AIR- | AI behaviour requirements | 5 |
| CP- | LLM call points | 5.9 |
| AGR- | Agent and external integration requirements | 6 |
| NFR- | Non-functional requirements | 7 |
| IR- | External interface requirements | 8 |
| SEC- | Security, privacy and guardrail requirements | 9 |
| UC- | Use cases | 10 |
| TST- | Verification activities | 11 |
| B- | Blocking mentor decisions | 14.1 |
| T- | Team design decisions (resolved in the architecture) | 14.2 |

**Source tags.** B = brief (SRC-1). M = mentor transcript (SRC-2). T = team constraint (SRC-3). P = team proposal awaiting mentor review. Combined tags such as B/P mean the need comes from the brief and the specific form is a team proposal.

**Priority.** Every requirement carries one priority:

| Priority | Meaning |
|---|---|
| Must | Part of the minimum end-to-end product that satisfies SC-01 to SC-06. Built first. |
| Should | Adds the depth that evaluation rewards (accuracy, explanation, robustness). Built after the Must items of the same module. |
| Could | Valuable if time remains. |
| Future | Recorded so it is not lost; not planned for the internship. |

Every one of the ten modules has Must requirements, so all ten appear in the final product, at different depths, as the brief advises (SRC-1 §8). Priorities are team proposals for mentor approval (B-02).

---

## 2. Overall Description

### 2.1 Product perspective

The product is a standalone, local-first web application. Logically it consists of:

| Logical part | Responsibility |
|---|---|
| Web client | All user interaction |
| Application services | Authentication, workspace scoping, business rules, APIs |
| Ingestion pipeline | Import, validation, cleaning, standardisation, PII masking, enrichment |
| Analysis services | Classification, themes, request aggregation, statistics, scoring, roadmap sequencing |
| Generation and verification services | PRDs, stories, summaries, assistant answers, and checks against evidence |
| Language model runtime | Produces text and structured output; replaceable |
| Data store | Raw, processed and derived data, documents, audit log |
| Integration component | The only part that talks to external systems such as Jira (through MCP) |

The entry point is the web client's sign-in page. All later processing happens server-side, inside the active workspace.

### 2.2 The product management workflow

The brief's PM exercise (SRC-1 §3) defines the workflow. Tedious steps are automated; judgement steps stay with the PM.

| Step | PM activity | What the system does | Who decides |
|---|---|---|---|
| 1. Collect | Gather reviews, tickets, requests, transcripts, metrics | Imports, validates, reports what was imported | PM chooses sources |
| 2. Clean | Discard junk, merge duplicates | Filters noise and spam, detects duplicates, masks PII | PM can restore flagged records |
| 3. Understand | Read and group feedback into themes | Classifies, groups into themes, counts customers, shows evidence | PM renames, merges, corrects |
| 4. Compare | Check opinions against behaviour | Shows metrics beside themes, flags conflicts | PM interprets conflicts |
| 5. Decide | Rank what to fix | Computes scores with a chosen framework, explains them | PM sets inputs and makes decisions |
| 6. Document | Write PRD, stories, acceptance criteria | Drafts cited documents, verifies claims | PM edits and approves |
| 7. Plan | Sequence work | Proposes a roadmap from priority, effort, dependencies | PM reorders and approves |
| 8. Communicate | Brief leadership; hand stories to engineering | Generates an executive summary; creates approved stories in Jira | PM approves each external action |
| 9. Ask | Follow-up questions at any time | Answers from workspace data with citations, or says it cannot | PM judges the answer |

### 2.3 Users and stakeholders

| Stakeholder | Interest |
|---|---|
| Product Manager (primary user) | Faster, evidence-based understanding, prioritisation and documentation |
| Product team members | Read evidence, PRDs, stories, roadmaps |
| Leadership | Read executive summaries and roadmaps |
| Workspace Owner | Administer the workspace, members and integrations |
| Mentor and evaluators | Judge accuracy, quality, usability and completeness |

### 2.4 Roles and permissions

Roles are a team proposal (A-20).

| Capability | Owner | Editor | Viewer |
|---|---|---|---|
| View dashboards, themes, evidence, documents, roadmap | Yes | Yes | Yes |
| Ask the assistant | Yes | Yes | Yes |
| Import data; run analysis | Yes | Yes | No |
| Edit themes, groups, scoring inputs, roadmap | Yes | Yes | No |
| Generate, edit and approve documents | Yes | Yes | No |
| Approve creation of Jira items | Yes | Yes | No |
| Configure integrations; manage members; view audit log; view raw text containing PII | Yes | No | No |
| Delete workspace | Yes | No | No |

### 2.5 Operating environment

| ID | Item | Requirement or known fact | Status |
|---|---|---|---|
| OE-01 | Client | Desktop web browser; latest two stable versions of Chrome, Edge and Firefox (A-19) | Team proposal |
| OE-02 | Deployment for development and demo | Runs locally on one laptop; the browser connects to the application on the same machine | Team proposal; confirm (B-06) |
| OE-03 | Reference hardware | Intel Core i7-13700HX (16 cores, 24 threads); 16 GB DDR5 of which Windows reports 13.7 GB usable; NVIDIA GeForce RTX 4060 Laptop GPU with 8 GB dedicated memory; Intel UHD integrated graphics; NVMe SSD. A snapshot showed 9.8 GB of RAM in use with everyday applications open | Measured by the team (Task Manager, 20 Nov 2026) |
| OE-04 | Operating system | Windows 11 on the reference laptop. Teammates may use other operating systems; the system must not depend on one person's machine for development | Known (reference laptop); team proposal |
| OE-05 | Network | Required only for installing software and for the optional Jira integration. Core functions, including AI functions, must work offline once installed | Team constraint (T) |
| OE-06 | Paid services | None mandatory (C-05) | Team constraint (T) |
| OE-07 | Data | Public or synthetic datasets (A-01) | Assumption; confirm (B-01) |

### 2.6 Constraints, assumptions and dependencies

**Constraints**

| ID | Constraint | Source |
|---|---|---|
| C-01 | Eight weeks in four milestones, roughly 10 hours of planned effort per milestone | B |
| C-02 | Group project; teams of about five | M |
| C-03 | Technology, model and architecture choices are owned and justified by the team | B |
| C-04 | The PM remains in charge; AI output is advisory | B |
| C-05 | No mandatory paid AI service, subscription or API key | T |
| C-06 | The complete system must run, be tested and be demonstrated on the reference laptop (OE-03) | T |
| C-07 | No LLM orchestration framework (for example LangChain or LangGraph) unless the mentor decides otherwise | T, relayed; confirm B-04 |
| C-08 | Deliverables in Markdown | M |
| C-09 | Milestone 1 covers requirements, system design, data schema, data pipeline and AI agent architecture, and ends on the Friday stated by the mentor | M |

**Assumptions and proposed default values.** These replace most of the open items of draft 0.1. Each is a team proposal that can be changed by configuration or by the mentor.

| ID | Assumption or default | Rationale |
|---|---|---|
| A-01 | Datasets are public or synthetic; no real company data | Brief suggests public review datasets (SRC-1 §3) |
| A-02 | Desktop browser use only; no mobile application | Typical PM working context; reduces scope |
| A-03 | All languages are detected; English records are analysed; non-English records are flagged and excluded from theme analysis by default | Keeps accuracy measurable within scope; brief requires multilingual text to be handled, not fully analysed |
| A-04 | Analytics data arrives as CSV files, not live connections | No analytics accounts available |
| A-05 | Reference workspace: 5,000 feedback records; maximum 20,000 records per import | Large enough to need a copilot, small enough to process on the reference laptop |
| A-06 | Maximum upload size 20 MB per file | Comfortably holds A-05 volumes as CSV |
| A-07 | Sessions end after 30 minutes of inactivity | Common web-application default |
| A-08 | After 5 failed sign-in attempts within 15 minutes, further attempts for that account are blocked for 15 minutes | Limits password guessing without permanent lockout |
| A-09 | A record with fewer than 3 words after cleaning is flagged as noise | Such records rarely carry an actionable problem; tune with data |
| A-10 | The near-duplicate threshold is configurable; its starting value is set in the architecture and tuned on the labelled set | Depends on the similarity method chosen in design |
| A-11 | A theme with at least 10 records is flagged as "vocal-customer dominated" when one customer contributes more than 20% of its records | Directly answers design question 1 (SRC-1 §6); tune with data |
| A-12 | Results with confidence below 0.6 on the system's confidence scale go to review; the threshold is recalibrated after the first evaluation | Model-reported confidence is not calibrated, so the value must be checked against labelled data |
| A-13 | A claim that users want or report something needs evidence from at least 3 distinct customers | Prevents single-customer anecdotes becoming "user needs" |
| A-14 | At most 2 records per customer in any evidence set given to the language model | Prevents one customer dominating generation |
| A-15 | Each language model call has a 120-second time limit; invalid structured output is retried at most 2 times | Local inference on a laptop GPU is slower than cloud services |
| A-16 | The assistant uses at most 6 tool calls per question; any AI workflow run stops after 5 minutes | Bounded, predictable behaviour |
| A-17 | Scoring frameworks: RICE (Must), ICE (Should) | Widely used and documented frameworks with clear formulas |
| A-18 | Export format: Markdown | Matches the mentor's preferred format |
| A-19 | Supported browsers as OE-01 | Covers the team's and evaluators' likely browsers |
| A-20 | Roles: Owner, Editor, Viewer | Smallest set that separates administration, editing and reading |
| A-21 | Audit entries are kept for the lifetime of the workspace | No retention rule was given |
| A-22 | Raw text that contains PII is visible only to the Owner | Least privilege |
| A-23 | Times are stored in UTC and displayed in the browser's local time | Avoids time-zone errors in trends |
| A-24 | Rating scales are standardised to 1 to 5 | Common scale across review sources |
| A-25 | For the Jira integration, a Jira Cloud test site is provided by the team or mentor | Needed for testing; confirm (B-03) |

**Dependencies**

| ID | Dependency |
|---|---|
| D-01 | A language model and an embedding capability that run locally on the reference laptop (selected in the architecture) |
| D-02 | A hand-labelled evaluation set created by the team (SRC-1 §9) |
| D-03 | Mentor decisions B-01 to B-06 |
| D-04 | A Jira test site and MCP server access, for the Jira integration only |

---

## 3. Functional Requirements

Each module below follows the same structure. Data handling shared by several modules is specified once in Section 4; AI behaviour in Section 5; agent and Jira behaviour in Section 6; security in Section 9.

### 3.1 Module 1: User Authentication and Workspace Management

- **Purpose.** People sign in and work inside a workspace (a product, team or project) that keeps its data separate from others (SRC-1 §2).
- **Actors and preconditions.** Visitor, Owner, Editor, Viewer. All other modules require an authenticated user with an active workspace.
- **Inputs.** Email and password; workspace name; member and role assignments.
- **Workflow.** Register, sign in, create or select a workspace, optionally add members. Every subsequent request is checked against membership and role.
- **Outputs.** Authenticated session; workspace with members; audit entries (SEC-14).

| ID | Requirement | Priority | Src |
|---|---|---|---|
| FR-AUTH-01 | The system shall allow a visitor to register with a unique email address and a password. | Must | P |
| FR-AUTH-02 | The system shall refuse every function except registration and sign-in to unauthenticated requests. | Must | B/P |
| FR-AUTH-03 | The system shall invalidate the session immediately when the user signs out. | Must | P |
| FR-AUTH-04 | The system shall end a session after the inactivity period in A-07. | Should | P |
| FR-AUTH-05 | The system shall allow an authenticated user to create a workspace with a name and an optional description. | Must | B |
| FR-AUTH-06 | The system shall associate every stored record, result, document and audit entry with exactly one workspace. | Must | B |
| FR-AUTH-07 | The system shall refuse any request for a resource of a workspace in which the requesting user is not a member. | Must | B |
| FR-AUTH-08 | The system shall allow an Owner to add an existing registered user to the workspace with the role Owner, Editor or Viewer. | Should | P |
| FR-AUTH-09 | The system shall enforce the role permissions of Section 2.4 on every server-side operation. | Should | P |
| FR-AUTH-10 | The system shall allow a member of several workspaces to switch the active workspace. | Should | P |
| FR-AUTH-11 | The system shall allow an Owner to delete a workspace and all its data after an explicit confirmation step. | Could | P |
| FR-AUTH-12 | The system shall allow a user to reset a forgotten password through a verified channel. | Future | P |

**Errors.** Wrong credentials give a generic message that does not reveal whether the email exists. A duplicate email at registration is refused. A request for another workspace's resource is refused without revealing any of its data. An expired session returns the user to sign-in. An insufficient role is refused with the required role named.

| ID | Acceptance criterion | Verifies |
|---|---|---|
| AC-AUTH-01 | Given workspaces A and B with data, when a member of A requests any resource of B through the interface or directly through the API, then the request is refused and zero records of B are returned. | FR-AUTH-06, FR-AUTH-07 |
| AC-AUTH-02 | Given no session, when any protected endpoint is called, then 100% of tested endpoints refuse access. | FR-AUTH-02 |
| AC-AUTH-03 | Given a signed-out session token, when it is reused, then the request is refused. | FR-AUTH-03 |
| AC-AUTH-04 | Given a Viewer, when the Viewer attempts to import, edit a score or approve a document, then each attempt is refused and logged. | FR-AUTH-09 |

### 3.2 Module 2: Customer Feedback and Support Ticket Ingestion

- **Purpose.** Get messy, real-world text (reviews, tickets, feature requests, transcripts) into the system (SRC-1 §2; SRC-2 "mechanism for importing").
- **Actors and preconditions.** Owner, Editor. Active workspace.
- **Inputs.** Files or pasted text with a source type; column mapping for tabular files.
- **Workflow.** Choose source type, upload, validate, map columns, process asynchronously through the pipeline (Section 4), review the import report.
- **Outputs.** Stored records with evidence IDs; import report; failure list.

| ID | Requirement | Priority | Src |
|---|---|---|---|
| FR-ING-01 | The system shall accept feedback files in the formats defined in DR-05. | Must | B/P |
| FR-ING-02 | The system shall require each import to be labelled with one source type: customer review, support ticket, feature request, meeting transcript or other. | Must | B |
| FR-ING-03 | The system shall let the user map the columns of a tabular file to the standard fields: text, timestamp, customer identifier, rating, product version and source record identifier. | Must | P |
| FR-ING-04 | The system shall process each import in the background and show its status as queued, processing, completed, completed with errors or failed. | Must | P |
| FR-ING-05 | The system shall show an import report containing the counts defined in DR-31. | Must | B/P |
| FR-ING-06 | The system shall assign every imported record a stable evidence ID. | Must | B/P |
| FR-ING-07 | The system shall allow a failed or partly failed import to be retried without storing any record twice. | Should | P |
| FR-ING-08 | The system shall show the import history of the workspace. | Should | P |
| FR-ING-09 | The system shall show any record's original text beside its processed text. | Should | P |
| FR-ING-10 | The system shall allow feedback to be added by pasting text. | Could | P |
| FR-ING-11 | The system shall allow a saved column mapping to be reused for later files. | Could | P |
| FR-ING-12 | The system shall allow an import to be removed after listing the derived results it affects. | Could | P |

**Errors.** Covered in DR-06 to DR-10 and DR-36 to DR-40: invalid files are rejected with reasons; invalid rows are rejected individually while valid rows continue; failures are listed and retryable.

| ID | Acceptance criterion | Verifies |
|---|---|---|
| AC-ING-01 | Given a valid CSV of N rows, when imported, then received = imported + rejected + duplicates + filtered = N, and every stored record has a unique evidence ID. | FR-ING-01, FR-ING-05, FR-ING-06 |
| AC-ING-02 | Given an import interrupted part-way, when retried, then no record is stored twice. | FR-ING-07 |
| AC-ING-03 | Given a stored record, when viewed, then its original text is shown exactly as supplied. | FR-ING-09 |
| AC-ING-04 | Given a CSV with non-standard column names, when the user maps them, then the records are stored with the correct standard fields. | FR-ING-03 |

### 3.3 Module 3: Product Analytics Data Integration

- **Purpose.** Bring in numbers (usage, funnels, retention, ticket volume) so opinions can be checked against behaviour (SRC-1 §2).
- **Actors and preconditions.** Owner, Editor. Active workspace; analysed feedback for comparisons.
- **Inputs.** Metric CSV files; release versions and dates; links between metrics and themes.
- **Workflow.** Upload metrics, register releases, view trends, link metrics to themes, review conflicts.
- **Outputs.** Metric series, release markers, conflict list.

| ID | Requirement | Priority | Src |
|---|---|---|---|
| FR-ANA-01 | The system shall import product metric data in the structure defined in DR-41. | Must | B |
| FR-ANA-02 | The system shall allow the user to register product releases with a version label and a date. | Must | P |
| FR-ANA-03 | The system shall display each metric as a trend over time with release markers. | Should | B/P |
| FR-ANA-04 | The system shall allow the user to link a metric to a theme or aggregated request. | Should | P |
| FR-ANA-05 | The system shall flag a conflict when a linked theme or request and its metric point in opposite directions, displaying both signals side by side without choosing one. | Should | B |
| FR-ANA-06 | The system shall label any metric link it suggests as a suggestion until the user accepts it. | Could | P |

**Errors.** Missing columns or invalid values are rejected with reasons (DR-41). Overlapping series require the user to choose replace, keep or cancel. Without analytics data, conflict views state that no behaviour data exists.

| ID | Acceptance criterion | Verifies |
|---|---|---|
| AC-ANA-01 | Given a metrics file with valid and invalid rows, when imported, then valid rows are stored and invalid rows are listed with reasons. | FR-ANA-01 |
| AC-ANA-02 | Given registered releases, when a trend is displayed, then markers appear at the registered dates. | FR-ANA-02, FR-ANA-03 |
| AC-ANA-03 | Given a theme with rising requests linked to a metric showing falling or negligible usage, when compared, then a conflict is shown with both values. | FR-ANA-04, FR-ANA-05 |

### 3.4 Module 4: Feedback Classification and Theme Extraction

- **Purpose.** Turn thousands of comments into a manageable set of themes and pain points; a theme is more than a label (SRC-1 §2, §4).
- **Actors and preconditions.** Editor (correct), all roles (view). Records imported and prepared.
- **Inputs.** Prepared records; PM corrections.
- **Workflow.** Classify each record, group records into themes, name themes, compute statistics, flag low-confidence and vocal-customer cases, let the PM correct.
- **Outputs.** Classified records; themes with member lists and statistics; review queue.

| ID | Requirement | Priority | Src |
|---|---|---|---|
| FR-THM-01 | The system shall assign each analysed record one category from the taxonomy: bug report, feature request, usability issue, performance issue, praise, question, other. | Must | B/P |
| FR-THM-02 | The system shall assign each analysed record one sentiment: positive, neutral, negative or mixed. | Must | P |
| FR-THM-03 | The system shall group analysed records into themes, each with a name and a one-sentence description of the pain point. | Must | B |
| FR-THM-04 | The system shall let the user open any theme and see all of its member records with their text. | Must | B |
| FR-THM-05 | The system shall show for each theme its record count, unique-customer count, share of analysed records, sentiment distribution and weekly trend. | Must | B/P |
| FR-THM-06 | The system shall flag themes that meet the vocal-customer rule in A-11. | Must | B |
| FR-THM-07 | The system shall show records that belong to no theme in a visible "unassigned" group. | Should | P |
| FR-THM-08 | The system shall send results below the confidence threshold in A-12 to a review list. | Should | P |
| FR-THM-09 | The system shall allow an Editor to rename themes and to merge two themes. | Should | P |
| FR-THM-10 | The system shall flag records that may be sarcastic and exclude their sentiment from theme statistics until reviewed. | Should | B |
| FR-THM-11 | The system shall allow an Editor to split a theme and to move records between themes. | Could | P |
| FR-THM-12 | The system shall preserve Editor corrections when analysis is re-run on new data. | Could | P |

**Errors.** Records that are empty or noise after cleaning are excluded and counted. If classification fails for a record, the record stays unclassified, the user is told, and processing can resume without re-importing. If fewer than 50 analysed records exist, the system states that the sample is too small for reliable themes (team proposal).

| ID | Acceptance criterion | Verifies |
|---|---|---|
| AC-THM-01 | Given a theme, when opened, then the number of listed records equals the displayed record count. | FR-THM-04, FR-THM-05 |
| AC-THM-02 | Given a theme of at least 10 records where one customer wrote more than 20%, when analysis completes, then the theme is flagged. | FR-THM-06 |
| AC-THM-03 | Given the labelled evaluation set, when classification and theme extraction run, then the metrics of TST-05 are computed and reported. | FR-THM-01, FR-THM-03 |
| AC-THM-04 | Given a seeded sarcastic record, then it is flagged or sent to review rather than counted as positive. | FR-THM-10 |

### 3.5 Module 5: Feature Request Aggregation

- **Purpose.** Recognise that 40 differently worded requests are the same ask, and count them (SRC-1 §2).
- **Actors and preconditions.** Editor (correct), all roles (view). Records classified.
- **Inputs.** Records categorised as feature requests; Editor corrections.
- **Workflow.** Extract a short canonical ask from each request, group equivalent asks, count requests and customers, let the Editor correct.
- **Outputs.** Aggregated requests with counts and members.

| ID | Requirement | Priority | Src |
|---|---|---|---|
| FR-AGG-01 | The system shall identify feature requests in records of every source type. | Must | B |
| FR-AGG-02 | The system shall express each feature request as a short canonical ask while keeping the original text. | Should | P |
| FR-AGG-03 | The system shall group equivalent feature requests into one aggregated request with a title. | Must | B |
| FR-AGG-04 | The system shall show each aggregated request's request count and unique-customer count. | Must | B/P |
| FR-AGG-05 | The system shall allow an Editor to open an aggregated request and merge, split or remove members. | Should | P |
| FR-AGG-06 | The system shall flag low-confidence groupings for review. | Could | P |
| FR-AGG-07 | The system shall show each aggregated request's volume over time. | Could | P |

**Errors.** Ambiguous requests stay ungrouped and flagged. A record containing several asks is flagged for splitting. If grouping fails, previous groups are kept and the user is told.

| ID | Acceptance criterion | Verifies |
|---|---|---|
| AC-AGG-01 | Given labelled sets of paraphrased requests, when aggregation runs, then pairwise grouping precision and recall are computed (TST-06). | FR-AGG-03 |
| AC-AGG-02 | Given one customer who submitted the same request ten times, then the request count is 10 and the unique-customer count is 1. | FR-AGG-04 |

### 3.6 Module 6: AI-Based Prioritization and Impact Analysis

- **Purpose.** Rank opportunities using configurable scoring frameworks, estimate business impact, and show reasoning a PM can inspect (SRC-1 §2, §4).
- **Actors and preconditions.** Editor (change), all roles (view). Themes or aggregated requests exist.
- **Inputs.** Themes, requests, metrics, framework choice, input values and weights.
- **Workflow.** Create opportunities, choose a framework, fill inputs (from data, AI suggestion or PM entry), compute scores, explain, let the PM change inputs and recompute.
- **Outputs.** Ranked opportunities with score breakdowns, explanations and impact estimates.

| ID | Requirement | Priority | Src |
|---|---|---|---|
| FR-PRI-01 | The system shall maintain a list of opportunities derived from themes and aggregated requests. | Must | B |
| FR-PRI-02 | The system shall score opportunities with the RICE framework. | Must | B/P |
| FR-PRI-03 | The system shall compute every score with a documented formula that the user can view, so that identical inputs always give identical scores. | Must | P |
| FR-PRI-04 | The system shall show, for every score input, its value and its origin: computed from data, suggested by AI, or entered by a person. | Must | B |
| FR-PRI-05 | The system shall recompute the ranking when an Editor changes any input or weight, and show which items moved. | Must | B |
| FR-PRI-06 | The system shall score opportunities with the ICE framework as an alternative selectable by the user. | Should | B/P |
| FR-PRI-07 | The system shall show, for any AI-suggested input, a rationale that cites evidence and a label marking the value as an estimate. | Should | B |
| FR-PRI-08 | The system shall explain why one opportunity ranks above another by showing the input differences that decide the order. | Should | B |
| FR-PRI-09 | The system shall show an impact estimate for each opportunity together with the assumptions it rests on. | Should | B |
| FR-PRI-10 | The system shall show a confidence indicator per opportunity that is lowered by a feedback-versus-behaviour conflict. | Could | P |
| FR-PRI-11 | The system shall allow an Editor to record a decision (accepted, deferred or rejected) with a reason. | Could | P |

**Errors.** Opportunities with missing inputs are shown as incomplete and excluded from the ranking until completed. Invalid input values are refused with the allowed range. If an AI suggestion fails, the Editor can enter the value manually. Ties are ordered by a documented rule.

| ID | Acceptance criterion | Verifies |
|---|---|---|
| AC-PRI-01 | Given fixed inputs, when scores are computed twice, then the results are identical. | FR-PRI-03 |
| AC-PRI-02 | Given a change to one input, when saved, then the ranking updates and the moved items are indicated. | FR-PRI-05 |
| AC-PRI-03 | Given any score, when opened, then each input shows value and origin. | FR-PRI-04 |
| AC-PRI-04 | Given the team's manual ranking of an evaluation set, when compared with the system ranking, then rank correlation is reported (TST-07). | FR-PRI-01, FR-PRI-02 |

### 3.7 Module 7: PRD and User Story Generation

- **Purpose.** Draft requirement documents, user stories and acceptance criteria grounded in the evidence; a reviewer must be able to tell which customer problem a PRD came from (SRC-1 §2, §4). Approved stories may be created in Jira through MCP (SRC-2).
- **Actors and preconditions.** Editor. An opportunity with supporting evidence exists.
- **Inputs.** Selected opportunity, its evidence and statistics, PRD template, Editor edits.
- **Workflow.** Select an opportunity, assemble evidence, draft PRD and stories, verify claims, review and edit, approve, optionally send stories to Jira (Section 6).
- **Outputs.** PRD, stories and acceptance criteria with citations and per-claim verification status.

| ID | Requirement | Priority | Src |
|---|---|---|---|
| FR-DOC-01 | The system shall generate a PRD draft for a selected opportunity using only evidence stored in the workspace. | Must | B |
| FR-DOC-02 | The system shall structure each PRD with these sections: problem statement, supporting evidence, goals, scope, user stories, acceptance criteria, success metrics, risks, open questions. | Must | P |
| FR-DOC-03 | The system shall link every factual claim in a generated document to at least one evidence item. | Must | B |
| FR-DOC-04 | The system shall mark each claim with its verification status from AIR-14 to AIR-17. | Must | B |
| FR-DOC-05 | The system shall generate user stories in the form "As a [user], I want [goal], so that [benefit]". | Must | B |
| FR-DOC-06 | The system shall generate at least one acceptance criterion per user story in the form "Given [context], when [action], then [outcome]". | Must | B |
| FR-DOC-07 | The system shall open the original record when the user selects a citation. | Must | B |
| FR-DOC-08 | The system shall keep every generated document in draft status until an Editor approves it. | Must | B |
| FR-DOC-09 | The system shall state that evidence is insufficient instead of asserting a claim that does not meet A-13. | Should | B/P |
| FR-DOC-10 | The system shall keep a version history of every Editor edit to a generated document. | Should | P |
| FR-DOC-11 | The system shall export a document in the format in A-18. | Should | P |
| FR-DOC-12 | The system shall include linked metrics and any feedback-versus-behaviour conflict in the PRD's evidence section. | Could | B |

**Errors.** If generation fails or returns invalid structure, the system retries within A-15, then shows any completed sections with the failed ones clearly marked. Unsupported claims are shown flagged, never silently removed or kept. Generation is blocked with an explanation when no evidence exists. A concurrent edit is refused with the newer version shown.

| ID | Acceptance criterion | Verifies |
|---|---|---|
| AC-DOC-01 | Given a generated PRD, then 100% of cited evidence IDs exist in the workspace, and every claim without valid evidence is flagged. | FR-DOC-03, FR-DOC-04 |
| AC-DOC-02 | Given a generated PRD, then every number in it equals the value computed from stored data. | AIR-16 |
| AC-DOC-03 | Given a reviewer who did not build the system, when reading a generated PRD, then the reviewer can identify the source customer problem through its citations. | FR-DOC-01, FR-DOC-03, FR-DOC-07 |
| AC-DOC-04 | Given a user story, then it follows the required form and has at least one acceptance criterion in Given/When/Then form. | FR-DOC-05, FR-DOC-06 |
| AC-DOC-05 | Given a draft containing an unsupported claim, when an Editor tries to approve it, then approval requires acknowledging each flagged claim. | FR-DOC-08, SEC-13 |

### 3.8 Module 8: Roadmap Planning and Visualization

- **Purpose.** Propose what to build when, and show it visually; sequencing must reflect priorities and plausible effort, not arbitrary dates (SRC-1 §2, §4).
- **Actors and preconditions.** Editor (edit), all roles (view). Ranked opportunities exist.
- **Inputs.** Ranked opportunities, effort estimates, dependencies, capacity assumption.
- **Workflow.** Request a roadmap, supply or accept effort estimates, view the proposed sequence, reorder and save.
- **Outputs.** Visual roadmap with items linked to opportunities and evidence.

| ID | Requirement | Priority | Src |
|---|---|---|---|
| FR-RMP-01 | The system shall propose a roadmap that orders the selected opportunities by score and effort. | Must | B |
| FR-RMP-02 | The system shall accept an Editor's effort estimate for each opportunity and label any system-suggested effort as an estimate. | Must | B/P |
| FR-RMP-03 | The system shall display the roadmap visually as Now, Next and Later lanes. | Must | B/P |
| FR-RMP-04 | The system shall flag any roadmap order that violates a dependency declared by an Editor. | Should | B/P |
| FR-RMP-05 | The system shall preserve the order and edits an Editor makes to roadmap items. | Should | P |
| FR-RMP-06 | The system shall link each roadmap item to its opportunity and supporting evidence. | Should | B |
| FR-RMP-07 | The system shall show the capacity assumption used for sequencing and allow an Editor to change it. | Could | P |

**Errors.** Items without effort estimates go to an "unscheduled" group. Circular dependencies are rejected with the cycle shown. With no ranked opportunities, roadmap generation is blocked with an explanation.

| ID | Acceptance criterion | Verifies |
|---|---|---|
| AC-RMP-01 | Given opportunities with different scores and efforts, then the proposed order follows the documented sequencing rule. | FR-RMP-01 |
| AC-RMP-02 | Given a declared dependency, then the dependent item is never placed before the item it depends on. | FR-RMP-04 |
| AC-RMP-03 | Given a reordered roadmap, when saved and reloaded, then the order is preserved. | FR-RMP-05 |

### 3.9 Module 9: Conversational Product Intelligence Assistant

- **Purpose.** Let a PM ask questions such as "what are users complaining about most since the last release?" and receive grounded answers (SRC-1 §2, §7).
- **Actors and preconditions.** All roles. Active workspace with analysed data.
- **Inputs.** Natural-language questions.
- **Workflow.** The user asks; the assistant selects permitted read-only tools (Section 6); counts come from computation and qualitative evidence from retrieval; the answer is composed, verified and shown with citations.
- **Outputs.** A cited answer, or a statement that the data does not support an answer.

| ID | Requirement | Priority | Src |
|---|---|---|---|
| FR-AST-01 | The system shall let a user ask questions in natural language about the active workspace. | Must | B |
| FR-AST-02 | The system shall answer only from the active workspace's data. | Must | B |
| FR-AST-03 | The system shall include in every answer citations that open the records or metrics it relies on. | Must | B |
| FR-AST-04 | The system shall derive every count, share and trend in an answer from computation on stored data. | Must | P |
| FR-AST-05 | The system shall state that the data is insufficient when it cannot support an answer. | Must | B |
| FR-AST-06 | The system shall answer questions bounded by a date range or by a registered release. | Should | B |
| FR-AST-07 | The system shall show which tools and data sources were used for each answer. | Should | P |
| FR-AST-08 | The system shall mention a relevant feedback-versus-behaviour conflict in an answer. | Could | B |
| FR-AST-09 | The system shall keep conversation history per user and workspace. | Could | P |
| FR-AST-10 | The system shall let the user mark an answer as helpful or incorrect and store the mark for evaluation. | Could | P |

**Errors.** Questions outside the data receive an insufficiency statement. A tool failure is reported as a missing part, never filled in. If the language model is unavailable, the user is told and no answer is fabricated (AIR-22). Requests touching other workspaces are refused and logged.

| ID | Acceptance criterion | Verifies |
|---|---|---|
| AC-AST-01 | Given "What are users complaining about most since the last release?", then the answer lists themes supported by records dated after the latest registered release, with working citations. | FR-AST-01, FR-AST-03, FR-AST-06 |
| AC-AST-02 | Given a question the data cannot answer, then the assistant says the data is insufficient. | FR-AST-05 |
| AC-AST-03 | Given a question asking for a count, then the number equals the value computed from stored data. | FR-AST-04 |
| AC-AST-04 | Given the evaluation question set (TST-10), then grounded-answer and correct-refusal rates are reported. | FR-AST-02, FR-AST-05 |

### 3.10 Module 10: Reporting and Insights Dashboard

- **Purpose.** A clear, visual home for the insights, plus executive summaries (SRC-1 §2).
- **Actors and preconditions.** All roles (view), Editor (generate summaries). Analysed data exists.
- **Inputs.** Analysed workspace data; filters.
- **Workflow.** Open the dashboard, filter, drill down to records, request an executive summary.
- **Outputs.** Dashboard views; executive summary.

| ID | Requirement | Priority | Src |
|---|---|---|---|
| FR-DSH-01 | The system shall show the main pain points with record counts, unique-customer counts and trend direction. | Must | B |
| FR-DSH-02 | The system shall let the user drill down from any dashboard figure to the records behind it. | Must | B |
| FR-DSH-03 | The system shall generate an executive summary containing the top pain points, recommended priorities, risks and conflicts, and next steps, with every claim cited. | Must | B |
| FR-DSH-04 | The system shall show trend charts over time by theme and sentiment. | Should | B |
| FR-DSH-05 | The system shall show the top-ranked opportunities with a one-line reason each. | Should | B |
| FR-DSH-06 | The system shall filter dashboard figures by date range, source type, theme and product version. | Should | P |
| FR-DSH-07 | The system shall show when data was last imported and last analysed, and indicate when analysis is out of date. | Should | P |
| FR-DSH-08 | The system shall show feedback-versus-behaviour conflicts when analytics data exists. | Could | B |
| FR-DSH-09 | The system shall export the dashboard summary and executive summary in the format in A-18. | Could | P |

**Errors.** With no data, the dashboard shows guidance to import instead of empty charts. Out-of-date analysis is shown with a notice. If summary generation fails, the dashboard remains usable and the failure is reported.

| ID | Acceptance criterion | Verifies |
|---|---|---|
| AC-DSH-01 | Given any displayed count, when the user drills down, then the number of records shown equals the count. | FR-DSH-02 |
| AC-DSH-02 | Given an executive summary, then every claim has a working citation and every number matches stored data. | FR-DSH-03 |
| AC-DSH-03 | Given an Editor merges two themes, then dashboard figures reflect the merge after recomputation. | FR-DSH-01, FR-THM-09 |

---

## 4. Data Requirements and Ingestion Pipeline

The mentor stressed that data is rarely ready to use and must be cleaned, noise-filtered, normalised and organised before the AI system can use it (SRC-2). This section states what the pipeline must achieve. The pipeline design and libraries are in the architecture document.

### 4.1 Input sources

| Source | Typical fields | Particular difficulties |
|---|---|---|
| Customer feedback and reviews | Text, rating, date, product version, customer identifier | Spam, sarcasm, very short text, mixed languages |
| Support tickets | Subject, body, status, priority, timestamps, customer identifier | Signatures, quoted replies, agent text mixed with customer text |
| Feature requests | Text, requester, date, product area | Many wordings of the same ask |
| Product analytics | Metric name, date, value, optional dimension | Numeric; handled by Module 3, not by text processing |
| Meeting transcripts | Speaker, time, text | Long, multi-topic, contains personal data |

### 4.2 Data lifecycle: from raw input to analysis-ready data

| Stage | What happens | Output |
|---|---|---|
| L1 Capture | File stored exactly as received, with an import job record | Raw layer (immutable) |
| L2 Validate | Type, size, encoding, required fields | Accepted rows; rejected rows with reasons |
| L3 Parse and map | Map to the common record structure | Structured records |
| L4 Clean and filter | Neutralise markup and boilerplate; flag noise and spam | Cleaned records with flags and reasons |
| L5 De-duplicate | Exact and near-duplicate detection | Duplicates linked to a primary record |
| L6 Standardise | Text, structural, temporal, categorical, identifier standardisation | Standardised records |
| L7 Protect | Detect and mask PII | Masked text used by everything downstream |
| L8 Enrich | Language detection, categorisation, sentiment, semantic representation, indexing | Analysis-ready records |
| L9 Analyse | Themes, aggregated requests, statistics | Derived results |
| L10 Report | Counts, rates, reconciliation | Import report and quality measures |

### 4.3 What "normalisation" means in this project

The word normalisation has three distinct meanings. The mentor's reference to "three, four types of normalisation" within the data pipeline (SRC-2) is interpreted as the first two. The third is a database design property.

| Meaning | Where it applies | How this project handles it |
|---|---|---|
| Data cleaning and standardisation | Ingestion pipeline (L4 to L6) | DR-11 to DR-23 |
| Five types of standardisation: text, structural, temporal, categorical, identifier | Ingestion pipeline (L6) | DR-19 to DR-23, one requirement each |
| Relational database normalisation (1NF, 2NF, 3NF) | Logical and physical database design | Not a functional requirement. The architecture document designs the schema in third normal form, with documented exceptions for derived statistics |

### 4.4 Ingestion and import

| ID | Requirement | Priority | Src |
|---|---|---|---|
| DR-01 | The system shall tag every imported record with its source type. | Must | B |
| DR-02 | The system shall record each import as a job with an identifier, submitting user, workspace, source type, start time, end time and status. | Must | M/P |
| DR-03 | The system shall record the last lifecycle stage (Section 4.2) reached by each record. | Should | M/P |
| DR-04 | The system shall allow stored raw data to be re-processed after a change to cleaning or categorisation rules, without a new upload. | Should | P |

### 4.5 File formats and validation

| ID | Requirement | Priority | Src |
|---|---|---|---|
| DR-05 | The system shall accept CSV files encoded in UTF-8, JSON files containing an array of records, and plain-text files for transcripts. | Must | P |
| DR-06 | The system shall validate each upload's actual content type, size against A-06, encoding and required fields before processing. | Must | P |
| DR-07 | The system shall reject any record whose text is empty after trimming and count it in the import report. | Should | P |
| DR-08 | The system shall keep a record whose timestamp cannot be parsed, mark the timestamp as missing, and count it in the import report. | Should | P |
| DR-09 | The system shall report every validation failure with its row or position and the reason. | Should | P |
| DR-10 | The system shall warn the user when an uploaded file is identical to a file already imported into the same workspace. | Should | P |

### 4.6 Cleaning, noise and spam filtering

| ID | Requirement | Priority | Src |
|---|---|---|---|
| DR-11 | The system shall remove markup, control characters and boilerplate (such as email signatures and quoted reply chains) from the processed text while keeping the original text. | Must | M |
| DR-12 | The system shall flag records that meet the noise rule in A-09, with the reason. | Should | M/P |
| DR-13 | The system shall flag likely spam with a reason and exclude flagged records from analysis by default while keeping them viewable. | Should | B/M |
| DR-14 | The system shall keep an Editor's confirmation or reversal of a noise or spam flag in later runs. | Could | P |
| DR-15 | The system shall never delete original data as a result of filtering. | Should | P |

### 4.7 Duplicate detection

| ID | Requirement | Priority | Src |
|---|---|---|---|
| DR-16 | The system shall detect exact duplicates: records in the same workspace with identical standardised text. | Must | B |
| DR-17 | The system shall detect near-duplicates using a configurable similarity threshold (A-10). | Should | B |
| DR-18 | The system shall link each duplicate to a primary record without counting it as an additional customer or additional evidence. | Must | B/P |

### 4.8 Standardisation

| ID | Requirement | Priority | Src |
|---|---|---|---|
| DR-19 | **Text:** The system shall store processed text in one character encoding and Unicode normal form with consistent whitespace and line breaks. | Must | M/P |
| DR-20 | **Structural:** The system shall map every source to one common record structure before analysis. | Must | M/P |
| DR-21 | **Temporal:** The system shall store timestamps in UTC (A-23). | Must | M/P |
| DR-22 | **Categorical:** The system shall map source-specific values (rating scales, version labels, ticket status and priority) to a standard vocabulary (A-24), and flag values it cannot map. | Should | M/P |
| DR-23 | **Identifier:** The system shall replace customer identifiers with workspace-scoped pseudonymous keys so that unique customers can be counted without exposing identities. | Must | B/P |

### 4.9 Preprocessing and categorisation

| ID | Requirement | Priority | Src |
|---|---|---|---|
| DR-24 | The system shall detect and store the language of each record. | Should | B |
| DR-25 | The system shall flag non-English records and exclude them from theme analysis by default (A-03). | Should | B/P |
| DR-26 | The system shall compute and index a semantic representation of every analysed record and store the identifier of the method used. | Must | M/P |
| DR-27 | The system shall split meeting transcripts into segments and link each segment to its parent transcript. | Could | P |

### 4.10 Personal information detection and masking

| ID | Requirement | Priority | Src |
|---|---|---|---|
| DR-28 | The system shall detect email addresses, phone numbers, payment card numbers, government identifier patterns and personal names in record text. | Must | B |
| DR-29 | The system shall replace detected personal information with typed placeholders (for example `[EMAIL]`) in the processed text before the text is sent to any language model or shown outside the raw-record view. | Must | B/P |
| DR-30 | The system shall show raw text containing personal information only to the workspace Owner (A-22). | Should | P |

### 4.11 Reporting, storage and traceability

| ID | Requirement | Priority | Src |
|---|---|---|---|
| DR-31 | The system shall report for each import the counts of records received, imported, rejected, duplicates, noise, spam, PII items masked by type, and records per language. | Must | B/P |
| DR-32 | The system shall compute for each import the completeness of required fields, duplicate rate, spam rate and date range. | Should | P |
| DR-33 | The system shall keep raw, processed and derived data as separate layers linked by evidence ID. | Should | P |
| DR-34 | The system shall store, with every derived result, the source records it came from and the identifiers of the method and prompt template versions that produced it. | Must | B/P |
| DR-35 | The system shall keep raw data unchanged after import, removing it only through import removal or workspace deletion, each recorded in the audit log. | Should | P |

### 4.12 Failure handling and recovery

| ID | Requirement | Priority | Src |
|---|---|---|---|
| DR-36 | The system shall continue processing the remaining records of an import when individual records fail. | Should | P |
| DR-37 | The system shall store each failed record with its stage and reason in a failure list that the user can download. | Should | P |
| DR-38 | The system shall retry a stage that fails for a transient reason at most 2 times before marking the record failed. | Should | P |
| DR-39 | The system shall resume or safely restart an interrupted import without losing or duplicating records. | Should | P |
| DR-40 | The system shall reconcile every import (received = imported + rejected + duplicates + filtered + failed) and report any discrepancy as an error. | Must | P |

### 4.13 Analytics data

| ID | Requirement | Priority | Src |
|---|---|---|---|
| DR-41 | The system shall accept metric rows containing a metric name, a date and a numeric value, with an optional dimension, and reject other rows with reasons. | Must | B/P |

### 4.14 Logical data entities

The following entities must be representable. The physical schema is designed in the architecture document.

| Entity | Purpose |
|---|---|
| User, Workspace, Membership | Identity, isolation and roles |
| ImportJob, ImportFailure | Import tracking, report and failures |
| FeedbackRecord | Evidence: original text, processed text, source, language, dates, flags, pseudonymous customer key, labels |
| Metric, Release | Analytics and release markers |
| Theme, ThemeMembership | Themes and their member records |
| AggregatedRequest, RequestMembership | Grouped feature requests |
| Opportunity, ScoreInput, Ranking | Prioritisation with input origins |
| Document, DocumentVersion, Claim, ClaimEvidence | Generated documents and verification |
| RoadmapItem, Dependency | Roadmap |
| Conversation, Message | Assistant history |
| Integration, ExternalLink, Approval | Jira configuration, created items, approvals |
| AuditEntry, ModelCallRecord, EvaluationRun | Audit, AI call records, evaluation results |

---

## 5. AI Behaviour Requirements

### 5.1 Principles

1. AI output is advisory; the PM decides (SRC-1 §1).
2. Every analytical statement must be traceable to stored evidence (SRC-1 §4, §6).
3. Counts, shares, trends and scores are computed by deterministic code; the language model supplies wording, grouping suggestions and rationale.
4. "Insufficient evidence" is an acceptable answer.
5. Model, embedding and method choices belong to the architecture (C-03).

### 5.2 Classification and themes

| ID | Requirement | Priority | Src |
|---|---|---|---|
| AIR-01 | The system shall accept a classification output only if its label is one of the allowed taxonomy values. | Must | B/P |
| AIR-02 | The system shall attach a confidence value between 0 and 1 to each AI-assigned label. | Should | P |
| AIR-03 | The system shall determine theme membership and all theme statistics from stored records, using the language model only to propose theme names and descriptions. | Must | B |
| AIR-04 | The system shall produce the same theme memberships when analysis is re-run on unchanged data with unchanged configuration. | Should | P |

### 5.3 Retrieval and evidence

| ID | Requirement | Priority | Src |
|---|---|---|---|
| AIR-05 | The system shall retrieve only records of the active workspace that the user's role permits. | Must | B/P |
| AIR-06 | The system shall pass every retrieved record to the language model together with its evidence ID. | Must | B/P |
| AIR-07 | The system shall limit any evidence set given to the language model to A-14 records per customer. | Must | B |
| AIR-08 | The system shall never use the language model to produce counts, shares, trends or scores. | Must | P |

### 5.4 Output validation and failure handling

| ID | Requirement | Priority | Src |
|---|---|---|---|
| AIR-09 | The system shall validate every structured model output against its required structure before using it. | Must | P |
| AIR-10 | The system shall retry invalid structured output within the limit of A-15 and then mark the call as failed visibly. | Should | P |
| AIR-11 | The system shall stop any model call that exceeds the time limit in A-15 and report it as failed. | Should | P |
| AIR-12 | The system shall record for each model call: call point, prompt template version, model identifier, time, workspace, token counts, latency and outcome. | Should | M/P |

### 5.5 Claims, citations and verification

| ID | Requirement | Priority | Src |
|---|---|---|---|
| AIR-13 | The system shall classify every claim in generated text as quantitative, qualitative, quotation or recommendation. | Must | P |
| AIR-14 | The system shall verify that every cited evidence ID exists in the workspace and was part of the evidence set supplied for that generation. | Must | B |
| AIR-15 | The system shall verify that every quotation exactly matches the stored processed text of the cited record. | Should | B |
| AIR-16 | The system shall verify that every number in generated text equals the value computed from stored data. | Must | B/P |
| AIR-17 | The system shall assess whether each qualitative claim is supported by its cited evidence and show one status: supported, partly supported, unsupported or not checked. | Should | B |
| AIR-18 | The system shall show recommendations as the system's reasoning, visually separate from evidence. | Should | P |
| AIR-19 | The system shall mark all AI-generated content as AI-generated. | Should | B/P |

### 5.6 Evaluation, configuration and availability

| ID | Requirement | Priority | Src |
|---|---|---|---|
| AIR-20 | The system shall run the evaluation suite of Section 11 at each milestone and store the results. | Must | B |
| AIR-21 | The system shall allow the language model, embedding method and prompt template versions to be changed by configuration without code changes. | Should | C-03/P |
| AIR-22 | The system shall show AI features as unavailable when the language model cannot be reached, while all non-AI functions continue to work. | Should | P |
| AIR-23 | The system shall measure and report how consistently the same input receives the same label across repeated runs. | Should | P |
| AIR-24 | The system shall store Editor corrections to AI output for evaluation without altering raw data. | Could | P |
| AIR-25 | The system shall reuse a stored result when the input and prompt template version are identical. | Could | P |

### 5.7 Use of AI capabilities

| Capability | Where used | Governed by |
|---|---|---|
| Classification, sentiment | Module 4 | FR-THM-01, FR-THM-02, AIR-01, AIR-02 |
| Theme extraction | Module 4 | FR-THM-03, AIR-03, AIR-04 |
| Feature-request identification and aggregation | Module 5 | FR-AGG-01 to FR-AGG-04 |
| Semantic similarity | Duplicates, grouping, retrieval | DR-17, DR-26 |
| Retrieval-augmented generation | Documents, summaries, assistant | AIR-05 to AIR-07 |
| Conversational AI | Module 9 | FR-AST-01 to FR-AST-05 |
| Tool calling | Module 9 | AGR-06 to AGR-11 |
| AI-assisted prioritisation | Module 6 | FR-PRI-07, AIR-08 |
| PRD, story and acceptance-criteria generation | Module 7 | FR-DOC-01 to FR-DOC-09 |
| Evidence-backed responses | All generated text | AIR-13 to AIR-19 |

### 5.8 What happens around every language model call

The mentor asked how LLM calls happen and what happens after each call (SRC-2). Every call follows the same sequence:

1. **Assemble.** Build the input from stored data (records with evidence IDs, computed statistics) and a versioned prompt template.
2. **Protect.** Use masked text only (DR-29); mark customer text as data (SEC-07).
3. **Call.** Apply the time limit (AIR-11).
4. **Validate.** Check structure (AIR-09); retry within limits (AIR-10).
5. **Verify.** Check IDs, quotations and numbers (AIR-14 to AIR-16); assess support (AIR-17).
6. **Record.** Store the call record (AIR-12).
7. **Route.** Accept, send for human review, or mark as failed and tell the user.

### 5.9 Call points

| ID | Triggered by | Input | Output | After the call |
|---|---|---|---|---|
| CP-01 | Pipeline, borderline spam cases | Record text | Spam label with reason | Stored with confidence; Editor can reverse |
| CP-02 | Pipeline | Masked record text | Category, sentiment, sarcasm flag, confidence | Validated against taxonomy; low confidence sent to review |
| CP-03 | Analysis | Representative records of a group | Theme name and description | Validated; statistics computed separately from stored data |
| CP-04 | Analysis | Feature-request records | Canonical ask; same-or-different decision for borderline pairs | Low-confidence groupings flagged |
| CP-05 | User opens scoring | Evidence set and statistics | Suggested input values with rationale | Labelled as estimates; citations verified |
| CP-06 | User requests a PRD | Evidence set, statistics, template | Sections with typed claims and evidence IDs | Validated, verified, saved as draft |
| CP-07 | After CP-06 or CP-09 | Claim and cited records | Support status | Stored and shown per claim |
| CP-08 | User requests a summary | Verified statistics, themes, opportunities | Summary with claims and citations | Validated, verified, saved as draft |
| CP-09 | User asks a question | Question, history, tool definitions | Tool requests, then a cited answer | Tools validated and run within permissions; answer verified |

---

## 6. Agent and External Integration Requirements

### 6.1 Confirmed direction and open details

| Item | Status |
|---|---|
| Design the AI agent architecture | Requested by the mentor (SRC-2) |
| Use MCP to connect with Jira for creating user stories | Direction stated by the mentor (SRC-2) |
| Whether Jira creation is mandatory for the final demo | Open, B-03 |
| Jira site, MCP server, permissions, issue types, field mapping | Open, B-03; proposed defaults in the architecture |
| Updating existing Jira items; reading status back | Not requested; Future |
| Human approval before external actions | Team proposal, consistent with SRC-1 §1 |

### 6.2 Controlled workflows

| ID | Requirement | Priority | Src |
|---|---|---|---|
| AGR-01 | The system shall implement each multi-step AI behaviour as a defined workflow with explicit steps, inputs, outputs and stopping conditions. | Must | M/P |
| AGR-02 | The system shall give each workflow run an identifier, a state and a step log viewable by authorised users. | Should | P |
| AGR-03 | The system shall stop any workflow that exceeds the step or duration limits of A-16 and report why. | Must | P |
| AGR-04 | The system shall restart an interrupted workflow without repeating any external action already performed. | Should | P |
| AGR-05 | The system shall start workflows only in response to a user action or to processing that follows a user's import. | Should | P |

### 6.3 Tools and execution boundaries

| ID | Requirement | Priority | Src |
|---|---|---|---|
| AGR-06 | The system shall execute only tools on the registered tool list, refusing and logging any other tool request. | Must | M/P |
| AGR-07 | The system shall provide the assistant only with tools that read data. | Must | P |
| AGR-08 | The system shall run every tool with the requesting user's role and active workspace, both supplied by the system. | Must | P |
| AGR-09 | The system shall validate tool arguments against the tool's declared argument structure before execution. | Must | P |
| AGR-10 | The system shall limit the context given to the language model to the current conversation and workspace, and tell the user when evidence was truncated. | Should | P |
| AGR-11 | The system shall never execute model output as a command, query or program. | Must | P |

### 6.4 Jira integration through MCP

| ID | Requirement | Priority | Src |
|---|---|---|---|
| AGR-12 | The system shall access Jira only through MCP, from the integration component. | Should | M |
| AGR-13 | The system shall perform Jira operations only from deterministic application code after approval, never as a tool the language model can call. | Should | P |
| AGR-14 | The system shall allow the Owner to configure and test the Jira connection. | Should | M/P |
| AGR-15 | The system shall limit the Jira operations it uses to an allow-list: listing projects and issue types, reading field metadata, creating issues, and reading a created issue. | Should | P |
| AGR-16 | The system shall store Jira credentials encrypted and never expose them to the language model, the interface or logs. | Should | P |
| AGR-17 | The system shall create Jira issues from approved user stories containing at least a summary, a description and the acceptance criteria. | Should | M |
| AGR-18 | The system shall include in each Jira issue a reference to the source PRD and an evidence summary, with no personal information. | Should | P |
| AGR-19 | The system shall show a preview of exactly what will be created before any Jira issue is created. | Should | P |
| AGR-20 | The system shall create Jira issues only after an authorised user approves that specific preview. | Should | M/P |
| AGR-21 | The system shall store each approval with approver, time and the exact content approved. | Should | P |
| AGR-22 | The system shall allow the approver to edit or reject items in the preview, making no external call for rejected items. | Should | P |
| AGR-23 | The system shall store each created issue's key and link against its story and prevent creating the same story twice unless the user confirms. | Should | P |
| AGR-24 | The system shall report which items of a Jira batch succeeded and which failed, without automatically retrying create operations. | Should | P |
| AGR-25 | The system shall keep all other functions available when the Jira integration is unavailable or not configured. | Should | P |
| AGR-26 | The system shall update a linked Jira issue after an approved story is edited. | Future | P |
| AGR-27 | The system shall show the current Jira status of each linked issue. | Future | P |

---

## 7. Non-Functional Requirements

Numeric targets are stated only where they follow from a constraint or a deterministic check. Other targets are set from a measured baseline and agreed with the mentor (Section 11.3).

### 7.1 Performance and resources

| ID | Requirement | Measurement | Priority | Src |
|---|---|---|---|---|
| NFR-01 | The system shall display an import's status within 2 seconds after the upload completes. | Timed test | Should | P |
| NFR-02 | The system shall load the dashboard and theme pages within 3 seconds for the reference workspace (A-05) on the reference laptop. | Timed page loads; target confirmed after baseline | Should | P |
| NFR-03 | The system shall have its pipeline throughput measured and reported each milestone, separately for non-AI and AI stages. | Benchmark run | Should | P |
| NFR-04 | The system shall show a progress indicator or the start of an answer within 2 seconds of an assistant question being submitted. | Timed test | Should | P |
| NFR-05 | The system shall run the end-to-end demo (UC-12) on the reference laptop with at least 1.5 GB of system memory available throughout and the language model running entirely on the GPU. | Resource log during demo rehearsal | Must | T |
| NFR-06 | The system shall operate without any paid service, subscription or API key. | Inspection of configuration and dependencies | Must | T |
| NFR-07 | The system shall run with no more than four continuously running services in demo mode: web and API, background worker, database, model runtime. | Inspection | Should | T/P |

### 7.2 Reliability and availability

| ID | Requirement | Measurement | Priority | Src |
|---|---|---|---|---|
| NFR-08 | The system shall satisfy DR-40 for 100% of test imports, including imports interrupted on purpose. | Reconciliation tests | Must | P |
| NFR-09 | The system shall prevent a failed job in one workspace from changing data in any other workspace. | Fault-injection test | Should | P |
| NFR-10 | The system shall resume, or mark for restart, every interrupted job within 1 minute of the application restarting. | Restart test | Should | P |
| NFR-11 | The system shall provide a demo readiness check covering model availability, database connectivity, seed data and, if configured, Jira connectivity. | Executed before each milestone demo | Should | P |

### 7.3 Maintainability

| ID | Requirement | Measurement | Priority | Src |
|---|---|---|---|---|
| NFR-12 | The system shall hold prompt templates, scoring formulas, taxonomy and thresholds as versioned configuration rather than in code. | Inspection; a change creates a new version | Should | P |
| NFR-13 | The system shall have every Must requirement covered by at least one test case listed in the test plan. | Traceability review | Must | P |
| NFR-14 | The system shall access the language model, embedding method and Jira through internal interfaces, so that replacing a provider changes only its adapter. | Inspection; replacement exercise | Should | P |
| NFR-15 | The system shall run its automated test suite on every change merged into the main branch. | CI history | Should | P |

### 7.4 Usability and accessibility

| ID | Requirement | Measurement | Priority | Src |
|---|---|---|---|---|
| NFR-16 | The system shall allow at least 4 of 5 first-time users to import a file, find a theme and open its evidence without assistance. | Usability test | Should | B/P |
| NFR-17 | The system shall make the evidence behind any AI-generated item reachable in one interaction. | Interface inspection | Must | B |
| NFR-18 | The system shall state in every error message what went wrong and what the user can do next. | Review of defined error cases | Should | P |
| NFR-19 | The system shall provide defined empty, loading and error states for every data view. | Interface inspection | Should | P |
| NFR-20 | The system shall make core flows operable by keyboard and meet WCAG 2.2 level AA colour contrast. | Automated accessibility checks plus manual keyboard test | Should | P |

### 7.5 Privacy, isolation, auditability and observability

| ID | Requirement | Measurement | Priority | Src |
|---|---|---|---|---|
| NFR-21 | The system shall send no unmasked seeded personal information to the language model. | Seeded test; inspection of logged model inputs | Must | B |
| NFR-22 | The system shall show zero cross-workspace data exposures across the isolation test suite. | TST-12 | Must | B |
| NFR-23 | The system shall show, for any generated document, the evidence used, the model and prompt template versions, the approver and the approval time. | Inspection | Should | B/P |
| NFR-24 | The system shall tag every log entry with a correlation identifier for its request or job. | Log inspection | Should | P |
| NFR-25 | The system shall make model usage (calls, tokens, latency, failures) viewable by the team. | Inspection | Should | P |

### 7.6 AI quality and explainability

| ID | Requirement | Measurement | Priority | Src |
|---|---|---|---|---|
| NFR-26 | The system shall display only citations that refer to an existing evidence item in the same workspace. | Automatic citation check on all evaluation outputs; target 100% | Must | B |
| NFR-27 | The system shall display only numbers in generated text that equal the values computed from stored data. | Automatic comparison; target 100% | Must | B |
| NFR-28 | The system shall have the quality metrics of TST-05 to TST-10 measured each milestone, with targets set from the first baseline and agreed with the mentor. | Evaluation reports | Must | B |
| NFR-29 | The system shall have its unsupported-claim rate reported each milestone. | Verification statistics | Should | B |
| NFR-30 | The system shall keep evaluation datasets, scripts and configurations versioned so that results can be reproduced. | Re-run produces the same report | Should | B/P |

---

## 8. External Interface Requirements

| ID | Requirement | Priority | Src |
|---|---|---|---|
| IR-01 | The system shall provide a web user interface supporting the browsers in OE-01. | Must | P |
| IR-02 | The system shall provide navigation to workspace selection, imports, themes, feature requests, opportunities, documents, roadmap, assistant and dashboard. | Should | B/P |
| IR-03 | The system shall use one shared evidence viewer for every citation in the interface. | Must | B/P |
| IR-04 | The system shall expose an authenticated, workspace-scoped HTTP API for every user-interface function. | Must | M/P |
| IR-05 | The system shall describe its HTTP API in a machine-readable specification. | Should | P |
| IR-06 | The system shall return API errors in one consistent format. | Should | P |
| IR-07 | The system shall support pagination and filtering on API endpoints that return lists of records, themes or requests. | Should | P |
| IR-08 | The system shall route all language model and embedding calls through one internal interface. | Must | M/P |
| IR-09 | The system shall show upload limits, upload progress and validation results in the upload interface. | Should | P |
| IR-10 | The system shall perform Jira operations through an MCP client within the integration component. | Should | M |
| IR-11 | The system shall perform all database access through a data-access layer that applies workspace scoping. | Must | P |

---

## 9. Security, Privacy and AI Guardrails

| ID | Requirement | Priority | Src |
|---|---|---|---|
| SEC-01 | The system shall store passwords only as salted hashes produced by a slow password-hashing algorithm. | Must | P |
| SEC-02 | The system shall throttle failed sign-in attempts as defined in A-08. | Should | P |
| SEC-03 | The system shall check authorisation on the server for every request. | Must | B/P |
| SEC-04 | The system shall derive the workspace for every request from the authenticated session and membership, never from an unverified value supplied by the client or the language model. | Must | B/P |
| SEC-05 | The system shall protect state-changing requests against cross-site request forgery. | Should | P |
| SEC-06 | The system shall pass the isolation test suite (TST-12) before each milestone demo. | Must | B/P |
| SEC-07 | The system shall present customer text to the language model as clearly delimited data and instruct the model not to follow instructions found in it. | Must | P |
| SEC-08 | The system shall give no tool access to model calls that process imported customer text. | Must | P |
| SEC-09 | The system shall pass the prompt-injection test suite (TST-13) at each milestone with no unauthorised tool call, external action or cross-workspace disclosure. | Must | P |
| SEC-10 | The system shall escape stored text when displaying it, so that it cannot run as script. | Should | P |
| SEC-11 | The system shall store uploaded files outside any directory served to browsers and never execute them. | Should | P |
| SEC-12 | The system shall neutralise leading formula characters (=, +, -, @) in exported spreadsheet-compatible files. | Should | P |
| SEC-13 | The system shall allow approval of a document that contains unsupported claims only after an Editor acknowledges each such claim, and keep the markings visible. | Must | B/P |
| SEC-14 | The system shall record in the audit log: sign-ins and failed sign-ins, membership changes, imports and removals, Editor overrides, document approvals, Jira actions, refused tool calls and workspace deletion. | Should | P |
| SEC-15 | The system shall record each audit entry with actor, action, target, time and outcome in a store that users cannot edit or delete. | Should | P |
| SEC-16 | The system shall allow the Owner to view the workspace audit log. | Could | P |
| SEC-17 | The system shall exclude raw personal information, passwords, tokens and credentials from logs. | Should | P |
| SEC-18 | The system shall keep secrets out of source code and version control. | Must | P |
| SEC-19 | The system shall use TLS for all communication with external services, and HTTPS if the application is served beyond the local machine. | Should | P |
| SEC-20 | The system shall provide a documented procedure to back up and restore the database. | Should | P |
| SEC-21 | The system shall assign the Viewer role to newly added members by default. | Could | P |

**Coverage of trust topics.**

| Topic | Requirements |
|---|---|
| Hallucination prevention | AIR-08, AIR-13 to AIR-17, FR-DOC-09, FR-AST-05, SEC-13 |
| Evidence traceability | FR-ING-06, DR-33, DR-34, FR-DOC-03, FR-DOC-07, NFR-23 |
| Citation correctness | AIR-14, NFR-26 |
| Exact quotation | AIR-15 |
| Numeric accuracy | AIR-08, AIR-16, FR-AST-04, NFR-27 |
| Prompt injection | SEC-07 to SEC-09, AGR-06 to AGR-11, AGR-13 |
| PII | DR-28 to DR-30, NFR-21, SEC-17 |
| Workspace isolation | FR-AUTH-06, FR-AUTH-07, SEC-04, SEC-06, IR-11, NFR-22 |
| Invalid model output | AIR-09, AIR-10 |
| Low confidence | AIR-02, FR-THM-08, FR-AGG-06 |
| Missing or conflicting evidence | FR-DOC-09, FR-AST-05, FR-ANA-05 |
| Timeouts and model failure | AIR-11, AIR-22 |
| Duplicate ingestion | DR-10, DR-16 to DR-18, FR-ING-07 |
| Import recovery | DR-36 to DR-40 |
| Human approval | FR-DOC-08, AGR-19 to AGR-22, SEC-13 |
| Audit | SEC-14 to SEC-16, NFR-23 |

---

## 10. Use Cases

| ID | Use case | Actor | Preconditions | Main flow (requirements) | Alternate and error flows | Result |
|---|---|---|---|---|---|---|
| UC-01 | Register and create a workspace | Visitor | None | Register (FR-AUTH-01); sign in (FR-AUTH-02); create workspace (FR-AUTH-05); optionally add members (FR-AUTH-08) | Duplicate email refused; throttled sign-in (SEC-02) | Isolated workspace exists |
| UC-02 | Upload customer feedback | Editor | Active workspace | Choose source type (FR-ING-02); upload (FR-ING-01); map columns (FR-ING-03); background processing (FR-ING-04, Section 4.2); view report (FR-ING-05) | Invalid file rejected (DR-06, DR-09); partial failure and retry (DR-36 to DR-39, FR-ING-07); identical file warning (DR-10) | Records stored with evidence IDs; report shown |
| UC-03 | Import analytics and releases | Editor | Active workspace | Upload metrics (FR-ANA-01, DR-41); register releases (FR-ANA-02); view trends (FR-ANA-03) | Invalid rows listed | Metrics and releases stored |
| UC-04 | Analyse feedback | Editor | Records prepared | Classify (FR-THM-01, FR-THM-02); group into themes (FR-THM-03); compute statistics (FR-THM-05); flag vocal-customer themes and low confidence (FR-THM-06, FR-THM-08) | Model unavailable (AIR-22); sample too small | Themes with evidence |
| UC-05 | Identify recurring problems | Any role | Analysis done | Open dashboard (FR-DSH-01); open a theme and its evidence (FR-THM-04, FR-DSH-02); review aggregated requests (FR-AGG-03, FR-AGG-04); check conflicts (FR-ANA-05) | No data: guidance shown | User sees evidenced pain points |
| UC-06 | Prioritise opportunities | Editor | Themes or requests exist | List opportunities (FR-PRI-01); score with RICE (FR-PRI-02, FR-PRI-03); inspect origins (FR-PRI-04); change inputs and see movement (FR-PRI-05) | Missing inputs (item incomplete); AI suggestion fails (manual entry) | Explainable ranking |
| UC-07 | Generate a PRD | Editor | Opportunity with evidence | Request PRD (FR-DOC-01); evidence assembled (AIR-05 to AIR-07); draft generated (FR-DOC-02, FR-DOC-05, FR-DOC-06); verified (AIR-14 to AIR-17); review citations (FR-DOC-07); approve (FR-DOC-08) | Insufficient evidence (FR-DOC-09); failed sections marked; unsupported claims need acknowledgement (SEC-13) | Approved, traceable PRD |
| UC-08 | Create Jira stories | Editor | Approved stories; Jira configured (AGR-14) | Select stories; preview (AGR-19); edit or reject (AGR-22); approve (AGR-20, AGR-21); issues created through MCP (AGR-12, AGR-17); keys stored (AGR-23) | Rejection makes no call; partial failure reported (AGR-24); Jira unavailable (AGR-25) | Stories in Jira, linked and audited |
| UC-09 | Ask the assistant | Any role | Analysed data | Ask (FR-AST-01); tools selected and run (AGR-06 to AGR-09); counts computed (FR-AST-04); cited answer (FR-AST-03) | Insufficient data (FR-AST-05); tool failure reported; cross-workspace request refused | Grounded answer or honest refusal |
| UC-10 | Review the roadmap | Editor | Ranked opportunities | Propose roadmap (FR-RMP-01); set efforts (FR-RMP-02); view lanes (FR-RMP-03); reorder (FR-RMP-05) | Missing effort (unscheduled); circular dependency rejected | Saved roadmap |
| UC-11 | Produce dashboard and executive summary | Editor | Analysed data | Filter dashboard (FR-DSH-06); drill down (FR-DSH-02); generate summary (FR-DSH-03); export (FR-DSH-09) | Summary failure leaves dashboard usable | Cited executive summary |
| UC-12 | End-to-end demo | Editor | Seed dataset | UC-01, UC-02, UC-03, UC-04, UC-05, UC-06, UC-07, UC-10, UC-11, UC-09, then UC-08 if Jira is configured | Each step's error flows above | Brief's success criteria SC-01 to SC-06 demonstrated |

---

## 11. Verification and Evaluation

### 11.1 Evaluation data

- A hand-labelled set of at least 300 records drawn from the chosen public dataset, labelled independently by two team members for category, sentiment, theme group and duplicates. Agreement between labellers is measured with Cohen's kappa; disagreements are resolved and documented (team proposal).
- The set includes seeded cases the brief requires to be handled (SRC-1 §6, question 7): duplicates, spam, sarcasm, non-English text, personal information, and prompt-injection strings.
- A fixed set of about 30 assistant questions (answerable, unanswerable and adversarial) and a team-produced manual ranking of opportunities for comparison.
- Evaluation data, scripts and configurations are versioned (NFR-30).

### 11.2 Verification activities

| ID | Activity | What is verified | Main requirements |
|---|---|---|---|
| TST-01 | Functional testing | Each acceptance criterion in Section 3 | All FR- |
| TST-02 | API testing | Authentication, role enforcement, error format, pagination | IR-04 to IR-07, FR-AUTH-02, SEC-03, SEC-05 |
| TST-03 | Database testing | Workspace scoping of every query; constraints; repeatable migrations; raw-data immutability | FR-AUTH-06, IR-11, DR-33 to DR-35 |
| TST-04 | Pipeline testing | Each stage with seeded data; reconciliation; interruption and restart | DR-01 to DR-41, NFR-08 |
| TST-05 | Classification and theme evaluation | Accuracy and macro-F1 per label; theme agreement with labelled groups; vocal-customer flag; reproducibility | AIR-01 to AIR-04, AIR-23, FR-THM-01 to FR-THM-10 |
| TST-06 | Aggregation evaluation | Pairwise precision and recall on labelled paraphrase sets | FR-AGG-01 to FR-AGG-04 |
| TST-07 | Prioritisation evaluation | Determinism; sensitivity to input changes; rank correlation with the manual ranking | FR-PRI-01 to FR-PRI-08 |
| TST-08 | Generated document evaluation | Citation validity; numeric accuracy; quotation check; claim-support rate; rubric scores from three reviewers | FR-DOC-01 to FR-DOC-09, FR-DSH-03, AIR-13 to AIR-17, NFR-26, NFR-27, NFR-29 |
| TST-09 | Retrieval evaluation | Relevance of retrieved records for labelled questions; per-customer cap; workspace restriction | AIR-05 to AIR-07 |
| TST-10 | Assistant evaluation | Grounded-answer rate; correct-refusal rate; count accuracy | FR-AST-01 to FR-AST-06 |
| TST-11 | Security testing | Password storage, throttling, session handling, CSRF, output escaping, upload handling, secrets | SEC-01 to SEC-05, SEC-10 to SEC-12, SEC-17 to SEC-19 |
| TST-12 | Isolation testing | Cross-workspace attempts through interface, API, retrieval, assistant and exports | SEC-04, SEC-06, NFR-22 |
| TST-13 | Prompt-injection testing | Planted instructions in reviews, tickets and transcripts; check for tool misuse, external actions, disclosure, changed behaviour | SEC-07 to SEC-09, AGR-06 to AGR-11 |
| TST-14 | Privacy testing | PII detection recall on seeded data; inspection of model inputs and logs | DR-28 to DR-30, NFR-21, SEC-17 |
| TST-15 | Model integration testing | Timeouts, malformed output, retries, model unavailable | AIR-09 to AIR-12, AIR-22 |
| TST-16 | Jira and MCP testing | Against a test Jira site: preview, approval, creation, rejection, duplicate prevention, partial failure, integration disabled | AGR-12 to AGR-25 |
| TST-17 | Usability and accessibility testing | First-use task completion; one-interaction evidence access; states; keyboard and contrast | NFR-16 to NFR-20 |
| TST-18 | Performance and resource testing | Timings on the reference workspace; memory and GPU use during the demo | NFR-01 to NFR-07 |
| TST-19 | Reliability testing | Interrupted jobs, restart, failure isolation | NFR-08 to NFR-10, DR-36 to DR-40 |
| TST-20 | End-to-end testing | UC-12 run as the demo script | Section 10 |
| TST-21 | Audit testing | Required events recorded; entries cannot be edited | SEC-14 to SEC-16, NFR-23 |
| TST-22 | Regression | All suites re-run at each milestone and after changes to prompts, thresholds or models | NFR-12, NFR-15, AIR-20 |

### 11.3 Targets

| Metric | Target | Justification |
|---|---|---|
| Citation validity | 100% | Deterministic check; invalid citations are blocked before display |
| Numeric accuracy in generated text | 100% | Numbers are filled from stored data and checked |
| Cross-workspace exposures | 0 | Isolation is a core brief requirement |
| Seeded PII reaching the model | 0 | Masking runs before every model call |
| Import reconciliation | 100% | Deterministic accounting |
| Classification macro-F1, theme agreement, aggregation precision and recall, claim-support rate, assistant grounded-answer and refusal rates, rubric scores, rank correlation | Set after the first baseline (end of Milestone 2), as baseline plus an improvement goal, agreed with the mentor | No credible target can be stated before measuring on our data |

---

## 12. Scope and Priorities

### 12.1 Delivery tiers per module

| Module | Must (minimum end-to-end) | Should (depth) | Could and Future |
|---|---|---|---|
| 1 Auth and workspaces | Register, sign in and out, workspaces, isolation | Session timeout, members, roles, switching | Delete workspace; password reset (Future) |
| 2 Ingestion | Upload, source types, mapping, background import, report, evidence IDs | Retry, history, raw-versus-processed view | Paste text, saved mappings, import removal |
| 3 Analytics | Metric import, releases | Trends, links, conflicts | Suggested links |
| 4 Themes | Category, sentiment, themes, evidence, statistics, vocal-customer flag | Unassigned group, review list, rename and merge, sarcasm flag | Split and move, preserve corrections |
| 5 Aggregation | Identify, group, count | Canonical ask, edit groups | Low-confidence flags, volume over time |
| 6 Prioritisation | Opportunities, RICE, visible formula, input origins, recompute | ICE, AI rationale, A-versus-B explanation, impact | Confidence indicator, decisions |
| 7 PRD and stories | PRD, stories, acceptance criteria, citations, verification status, draft status | Insufficient-evidence statements, versions, export, Jira creation | Analytics context; Jira updates (Future) |
| 8 Roadmap | Proposal by score and effort, effort input, lanes | Dependencies, reorder, evidence links | Capacity assumption |
| 9 Assistant | Questions, workspace-only answers, citations, computed counts, refusals | Date and release bounds, tool transparency | Conflicts, history, feedback marks |
| 10 Dashboard | Pain points, drill-down, executive summary | Trends, top opportunities, filters, freshness | Conflicts panel, export |

Requirement counts by priority are given in Appendix A.

### 12.2 Out of scope

| Item | Reason |
|---|---|
| Autonomous product decisions or autonomous external actions | The PM stays in charge (SRC-1 §1) |
| Real company data | Not available (A-01) |
| Technology, model and framework selection | Architecture document (C-03) |
| Live connectors to review sites, help desks or analytics products | File import only (A-04); listed as a future enhancement |
| Audio or video transcription | Transcripts are accepted as text |
| Billing, subscriptions, mobile applications | Not in the brief |
| Training or fine-tuning models | Not needed for scope; may be considered after evaluation |

### 12.3 Limitations

- AI results can be wrong. The system exposes and limits errors through evidence, verification and review, but cannot remove them.
- Local models on the reference laptop are smaller than cloud models; output quality is measured, not assumed (Section 11).
- Insight quality depends on the volume and quality of imported data.
- Effort and impact values are estimates and are labelled as such.

---

## 13. Requirements Traceability

### 13.1 Modules

| Module (SRC-1 §2) | Requirements | Acceptance criteria | Use cases | Verification |
|---|---|---|---|---|
| 1 User Authentication and Workspace Management | FR-AUTH-01 to FR-AUTH-12; SEC-01 to SEC-06 | AC-AUTH-01 to AC-AUTH-04 | UC-01 | TST-02, TST-03, TST-11, TST-12 |
| 2 Customer Feedback and Support Ticket Ingestion | FR-ING-01 to FR-ING-12; DR-01 to DR-40 | AC-ING-01 to AC-ING-04 | UC-02 | TST-01, TST-04, TST-14, TST-19 |
| 3 Product Analytics Data Integration | FR-ANA-01 to FR-ANA-06; DR-41 | AC-ANA-01 to AC-ANA-03 | UC-03 | TST-01, TST-04 |
| 4 Feedback Classification and Theme Extraction | FR-THM-01 to FR-THM-12; AIR-01 to AIR-04 | AC-THM-01 to AC-THM-04 | UC-04, UC-05 | TST-05 |
| 5 Feature Request Aggregation | FR-AGG-01 to FR-AGG-07 | AC-AGG-01, AC-AGG-02 | UC-05 | TST-06 |
| 6 AI-Based Prioritization and Impact Analysis | FR-PRI-01 to FR-PRI-11; AIR-08 | AC-PRI-01 to AC-PRI-04 | UC-06 | TST-07 |
| 7 PRD and User Story Generation | FR-DOC-01 to FR-DOC-12; AIR-13 to AIR-19; AGR-12 to AGR-25; SEC-13 | AC-DOC-01 to AC-DOC-05 | UC-07, UC-08 | TST-08, TST-16 |
| 8 Roadmap Planning and Visualization | FR-RMP-01 to FR-RMP-07 | AC-RMP-01 to AC-RMP-03 | UC-10 | TST-01 |
| 9 Conversational Product Intelligence Assistant | FR-AST-01 to FR-AST-10; AIR-05 to AIR-07; AGR-01 to AGR-11; SEC-07 to SEC-09 | AC-AST-01 to AC-AST-04 | UC-09 | TST-09, TST-10, TST-13 |
| 10 Reporting and Insights Dashboard | FR-DSH-01 to FR-DSH-09 | AC-DSH-01 to AC-DSH-03 | UC-05, UC-11 | TST-01, TST-08 |

Individual test case IDs per requirement are assigned in the test plan (NFR-13).

### 13.2 Mentor expectations (SRC-2)

| ID | Expectation | Addressed in |
|---|---|---|
| ME-01 | Understand requirements before design | This document; Section 2.2 workflow |
| ME-02 | Entry point and what happens at each stage | Sections 2.1, 2.2, 4.2, 5.8; architecture document |
| ME-03 | Which component connects to which resource or system | Section 2.1; IR-04, IR-08, IR-10, IR-11; architecture document |
| ME-04 | How LLM calls happen and what happens after each | Sections 5.8, 5.9; AIR-09 to AIR-12 |
| ME-05 | Creating user stories using MCP to connect with Jira | Section 6.4; AGR-12 to AGR-25; UC-08 |
| ME-06 | Design the architecture and database | Section 4.14; physical design in the architecture document |
| ME-07 | Data pipeline from multiple sources (feedback, tickets, requests, analytics, transcripts) | Section 4; DR-01 to DR-41 |
| ME-08 | Normalise and organise data; noise filtering; three or four types of normalisation | Sections 4.3, 4.6, 4.8 |
| ME-09 | Mechanism for importing feedback and tickets; cleaning, preprocessing, categorisation | FR-ING-01 to FR-ING-12; DR-05 to DR-27 |
| ME-10 | AI agent architecture | Section 6; architecture document |
| ME-11 | SRS as first deliverable, in Markdown | This document (C-08) |

### 13.3 The brief's seven design questions (SRC-1 §6)

| Question | Answer in requirements |
|---|---|
| 1 Real theme versus one vocal customer | Unique-customer counts (FR-THM-05, FR-AGG-04, DR-23); vocal-customer flag (FR-THM-06, A-11); per-customer evidence cap (AIR-07); minimum distinct customers for claims (A-13); duplicates not counted (DR-18) |
| 2 Verifying "users want dark mode"; preventing invented evidence | Claims with citations (FR-DOC-03); verification of IDs, quotations, numbers and support (AIR-14 to AIR-17); approval gate (SEC-13); citation and numeric targets (NFR-26, NFR-27) |
| 3 Feedback and analytics disagree | Both signals shown, conflict flagged, no automatic choice (FR-ANA-05); confidence lowered (FR-PRI-10); mentioned in answers and PRDs (FR-AST-08, FR-DOC-12) |
| 4 Accuracy of theme extraction; ground truth | Hand-labelled set with agreement measured (11.1); TST-05; reproducibility (AIR-04); targets from baseline (11.3) |
| 5 PM disagrees with the ranking | Any input or weight editable; recompute and show movement (FR-PRI-04, FR-PRI-05); explanation (FR-PRI-08) |
| 6 Judging a generated PRD | Rubric by three reviewers plus automatic checks (TST-08); specificity through citations (AC-DOC-03) |
| 7 Duplicates, spam, sarcasm, multilingual, personal information | DR-16 to DR-18; DR-13; FR-THM-10; DR-24, DR-25; DR-28 to DR-30 |

### 13.4 Success and evaluation criteria (SRC-1 §7)

| Criterion | Requirements | Verification |
|---|---|---|
| SC-01 Load feedback and product data | FR-ING-01 to FR-ING-06, FR-ANA-01 | TST-01, TST-04 |
| SC-02 Pain points and trends with evidence | FR-THM-03 to FR-THM-05, FR-DSH-01, FR-DSH-02 | TST-05 |
| SC-03 Ranked opportunities with reasons | FR-PRI-01 to FR-PRI-05 | TST-07 |
| SC-04 PRD, stories, acceptance criteria | FR-DOC-01 to FR-DOC-08 | TST-08 |
| SC-05 Roadmap and executive summary | FR-RMP-01 to FR-RMP-03, FR-DSH-03 | TST-01, TST-08 |
| SC-06 Grounded follow-up questions | FR-AST-01 to FR-AST-05 | TST-10 |
| Evaluation: insight accuracy | AIR-01 to AIR-04, NFR-28 | TST-05, TST-06 |
| Evaluation: document quality | FR-DOC-01 to FR-DOC-12, AIR-13 to AIR-17 | TST-08 |
| Evaluation: prioritisation and roadmap | FR-PRI-01 to FR-PRI-11, FR-RMP-01 to FR-RMP-07 | TST-07 |
| Evaluation: usability of dashboards and assistant | FR-DSH-01 to FR-DSH-09, FR-AST-01 to FR-AST-10, NFR-16 to NFR-20 | TST-10, TST-17 |
| Evaluation: completeness, documentation, testing, presentation | NFR-13, NFR-15, NFR-30, Section 11 | TST-20, TST-22 |

---

## 14. Open Items

### 14.1 Blocking mentor decisions

Only items the team cannot reasonably decide alone are listed here.

| ID | Question | Why it blocks | Proposed default if not answered |
|---|---|---|---|
| B-01 | Will datasets be provided, or should the team use public or synthetic data? | Determines labelling and demo data | Use a public review or support-ticket dataset (A-01) |
| B-02 | Is the team's Must/Should/Could split acceptable, given that all ten modules are present at Must level? | Sets scope for 40 hours | Section 12.1 |
| B-03 | Is Jira creation through MCP mandatory for the final demo, and who provides the Jira Cloud test site? | Integration needs an external account | Should priority; team creates a free Jira Cloud test site if permitted (A-25) |
| B-04 | Please confirm the advice to avoid LLM orchestration frameworks (C-07) and the local-first, zero-cost constraint (C-05, C-06) | These shape the architecture | Proceed as stated |
| B-05 | What exactly must Milestone 1 deliver beyond this SRS (design document, working ingestion)? | Defines Friday's definition of done | SRS, architecture document, working ingestion of one source |
| B-06 | Is a local demo on the team laptop acceptable for evaluation? | Hosting would change constraints | Local demo (OE-02) |

### 14.2 Team design decisions

These were left open in draft 0.1. They are design decisions, not requirements, and each is resolved in the architecture document.

| ID | Decision | Resolved in architecture section |
|---|---|---|
| T-01 | Application architecture and technology stack | 2, 6 |
| T-02 | Language model selection and benchmark procedure | 4 |
| T-03 | Embedding method | 4.5 |
| T-04 | Theme detection and request grouping method | 11.4 |
| T-05 | Near-duplicate method and starting threshold (A-10) | 10 |
| T-06 | Prompt templates and their versioning | 11.2 |
| T-07 | Scoring formulas and sequencing rule | 11.5 |
| T-08 | Physical database schema and normal form | 9 |
| T-09 | Agent workflow and tool list | 12 |
| T-10 | MCP server, authentication method and Jira field mapping | 12.4 |
| T-11 | Authentication and session mechanism | 13 |
| T-12 | Local development, deployment and resource management | 3, 17 |

Proposed default values are recorded once, as assumptions A-01 to A-25 in Section 2.6.

---

## Appendix A. Requirement Counts

| Group | Must | Should | Could | Future | Total |
|---|---|---|---|---|---|
| Functional (FR-) | 47 | 32 | 18 | 1 | 98 |
| Data (DR-) | 18 | 21 | 2 | 0 | 41 |
| AI behaviour (AIR-) | 11 | 12 | 2 | 0 | 25 |
| Agent and integration (AGR-) | 7 | 18 | 0 | 2 | 27 |
| Non-functional (NFR-) | 10 | 20 | 0 | 0 | 30 |
| Interfaces (IR-) | 5 | 6 | 0 | 0 | 11 |
| Security (SEC-) | 9 | 10 | 2 | 0 | 21 |
| **Total** | **107** | **119** | **24** | **3** | **253** |

Must requirements are 42% of the total (draft 0.1: 66% Essential). Every module has Must requirements, so the minimum product covers all ten modules and success criteria SC-01 to SC-06. Draft 0.1 had 302 requirements, 91 of which combined several obligations; this version has 253 requirements, each with a single "shall".

*End of document.*
