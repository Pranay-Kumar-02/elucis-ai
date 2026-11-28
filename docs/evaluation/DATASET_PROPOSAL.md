# Evaluation dataset proposal (milestone 2, step 8)

Status: **dataset A approved by the owner on 28 Nov 2026** and downloaded to `data/evaluation/zenodo-15852840/` (git-ignored): `test_1594.csv` (SHA-256 `44e2bcda…3c8f`) and `val_1595.csv` (`58936888…c398`). The test split is used only for the accuracy report and the validation split only for the model benchmark. No labels are invented: every number in the accuracy report must come from labels written by the dataset's authors or by our team on the labelling sheet.

## What we need to measure

| Measure | Needs |
|---|---|
| Issue detection: precision, recall, F1 | Records with a human label saying whether each is an issue (bug, usability or performance problem) |
| Feature-request detection | Records with a human label saying whether each is a feature request |
| Feature grouping: pairwise precision, recall, F1 and purity | Feature-request records with a human label naming the group (the same ask) |

## Candidates checked (27 Nov 2026)

| Dataset | Licence (as stated on the page) | Content | Fit | Concerns |
|---|---|---|---|---|
| **A. Annotated Dataset for User Review Classification in the Privacy Domain for Social Media Applications**, Farah, Kabir, Ahmed (Islamic University of Technology), Zenodo, DOI [10.5281/zenodo.15852840](https://zenodo.org/records/15852840), v1, 10 Jul 2025 | **CC BY 4.0** ("unrestricted use, distribution, and reproduction … provided the original authors are appropriately credited") | 16,000 Google Play reviews of seven social apps, hand-labelled by two annotators (Cohen's kappa 0.87): feature request 3,627, bug report 4,221, irrelevant 8,152. CSV files with the original text and the label; train, validation and test splits | Bug-report and feature-request labels match our issue-detection and request-detection measures directly | Only privacy-related requests and bugs are labelled as such; other complaints count as "irrelevant", so our "issue" class is broader than theirs (see mapping below). No group labels for requests |
| B. A dataset of mobile application reviews for classifying reviews into maintenance tasks, Al-hawari, Mendeley Data, DOI [10.17632/5fk732vkwr.2](https://data.mendeley.com/datasets/5fk732vkwr), v2, 27 Sep 2019 | CC BY 4.0 | Two sets: Pan et al. (1,390 reviews: feature request, problem discovery, information giving or seeking) and Maalej et al. (3,691 reviews: feature request, bug report, user experience, rating) | Broad issue and request labels across many apps | It republishes data collected by other research groups (Panichella et al. and Maalej et al.), so we would need to confirm those groups allow redistribution. Not recommended until confirmed |
| C. A Dataset of End-User Reviews from the Apple App Store for Software Evolution Research, Khan, Mendeley Data, DOI [10.17632/75g52mjmpf.4](https://data.mendeley.com/datasets/75g52mjmpf), v4, 27 Oct 2025 | CC BY 4.0 | 158,910 App Store reviews from 84 apps with star ratings | Realistic volume for performance and trend tests | **No labels**: usable only after our team labels a sample on the labelling sheet |

## Recommendation

1. **Use dataset A's test split (1,594 or 1,595 records, as published) for issue and request detection.** Mapping, fixed before we look at any results:
   - their `bug report` → our issue (positive class for issue detection);
   - their `feature request` → our `feature_request`;
   - their `irrelevant` → not an issue and not a request **for the privacy question they labelled**.

   Because their "irrelevant" class can contain non-privacy bugs, issue-detection precision on this set is a **lower bound**. The report must say so, or our team relabels a sample of "irrelevant" records with the sheet.
2. **For grouping, label our own sample.** No candidate has group labels. The team takes 150–300 feature-request records from dataset A (or C), and two people assign each to a request group with the labelling sheet. Disagreements are resolved and recorded in the `notes` column.
3. Credit the authors in `docs/evaluation/ACCURACY_REPORT.md` and in the README, as CC BY 4.0 requires.

## How the data is used

- It is imported like any customer file, through API-14 and API-15, into a separate workspace ("Evaluation"). It never sits in a product workspace.
- The raw files stay in `data/` (git-ignored); they are not committed. The repository keeps only the evaluation script, the empty labelling sheet and the report.
- The texts are public app-store reviews and may contain names. They go through the same PII masking as any import before any model sees them.

## What we found in the data (28 Nov 2026, F-09)

- The "Review" column is lower-cased and partly normalised by the authors.
- Some test records read as machine-written (fluent feature descriptions and policy paragraphs), although the page describes augmentation for the training set only.
- Some labels are debatable for our purpose: for example "messages are not reaching…" is labelled privacy-irrelevant, although it is a (non-privacy) bug. This is exactly why label 2 is left unlabelled in our evaluation.
- The data has no record IDs, dates or customer IDs: `backend/scripts/prepare_zenodo.py` numbers the rows (`zen-test-00001`…), so trends and customer counts are not exercised by this set.

The numbers in ACCURACY_REPORT.md are therefore **indicative**: a public, licensed, human-labelled benchmark, not our customers' data. The team's own labelled sample (LABELLING_GUIDE.md) is the next step for grouping accuracy and for a representative issue-detection figure.
