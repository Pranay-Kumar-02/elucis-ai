# Accuracy report (milestone 2 step 8)

Generated 28 Nov 2026 14:50 UTC by `scripts/evaluate.py` from the current analysis run of workspace "Evaluation" (run `7ade0796-aa5d-4206-b3fb-4ea7896ab99c`, finished 28 Nov 2026 14:48 UTC, chat model `qwen3:4b`, embedding model `qwen3-embedding:0.6b`).

**Labels:** Farah, L., Kabir, M. R., Ahmed, S. (2025). *Annotated Dataset for User Review Classification in the Privacy Domain for Social Media Applications* (v1). Zenodo. https://doi.org/10.5281/zenodo.15852840. Licence CC BY 4.0. Labels by the dataset authors (two annotators, Cohen's kappa 0.87 as published).

Scope of these labels (F-09): only privacy-related bug reports and feature requests are labelled; the scores use the records labelled one of those two, where the label is definite. The texts are lower-cased by the authors, some read as machine-written, and the set has no customer IDs or dates. Treat the figures as an indicative public benchmark, not as accuracy on our customers' feedback.

Label rows: 1594. Found in the workspace: 1594. Not classified in the run (excluded before analysis or failed): 9 (noise 9). Those records are left out of every score below.

## Detection

| Measure | Records | TP | FP | FN | TN | Precision | Recall | F1 | Note |
|---|---|---|---|---|---|---|---|---|---|
| Issue detection (bug, usability or performance) | 778 | 389 | 68 | 31 | 290 | 0.85 | 0.93 | 0.89 |  |
| Feature-request detection (in a request group) | 778 | 280 | 12 | 78 | 408 | 0.96 | 0.78 | 0.86 |  |

## Per category (CP-02)

| Category | Labelled as this | Precision | Recall | F1 |
|---|---|---|---|---|
| `bug_report` | 420 | 0.92 | 0.77 | 0.84 |
| `feature_request` | 358 | 0.97 | 0.78 | 0.86 |

## Coverage of themes and request groups (from the run, no labels needed)

| Measure | Value |
|---|---|
| Themes | 8 |
| Classified records in a theme | 294 of 1585 (19%) |
| Request groups | 265 for 379 request records |

D03 (EXP-06) asks for at least 70% of records in a theme; many groups with one or two records mean the grouping threshold is too strict (F-08, F-12).

## Feature grouping

**Not measured:** these labels have no `request_group`. Grouping accuracy needs the team's labelling sheet (LABELLING_GUIDE.md); no number is estimated.

## Records without a label (description only, not scored)

How the model labelled the records the labels leave open:

`bug_report` 260, `praise` 187, `other` 124, `usability_issue` 82, `feature_request` 81, `performance_issue` 55, `question` 18.
