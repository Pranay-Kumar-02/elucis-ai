"""Preprocessing (SVC-05 to SVC-07) in the canonical order of D06 §1:

clean -> noise -> standardise (time, rating, version, customer key) -> PII masking ->
exact-duplicate detection. Language detection and spam are deferred (milestone 2 scope).

Every stage is a plain function on plain values, so each can be tested without a database.
``prepare.prepare_batch`` runs them for one batch inside the ingest job.
"""
