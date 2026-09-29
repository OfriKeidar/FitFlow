"""The OpenAI-compatible adapter (used for Gemini), and choosing a provider from the environment.

Same idea as test_chat.py: a scripted fake client returns real SDK response objects, and we check
what OUR code does with them. No network, no API key.
"""

import json

import httpx  # the OpenAI SDK's HTTP library, for building a fake error response
import openai
import pytest
from openai.types.chat import ChatCompletion

from fitflow.ai.agent import CoachAgent
from fitflow.ai.providers import (
    AnthropicProvider, LLMNotConfigured, OpenAICompatibleProvider, provider_from_env,
)
from fitflow.api.deps import get_agent
from fitflow.api.main import app
from tests.conftest import food_id


def completion(content: str | None = None, tool_calls: list | None = None, finish: str = "stop") -> ChatCompletion:
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = [
            {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}
            for call_id, name, arguments in tool_calls
        ]
        finish = "tool_calls"
    return ChatCompletion.model_validate({
        "id": "c1", "object": "chat.completion", "created": 0, "model": "gemini-test",
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
    })


class FakeOpenAI:
    """Stands in for openai.OpenAI(): scripted replies, and a record of every request."""

    def __init__(self):
        self.script: list = []
        self.requests: list[dict] = []
        self.chat = self
        self.completions = self

    def create(self, **request):
        self.requests.append(json.loads(json.dumps(request)))
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def gemini(client):
    fake = FakeOpenAI()
    app.dependency_overrides[get_agent] = lambda: CoachAgent(OpenAICompatibleProvider(fake, ["model-a", "model-b"], "gemini"))
    return fake


def chat(client, user, message):
    r = client.post("/chat", headers=user, json={"message": message})
    assert r.status_code == 200, r.text
    return r.json()


def test_food_flow_with_gemini(client, user, gemini):
    egg = food_id(client, "ביצה")
    gemini.script = [
        completion(tool_calls=[("c1", "search_foods", '{"queries": ["ביצה"]}')]),
        completion(tool_calls=[("c2", "propose_food_log", json.dumps({"items": [{"food_id": egg, "grams": 100}]}))]),
        completion("רשמתי 2 ביצים, מחכה לאישור שלך"),
    ]
    result = chat(client, user, "אכלתי 2 ביצים")

    [action] = result["actions"]
    client.post(f"/chat/actions/{action['id']}/confirm", headers=user)
    assert client.get("/today", headers=user).json()["eaten"]["kcal"] == 144


def test_request_format(client, user, gemini):
    gemini.script = [completion(tool_calls=[("c1", "search_foods", '{"queries": ["ביצה"]}')]), completion("ok")]
    chat(client, user, "ביצה")
    first, second = gemini.requests

    assert first["messages"][0]["role"] == "system" and "Dana" in first["messages"][0]["content"]
    assert first["tools"][0]["type"] == "function" and first["tools"][0]["function"]["name"] == "search_foods"
    # The tool result goes back as a "tool" message that references the call id.
    tool_message = second["messages"][-1]
    assert tool_message["role"] == "tool" and tool_message["tool_call_id"] == "c1"
    assert json.loads(tool_message["content"])["ביצה"][0]["name"] == "ביצה"


def test_unknown_fields_on_tool_calls_are_replayed(client, user, gemini):
    """Regression: Gemini rejects a tool call replayed without its extra_content.thought_signature."""
    call = completion(tool_calls=[("c1", "search_foods", '{"queries": ["ביצה"]}')])
    raw = call.model_dump()
    raw["choices"][0]["message"]["tool_calls"][0]["extra_content"] = {"google": {"thought_signature": "sig123"}}
    gemini.script = [ChatCompletion.model_validate(raw), completion("ok")]
    chat(client, user, "ביצה")

    replayed = gemini.requests[1]["messages"][-2]["tool_calls"][0]  # the assistant message before the tool result
    assert replayed["extra_content"] == {"google": {"thought_signature": "sig123"}}


def test_invalid_json_arguments_are_reported_to_the_model(client, user, gemini):
    gemini.script = [completion(tool_calls=[("c1", "search_foods", "{not json")]), completion("סליחה")]
    chat(client, user, "?")
    assert gemini.requests[1]["messages"][-1]["content"].startswith("Error:")


def test_history_is_kept_and_shown(client, user, gemini):
    gemini.script = [completion("שלום!"), completion("עדיין כאן")]
    chat(client, user, "היי")
    chat(client, user, "מה נשמע?")
    assert [m["role"] for m in gemini.requests[1]["messages"]] == ["system", "user", "assistant", "user"]
    assert [m["text"] for m in client.get("/chat/history", headers=user).json()] == ["היי", "שלום!", "מה נשמע?", "עדיין כאן"]


def test_rate_limited_model_falls_back_to_the_next(client, user, gemini):
    response = httpx.Response(429, request=httpx.Request("POST", "https://example.com"))
    gemini.script = [openai.RateLimitError("slow down", response=response, body=None), completion("שלום")]
    assert chat(client, user, "היי")["reply"] == "שלום"


def test_all_models_rate_limited_returns_429(client, user, gemini):
    response = httpx.Response(429, request=httpx.Request("POST", "https://example.com"))
    gemini.script = [openai.RateLimitError("slow down", response=response, body=None)] * 2
    assert client.post("/chat", headers=user, json={"message": "hi"}).status_code == 429


def test_overloaded_model_falls_back_to_the_next(client, user, gemini):
    response = httpx.Response(503, request=httpx.Request("POST", "https://example.com"))
    gemini.script = [openai.InternalServerError("overloaded", response=response, body=None), completion("שלום")]
    assert chat(client, user, "היי")["reply"] == "שלום"
    assert [r["model"] for r in gemini.requests] == ["model-a", "model-b"]


def test_failed_model_is_skipped_until_its_cooldown_ends():
    """Circuit breaker: after a 429, the next requests go straight to the next model for a minute."""
    now = [1000.0]
    fake = FakeOpenAI()
    provider = OpenAICompatibleProvider(fake, ["model-a", "model-b"], "gemini", clock=lambda: now[0])
    limited = openai.RateLimitError("slow down", response=httpx.Response(429, request=httpx.Request("POST", "https://x")), body=None)

    fake.script = [limited, completion("1")]
    provider.complete("system", "user", [{"role": "user", "content": "hi"}], [])
    fake.script = [completion("2")]
    provider.complete("system", "user", [{"role": "user", "content": "hi"}], [])
    now[0] += provider.RATE_LIMIT_COOLDOWN + 1  # the minute is over
    fake.script = [completion("3")]
    provider.complete("system", "user", [{"role": "user", "content": "hi"}], [])

    assert [r["model"] for r in fake.requests] == ["model-a", "model-b", "model-b", "model-a"]


def test_all_models_down_returns_503(client, user, gemini):
    response = httpx.Response(503, request=httpx.Request("POST", "https://example.com"))
    gemini.script = [openai.InternalServerError("overloaded", response=response, body=None)] * 2
    assert client.post("/chat", headers=user, json={"message": "hi"}).status_code == 503


def test_content_filter_is_a_refusal(client, user, gemini):
    gemini.script = [completion("", finish="content_filter")]
    assert chat(client, user, "...")["actions"] == []
    assert client.get("/chat/history", headers=user).json() == []


# --- choosing a provider ---

@pytest.fixture
def clean_env(monkeypatch):
    for name in ("LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_gemini_key_selects_gemini(clean_env):
    clean_env.setenv("GEMINI_API_KEY", "test-key")
    provider = provider_from_env()
    assert provider.name == "gemini" and provider.models[0] == "gemini-3.5-flash"
    assert provider.extra == {"reasoning_effort": "low"}
    assert str(provider.client.base_url) == "https://generativelanguage.googleapis.com/v1beta/openai/"


def test_model_list_can_be_overridden(clean_env):
    clean_env.setenv("GEMINI_API_KEY", "test-key")
    clean_env.setenv("LLM_MODEL", "model-x, model-y")
    assert provider_from_env().models == ["model-x", "model-y"]


def test_anthropic_key_selects_claude(clean_env):
    clean_env.setenv("ANTHROPIC_API_KEY", "test-key")
    assert isinstance(provider_from_env(), AnthropicProvider)


def test_no_key_is_a_clear_error(clean_env):
    with pytest.raises(LLMNotConfigured, match="GEMINI_API_KEY"):
        provider_from_env()
