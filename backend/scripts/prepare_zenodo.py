"""Prepare the approved evaluation dataset (docs/evaluation/DATASET_PROPOSAL.md) for import.

Source: Farah, Kabir, Ahmed, "Annotated Dataset for User Review Classification in the Privacy
Domain for Social Media Applications", Zenodo, DOI 10.5281/zenodo.15852840, CC BY 4.0.
Labels: 0 = privacy feature request, 1 = privacy bug report, 2 = privacy-irrelevant.

Writes, next to the downloaded split (all under the git-ignored ``data/``):

* ``<split>-import.csv``: ``record_id,review`` to upload in an "Evaluation" workspace
  (map Feedback text = review, Record ID = record_id);
* ``<split>-labels.csv``: the labelling-sheet format (docs/evaluation/labelling_sheet.csv)
  derived from the authors' labels. Label 2 is left *unlabelled* for issue and request
  detection, because "privacy-irrelevant" says nothing about other bugs or requests.

The original "Review" text is used (not the authors' "Processed" column), so the texts go
through our own cleaning and PII masking like any customer file. Nothing is invented: every
label comes from the dataset; rows are only numbered.

Usage (from backend/)::

    uv run python scripts/prepare_zenodo.py ../data/evaluation/zenodo-15852840/test_1594.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

LABEL_COLUMNS = [
    "record_id",
    "text",
    "is_issue",
    "category",
    "is_feature_request",
    "request_group",
    "labeller",
    "notes",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("split", type=Path, help="a downloaded split, e.g. test_1594.csv")
    args = parser.parse_args()
    source: Path = args.split
    stem = source.stem.split("_")[0]  # "test" or "val"
    with source.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    imported = source.with_name(f"{stem}-import.csv")
    labels = source.with_name(f"{stem}-labels.csv")
    with (
        imported.open("w", encoding="utf-8", newline="") as out_import,
        labels.open("w", encoding="utf-8", newline="") as out_labels,
    ):
        w_import = csv.writer(out_import)
        w_import.writerow(["record_id", "review"])
        w_labels = csv.DictWriter(out_labels, fieldnames=LABEL_COLUMNS)
        w_labels.writeheader()
        for number, row in enumerate(rows, start=1):
            record_id = f"zen-{stem}-{number:05d}"
            text, label = row["Review"], row["Label"].strip()
            w_import.writerow([record_id, text])
            entry = dict.fromkeys(LABEL_COLUMNS, "")
            entry.update(record_id=record_id, text=text, labeller="dataset authors")
            if label == "1":
                entry.update(is_issue="yes", category="bug_report", is_feature_request="no")
            elif label == "0":
                entry.update(is_issue="no", category="feature_request", is_feature_request="yes")
            else:
                entry["notes"] = "privacy-irrelevant: not labelled for issues or requests"
            w_labels.writerow(entry)
    print(f"{len(rows)} rows -> {imported.name}, {labels.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
