"""Analysis runs (SVC-08 to SVC-12, coordinated as SVC-10): a deterministic orchestrator
that runs named, restartable steps inside the ``analysis`` worker job (ADR-06). No agent
or LLM framework: each model call is one explicit, schema-checked task."""
