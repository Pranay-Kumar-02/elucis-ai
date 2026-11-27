"""Live checks against the real local models (marker ``ollama``).

They use the Ollama URL from the project's settings and are reported as skipped, with the
reason, when Ollama or the model is not available. They never call a remote service.
"""

from __future__ import annotations

import math

import pytest

from elucis.ai.ollama import OllamaClient
from elucis.core.config import Settings, get_settings
from elucis.core.errors import ModelUnavailableError
from elucis.db.models._common import CURRENT_EMBEDDING_MODEL, EMBEDDING_DIMENSION
from elucis.modules.analysis.embedding import embed_texts

pytestmark = pytest.mark.ollama


@pytest.fixture(scope="module")
def live() -> Settings:
    get_settings.cache_clear()
    settings = get_settings()
    try:
        with OllamaClient(settings, timeout_s=5) as client:
            if not client.has_model(CURRENT_EMBEDDING_MODEL):
                pytest.skip(f"{CURRENT_EMBEDDING_MODEL} is not pulled in Ollama")
    except ModelUnavailableError:
        pytest.skip("Ollama is not running")
    return settings


def test_real_embeddings_are_1024_dimensional_normalised_and_meaningful(live: Settings) -> None:
    texts = [
        "Checkout spins forever after I tap Pay",
        "The payment screen hangs when I try to pay",
        "Please add a dark mode",
    ]
    with OllamaClient(live) as client:
        vectors = embed_texts(client, texts)
    assert all(len(v) == EMBEDDING_DIMENSION for v in vectors)
    assert all(abs(math.sqrt(sum(x * x for x in v)) - 1) < 1e-6 for v in vectors)

    def cos(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    # Two payment complaints are closer to each other than to an unrelated request.
    assert cos(vectors[0], vectors[1]) > cos(vectors[0], vectors[2])
