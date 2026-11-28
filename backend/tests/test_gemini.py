"""The optional Gemini backup (IMP-38): the HTTP client against a mocked transport, and the
fallback rules of ``run_task``. No call ever reaches Google from the test suite."""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx2
import pytest
from pydantic import BaseModel

from elucis.ai.gemini import GeminiClient, inline_refs
from elucis.ai.ollama import CallStats, InvalidModelOutputError
from elucis.ai.prompts import CP02, Cp02Out
from elucis.core.errors import ModelUnavailableError
from elucis.modules.analysis.tasks import TaskContext, run_task
from tests.conftest import make_settings

KEY = "test-key-not-real"
OK_REPLY = {
    "candidates": [
        {
            "content": {
                "role": "model",
                "parts": [
                    {
                        "text": json.dumps(
                            {
                                "items": [
                                    {"key": "r1", "category": "bug_report", "sentiment": "negative"}
                                ]
                            }
                        )
                    }
                ],
            },
            "finishReason": "STOP",
        }
    ],
    "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 18, "totalTokenCount": 138},
}
MESSAGES = [
    {"role": "system", "content": "You label feedback."},
    {
        "role": "user",
        "content": '<customer_feedback id="r1">Checkout fails, mail [EMAIL]</customer_feedback>',
    },
]


def _client(handler: Any) -> GeminiClient:
    settings = make_settings(gemini_api_key=KEY)
    return GeminiClient(settings, transport=httpx2.MockTransport(handler))


def test_request_shape_and_reply_parsing() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=OK_REPLY)

    with _client(handler) as client:
        out, stats = client.chat_json(
            MESSAGES, Cp02Out, model="gemini-test", num_predict=600, think=False
        )
    assert (
        seen["url"]
        == "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
    )
    assert seen["key"] == KEY and KEY not in seen["url"]  # never in the URL, so never in logs
    body = seen["body"]
    assert body["systemInstruction"] == {"parts": [{"text": "You label feedback."}]}
    assert body["contents"] == [{"role": "user", "parts": [{"text": MESSAGES[1]["content"]}]}]
    config = body["generationConfig"]
    assert (config["responseMimeType"], config["temperature"], config["maxOutputTokens"]) == (
        "application/json",
        0.0,
        600,
    )
    assert "$ref" not in json.dumps(config["responseJsonSchema"])
    assert "$defs" not in config["responseJsonSchema"]
    assert out.items[0].category == "bug_report"
    assert (stats.model, stats.prompt_tokens, stats.output_tokens) == (
        "gemini:gemini-test",
        120,
        18,
    )


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx2.Response(429, json={"error": {"message": "quota"}}), ModelUnavailableError),
        (httpx2.Response(503), ModelUnavailableError),
        (httpx2.Response(400, json={"error": {"message": "bad schema"}}), InvalidModelOutputError),
        (
            httpx2.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}),
            InvalidModelOutputError,
        ),
        (
            httpx2.Response(
                200,
                json={
                    "candidates": [
                        {"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{"}]}}
                    ]
                },
            ),
            InvalidModelOutputError,
        ),
        (
            httpx2.Response(
                200,
                json={
                    "candidates": [
                        {"finishReason": "STOP", "content": {"parts": [{"text": "not json"}]}}
                    ]
                },
            ),
            InvalidModelOutputError,
        ),
    ],
)
def test_errors_map_to_the_gateway_errors(
    response: httpx2.Response, error: type[Exception]
) -> None:
    with _client(lambda _r: response) as client, pytest.raises(error):
        client.chat_json(MESSAGES, Cp02Out)


def test_timeouts_and_network_errors_mean_unavailable() -> None:
    def timeout(_r: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("slow")

    with _client(timeout) as client, pytest.raises(ModelUnavailableError):
        client.chat_json(MESSAGES, Cp02Out)


def test_no_key_no_client() -> None:
    with pytest.raises(ModelUnavailableError):
        GeminiClient(make_settings(gemini_api_key=""))
    assert make_settings().gemini_configured is False


def test_inline_refs_resolves_nested_models() -> None:
    schema = inline_refs(Cp02Out.model_json_schema())
    item = schema["properties"]["items"]["items"]
    assert set(item["properties"]) == {"key", "category", "sentiment"}
    assert "title" not in item


# ---------------------------------------------------------------- run_task fallback rules
class Scripted:
    """A chat gateway that answers from a script: an exception class, or a reply."""

    def __init__(self, *script: Any) -> None:
        self.script, self.calls = list(script), 0

    def chat_json(self, messages: list[dict[str, str]], schema: type[BaseModel], **_: Any) -> Any:
        self.calls += 1
        step = self.script.pop(0) if self.script else self.script_last
        self.script_last = step
        if isinstance(step, type) and issubclass(step, Exception):
            raise step("scripted")
        return schema.model_validate(step), CallStats("m", 1, 1, None, None, None, 1.0)

    def close(self) -> None:
        pass

    script_last: Any = None


GOOD = {"items": [{"key": "r1", "category": "praise", "sentiment": "positive"}]}


def _tc(local: Any, backup: Any = None) -> TaskContext:
    return TaskContext(
        local,
        uuid.uuid4(),
        None,
        "qwen3:4b",
        {"CP-02": uuid.uuid4()},
        fallback=backup,
        fallback_model="gemini-test" if backup else None,
    )


def _run(tc: TaskContext) -> Any:
    return run_task(tc, CP02, "content", Cp02Out, None, sleep=lambda _s: None)


def test_without_a_backup_nothing_changes() -> None:
    tc = _tc(Scripted(InvalidModelOutputError))
    assert _run(tc) is None
    assert {c["provider"] for c in tc.pending} == {"ollama"}
    with pytest.raises(ModelUnavailableError):
        _run(_tc(Scripted(ModelUnavailableError)))


def test_backup_answers_when_the_local_output_stays_invalid() -> None:
    local, backup = Scripted(InvalidModelOutputError), Scripted(GOOD)
    tc = _tc(local, backup)
    out = _run(tc)
    assert out is not None and out.items[0].category == "praise"
    assert local.calls == 3 and backup.calls == 1  # 1 + 2 local retries, then the backup
    assert [c["provider"] for c in tc.pending] == ["ollama"] * 3 + ["gemini"]
    assert tc.pending[-1]["model"] == "gemini-test" and tc.pending[-1]["outcome"] == "ok"


def test_backup_answers_when_the_local_runtime_is_down() -> None:
    tc = _tc(Scripted(ModelUnavailableError), Scripted(GOOD))
    assert _run(tc) is not None


def test_both_failing_falls_through() -> None:
    assert _run(_tc(Scripted(InvalidModelOutputError), Scripted(InvalidModelOutputError))) is None
    assert _run(_tc(Scripted(InvalidModelOutputError), Scripted(ModelUnavailableError))) is None
    with pytest.raises(ModelUnavailableError):  # both down: the job retries later
        _run(_tc(Scripted(ModelUnavailableError), Scripted(ModelUnavailableError)))
