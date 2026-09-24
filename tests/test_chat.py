"""Tests for the AI coach, using a scripted fake LLM.

We don't test the model's intelligence here - we test OUR code around it: the agentic loop,
tool execution, the confirm-before-save gate, persistence and error handling.
Each test scripts what "Claude" answers on each round, then checks what our code did.
"""

import json

import anthropic
import httpx2
import pytest
from anthropic.types.beta import BetaMessage

from fitflow.ai.agent import MAX_TOOL_ROUNDS, REFUSAL_REPLY, TOO_MANY_ROUNDS_REPLY, CoachAgent
from fitflow.api.deps import get_agent
from fitflow.api.main import app
from tests.conftest import food_id


# --- a fake Anthropic client ---

def tool_call(name: str, tool_input: dict, call_id: str = "call_1") -> dict:
    return {"type": "tool_use", "id": call_id, "name": name, "input": tool_input}


def text(value: str) -> dict:
    return {"type": "text", "text": value}


def reply(*blocks: dict, stop_reason: str | None = None) -> BetaMessage:
    """Build a real SDK response object, like the API would return."""
    if stop_reason is None:
        stop_reason = "tool_use" if any(b["type"] == "tool_use" for b in blocks) else "end_turn"
    return BetaMessage.model_validate({
        "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5",
        "content": list(blocks), "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    })


class FakeLLM:
    """Stands in for anthropic.Anthropic(): returns scripted replies and records every request."""

    def __init__(self, *script):
        self.script = list(script)
        self.requests: list[dict] = []
        self.beta = self  # so code can call fake.beta.messages.create(...)
        self.messages = self

    def create(self, **request):
        self.requests.append(json.loads(json.dumps(request, default=str)))  # snapshot the request
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def llm(client):
    """Install a FakeLLM; each test sets its script with llm.script = [...]."""
    fake = FakeLLM()
    app.dependency_overrides[get_agent] = lambda: CoachAgent(fake)
    return fake


def chat(client, user, message: str, **extra) -> dict:
    r = client.post("/chat", headers=user, json={"message": message, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def last_tool_results(request: dict) -> list[dict]:
    return request["messages"][-1]["content"]


# --- tests ---

def test_food_is_proposed_not_logged_until_confirmed(client, user, llm):
    egg = food_id(client, "ביצה")
    llm.script = [
        reply(tool_call("search_foods", {"query": "ביצה"})),
        reply(tool_call("propose_food_log", {"items": [{"food_id": egg, "servings": 2}]}, "call_2")),
        reply(text("רשמתי 2 ביצים, 144 קק\"ל. מחכה לאישור שלך")),
    ]
    result = chat(client, user, "אכלתי 2 ביצים")

    assert result["reply"].startswith("רשמתי 2 ביצים")
    [action] = result["actions"]
    assert action["kind"] == "food" and action["status"] == "pending"
    assert client.get("/today", headers=user).json()["eaten"]["kcal"] == 0  # nothing logged yet

    client.post(f"/chat/actions/{action['id']}/confirm", headers=user)
    assert client.get("/today", headers=user).json()["eaten"]["kcal"] == 144


def test_tool_results_are_sent_back_to_the_model(client, user, llm):
    llm.script = [reply(tool_call("search_foods", {"query": "ביצה"})), reply(text("ok"))]
    chat(client, user, "כמה חלבון יש בביצה?")

    [result] = last_tool_results(llm.requests[1])
    assert result["type"] == "tool_result" and result["tool_use_id"] == "call_1"
    assert json.loads(result["content"])[0]["name"] == "ביצה"


def test_confirming_twice_does_not_log_twice(client, user, llm):
    llm.script = [reply(tool_call("propose_weight", {"weight_kg": 79.5})), reply(text("ok"))]
    [action] = chat(client, user, "שקלתי 79.5")["actions"]

    assert client.post(f"/chat/actions/{action['id']}/confirm", headers=user).status_code == 200
    assert client.post(f"/chat/actions/{action['id']}/confirm", headers=user).status_code == 404


def test_rejected_action_is_not_logged(client, user, llm):
    llm.script = [reply(tool_call("propose_custom_food", {
        "description": "פיצה משפחתית", "kcal": 2000, "protein_g": 80, "carbs_g": 250, "fat_g": 70,
    })), reply(text("ok"))]
    [action] = chat(client, user, "אכלתי פיצה משפחתית")["actions"]

    assert client.post(f"/chat/actions/{action['id']}/reject", headers=user).json()["status"] == "rejected"
    assert client.get("/today", headers=user).json()["eaten"]["kcal"] == 0


def test_workout_preview_comes_from_our_formula(client, user, llm):
    llm.script = [reply(tool_call("propose_workout", {"activity": "running", "minutes": 30})), reply(text("ok"))]
    chat(client, user, "רצתי חצי שעה")

    preview = json.loads(last_tool_results(llm.requests[1])[0]["content"])
    assert preview["kcal_burned"] == 352  # (9.8 - 1) MET * 80 kg * 0.5 h


def test_invalid_tool_input_is_returned_as_error_so_the_model_can_fix_it(client, user, llm):
    llm.script = [
        reply(tool_call("propose_food_log", {"items": [{"food_id": 99999, "servings": 1}]})),
        reply(text("לא מצאתי את המזון הזה")),
    ]
    result = chat(client, user, "אכלתי משהו")

    [error] = last_tool_results(llm.requests[1])
    assert error["is_error"] is True and "does not exist" in error["content"]
    assert result["actions"] == []


def test_parallel_tool_calls_get_all_results_in_one_message(client, user, llm):
    llm.script = [
        reply(tool_call("search_foods", {"query": "ביצה"}, "a"), tool_call("search_foods", {"query": "לחם"}, "b")),
        reply(text("ok")),
    ]
    chat(client, user, "ביצה ולחם")
    assert [r["tool_use_id"] for r in last_tool_results(llm.requests[1])] == ["a", "b"]


def test_conversation_history_is_kept_for_the_day(client, user, llm):
    llm.script = [reply(text("שלום!")), reply(text("עדיין כאן"))]
    chat(client, user, "היי")
    chat(client, user, "מה נשמע?")

    sent = llm.requests[1]["messages"]
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert client.get("/chat/history", headers=user).json() == [
        {"role": "user", "text": "היי"}, {"role": "assistant", "text": "שלום!"},
        {"role": "user", "text": "מה נשמע?"}, {"role": "assistant", "text": "עדיין כאן"},
    ]


def test_refusal_saves_nothing(client, user, llm):
    llm.script = [
        reply(tool_call("propose_weight", {"weight_kg": 80})),
        reply(stop_reason="refusal"),
    ]
    result = chat(client, user, "...")

    assert result == {"reply": REFUSAL_REPLY, "actions": []}
    assert client.get("/chat/history", headers=user).json() == []


def test_endless_tool_loop_is_stopped(client, user, llm):
    llm.script = [reply(tool_call("get_today_status", {})) for _ in range(MAX_TOOL_ROUNDS)]
    result = chat(client, user, "?")
    assert result["reply"] == TOO_MANY_ROUNDS_REPLY
    assert client.get("/chat/history", headers=user).json() == []


def test_api_outage_returns_503(client, user, llm):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    llm.script = [anthropic.InternalServerError("boom", response=httpx2.Response(500, request=request), body=None)]
    assert client.post("/chat", headers=user, json={"message": "hi"}).status_code == 503


def test_request_uses_expected_model_settings(client, user, llm):
    llm.script = [reply(text("ok"))]
    chat(client, user, "hi")
    request = llm.requests[0]
    assert request["model"] == "claude-opus-5"
    assert request["fallbacks"] == "default"
    assert {t["name"] for t in request["tools"]} >= {"search_foods", "propose_food_log", "propose_workout"}
