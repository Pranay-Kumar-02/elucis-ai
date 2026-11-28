# Labelling guide (accuracy evaluation, milestone 2 step 8)

The sheet `labelling_sheet.csv` holds the human labels that `backend/scripts/evaluate.py` compares with Elucis AI's output. **Never fill a label you are unsure of: leave it empty and write why in `notes`.** An empty label is left out of the scores; a guessed one makes them meaningless.

## Columns

| Column | What to write | Allowed values |
|---|---|---|
| `record_id` | The record's ID in the source file (the column mapped as "Record ID" when importing). It is how the script finds Elucis AI's output for the record | Copied, never invented |
| `text` | The feedback text, copied from the source file (for the labeller's convenience; the script ignores it) | |
| `is_issue` | Does the customer report a problem with the product? | `yes`, `no`, or empty |
| `category` | The one category that fits best | `bug_report`, `feature_request`, `usability_issue`, `performance_issue`, `praise`, `question`, `other`, or empty |
| `is_feature_request` | Does the customer ask for something new or changed? | `yes`, `no`, or empty |
| `request_group` | Only for feature requests: a short name for *what* is asked. Two records asking for the same thing get exactly the same name | Free text, e.g. `dark-mode`, `export-excel` |
| `labeller` | Your initials | |
| `notes` | Anything unusual: sarcasm, two topics in one record, unsure | |

## Rules

- **Issue** = a bug (something broken or wrong), a usability problem (works but confusing or hard), or a performance problem (slow, freezing, battery). Feature requests, praise and questions are not issues, unless the text also reports a problem.
- If a record both reports a problem and asks for something, the category is the problem (same rule the model uses), and `is_feature_request` is still `yes`.
- `request_group`: decide groups by meaning, not wording ("night mode" and "dark theme" are the same group). Keep a shared list of group names in the team chat so everyone uses the same name.
- Label the text as written; don't guess what the customer meant beyond it.

## Process

1. Pick the records: for issue detection, the published test split of the approved dataset (see `DATASET_PROPOSAL.md`); for grouping, 150 to 300 records the model or the dataset marks as feature requests.
2. Two people label the same records independently, each in their own copy of the sheet.
3. Compare the two copies. Agreement is reported (Cohen's kappa) together with the accuracy figures. Disagreements are settled by discussion; the settled label goes into the final sheet and the reason into `notes`.
4. Save the final sheet as `data/evaluation/labels.csv` (git-ignored, like all data files), import the same records into an "Evaluation" workspace, run an analysis, then run the script:

```powershell
cd backend
uv run python scripts/evaluate.py --workspace "Evaluation" --labels ..\data\evaluation\labels.csv
```

The script writes `docs/evaluation/ACCURACY_REPORT.md`. It never fills in a number for which there are no labels.
