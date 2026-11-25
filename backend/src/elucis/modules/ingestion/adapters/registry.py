"""Catalogue of source adapters (D01 section 3.1).

Only ``file`` is implemented. The connectors below are *designed* in D01: each needs a vendor
account, credentials and mentor approval (AR-05) before any code is written, so they are
reported honestly as ``designed`` and ``get_adapter_class`` refuses them.
"""

from __future__ import annotations

from elucis.core.errors import NotFoundError, ValidationFailedError
from elucis.modules.ingestion.adapters.base import AdapterStatus, SourceInfo
from elucis.modules.ingestion.adapters.file_adapter import FILE_SOURCE, FileAdapter

_DESIGNED = "Designed only. Needs vendor account, credentials and mentor approval (AR-05)."

CATALOGUE: tuple[SourceInfo, ...] = (
    FILE_SOURCE,
    SourceInfo(
        "google_play",
        "Google Play reviews",
        AdapterStatus.DESIGNED,
        auth="OAuth / service account",
        notes=_DESIGNED + " API returns the last 7 days.",
    ),
    SourceInfo(
        "app_store",
        "Apple App Store reviews",
        AdapterStatus.DESIGNED,
        auth="App Store Connect API key (JWT)",
        notes=_DESIGNED,
    ),
    SourceInfo(
        "zendesk",
        "Zendesk tickets",
        AdapterStatus.DESIGNED,
        auth="Bearer token (admin)",
        notes=_DESIGNED + " Incremental cursor export.",
    ),
    SourceInfo(
        "mixpanel",
        "Mixpanel raw events",
        AdapterStatus.DESIGNED,
        auth="Service account",
        notes=_DESIGNED + " Events must be aggregated to metrics.",
    ),
    SourceInfo(
        "amplitude",
        "Amplitude export",
        AdapterStatus.DESIGNED,
        auth="API key and secret",
        notes=_DESIGNED,
    ),
    SourceInfo(
        "ms_graph_transcripts",
        "Microsoft Teams transcripts",
        AdapterStatus.DESIGNED,
        auth="Microsoft Graph (OnlineMeetingTranscript.Read.All)",
        notes=_DESIGNED,
    ),
)

_IMPLEMENTED: dict[str, type[FileAdapter]] = {"file": FileAdapter}


def list_sources() -> tuple[SourceInfo, ...]:
    return CATALOGUE


def get_adapter_class(kind: str) -> type[FileAdapter]:
    if kind in _IMPLEMENTED:
        return _IMPLEMENTED[kind]
    if any(s.kind == kind for s in CATALOGUE):
        raise ValidationFailedError(
            f"The {kind!r} connector is designed but not implemented.",
            details=[{"field": "kind", "issue": "not_implemented"}],
        )
    raise NotFoundError(f"Unknown source kind {kind!r}.")
