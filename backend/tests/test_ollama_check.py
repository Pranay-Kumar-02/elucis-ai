"""The model smoke-test CLI against a simulated Ollama server (no network, no GPU).

This proves the CLI's logic and report format. The real measurements come from running it
on the laptop (scripts/windows/40-setup-ollama.ps1).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx2
import pytest

from elucis.ai import check
from elucis.ai.ollama import OllamaClient

DIM = 1024


def _vector(seed: float) -> list[float]:
    return [seed] + [0.01] * (DIM - 1)


def _fake_ollama(models: list[str]) -> httpx2.MockTransport:
    def handler(req: httpx2.Request) -> httpx2.Response:
        path = req.url.path
        if path == "/api/version":
            return httpx2.Response(200, json={"version": "0.40.4"})
        if path == "/api/tags":
            return httpx2.Response(
                200,
                json={
                    "models": [
                        {
                            "name": m,
                            "size": 2_500_000_000,
                            "digest": "359d7dd4bcda" + "0" * 52,
                            "details": {"parameter_size": "4.0B", "quantization_level": "Q4_K_M"},
                        }
                        for m in models
                    ]
                },
            )
        if path == "/api/chat":
            body = json.loads(req.content)
            content = (
                json.dumps({"category": "bug_report", "sentiment": "negative", "summary": "crash"})
                if "format" in body
                else "READY"
            )
            return httpx2.Response(
                200,
                json={
                    "model": body["model"],
                    "message": {"role": "assistant", "content": content},
                    "eval_count": 12,
                    "eval_duration": 300_000_000,
                    "total_duration": 600_000_000,
                    "load_duration": 50_000_000,
                },
            )
        if path == "/api/embed":
            texts = json.loads(req.content)["input"]
            seeds = [1.0, 0.98, -1.0][: len(texts)]
            return httpx2.Response(200, json={"embeddings": [_vector(s) for s in seeds]})
        if path == "/api/ps":
            return httpx2.Response(
                200,
                json={
                    "models": [
                        {"name": "qwen3:4b", "size": 3_000_000_000, "size_vram": 3_000_000_000}
                    ]
                },
            )
        return httpx2.Response(404, json={"error": "unknown"})

    return httpx2.MockTransport(handler)


@pytest.fixture
def fake_models(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    models = ["qwen3:4b", "qwen3-embedding:0.6b"]

    def factory(settings: Any = None, **_: Any) -> OllamaClient:
        return OllamaClient(settings, transport=_fake_ollama(models))

    monkeypatch.setattr(check, "OllamaClient", factory)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
    check.get_settings.cache_clear()
    yield models
    check.get_settings.cache_clear()


def test_full_check_passes_and_measures_dimension(fake_models: list[str], tmp_path: Path) -> None:
    out = tmp_path / "ollama.json"
    assert check.main(["--report", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    names = [c["name"] for c in report["checks"]]
    assert names == [
        "api_connectivity",
        "models_installed",
        "basic_generation",
        "json_structured_output",
        "embedding",
        "gpu_offload",
    ]
    assert report["ok"] is True
    assert report["measured_embedding_dimension"] == DIM
    embedding = report["checks"][4]
    assert embedding["matches_expected"] is True
    assert embedding["semantic_sanity"] is True
    assert report["checks"][3]["schema_valid_replies"] == 3
    assert report["checks"][5]["loaded"][0]["gpu_share"] == 1.0


def test_quick_check_skips_json_test(fake_models: list[str], tmp_path: Path) -> None:
    out = tmp_path / "quick.json"
    assert check.main(["--quick", "--report", str(out)]) == 0
    names = [c["name"] for c in json.loads(out.read_text(encoding="utf-8"))["checks"]]
    assert "json_structured_output" not in names


def test_missing_model_fails_the_report(fake_models: list[str], tmp_path: Path) -> None:
    fake_models.remove("qwen3:4b")
    out = tmp_path / "missing.json"
    assert check.main(["--quick", "--report", str(out)]) == 1
    report = json.loads(out.read_text(encoding="utf-8"))
    installed = next(c for c in report["checks"] if c["name"] == "models_installed")
    assert installed["ok"] is False
    assert installed["models"]["qwen3:4b"] is None


def test_unreachable_server_is_recorded_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")
    check.get_settings.cache_clear()
    try:
        out = tmp_path / "down.json"
        assert check.main(["--quick", "--report", str(out)]) == 1
    finally:
        check.get_settings.cache_clear()
    first = json.loads(out.read_text(encoding="utf-8"))["checks"][0]
    assert first["name"] == "api_connectivity"
    assert first["ok"] is False
    assert first["error"] == "ModelUnavailableError"
