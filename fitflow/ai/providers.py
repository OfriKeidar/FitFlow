"""LLM providers: one small interface, one adapter per API.

The agent loop (agent.py) only talks to `LLMProvider`. Each adapter translates between that
interface and one vendor's API. Switching models is a configuration change, not a code change:

    AnthropicProvider         Claude, via the Anthropic SDK
    OpenAICompatibleProvider  any "OpenAI-style" chat API: Google Gemini (free tier), Groq,
                              OpenRouter, a local Ollama... - only the URL and the model differ

Messages are stored in each provider's own format (tool calls look different in each API),
so a conversation is always continued with the provider that started it.
"""

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger("fitflow.llm")

# --- the common interface ---


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: dict | None  # None if the model produced invalid JSON arguments


@dataclass(frozen=True)
class ModelTurn:
    message: dict             # the assistant message in the provider's format, stored and replayed as-is
    text: str                 # the visible reply
    tool_calls: list[ToolCall]
    refused: bool = False     # the provider's safety system declined the request


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    output: str
    is_error: bool


class LLMError(Exception):
    """The model couldn't be reached (outage, bad key...). The SDKs already retried."""


class LLMRateLimited(LLMError):
    """Too many requests - common on free tiers. Worth retrying in a minute."""


class LLMNotConfigured(LLMError):
    """No API key is set for any provider."""


class LLMProvider(Protocol):
    name: str

    def complete(self, system: str, user_context: str, messages: list[dict], tools: list[dict]) -> ModelTurn:
        """`user_context`: a short per-user note (name, how to address them), sent after the static prompt."""
        ...

    def tool_results(self, results: list[ToolResult]) -> list[dict]:
        """The message(s) that send tool results back, in this provider's format."""
        ...


# --- Anthropic (Claude) ---


class AnthropicProvider:
    name = "anthropic"
    MODEL = "claude-opus-5"
    MAX_TOKENS = 16000
    EFFORT = "medium"  # chat + simple tool calls don't need deep reasoning; "high" is the API default

    def __init__(self, client):
        self.client = client  # anthropic.Anthropic(), or a fake in tests

    def complete(self, system, user_context, messages, tools):
        import anthropic

        try:
            response = self.client.beta.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                # The static prompt first (identical for everyone, cache-friendly), then this user's context.
                system=[{"type": "text", "text": system}, {"type": "text", "text": user_context}],
                tools=tools,
                messages=messages,
                output_config={"effort": self.EFFORT},
                cache_control={"type": "ephemeral"},  # cache the growing conversation prefix -> cheaper turns
                # If the safety classifier declines, retry on Anthropic's recommended fallback model.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError as e:
            raise LLMRateLimited(str(e)) from e
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            raise LLMError(str(e)) from e

        if response.stop_reason == "refusal":
            return ModelTurn({}, "", [], refused=True)
        # Keep every block (text, tool_use, thinking...) - the API needs them replayed unchanged.
        blocks = [b.model_dump(mode="json", by_alias=True, exclude_none=True) for b in response.content]
        return ModelTurn(
            message={"role": "assistant", "content": blocks},
            text="\n".join(b.text for b in response.content if b.type == "text").strip(),
            tool_calls=[ToolCall(b.id, b.name, b.input) for b in response.content if b.type == "tool_use"],
        )

    def tool_results(self, results):
        # Anthropic: ALL results in ONE user message, one tool_result block each.
        return [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": r.call_id, "content": r.output, "is_error": r.is_error}
            for r in results
        ]}]


# --- OpenAI-compatible (Gemini, Groq, OpenRouter, Ollama...) ---


class OpenAICompatibleProvider:
    RATE_LIMIT_COOLDOWN = 60.0  # seconds to skip a model after "429 quota exceeded" (quotas are per minute)
    OVERLOAD_COOLDOWN = 20.0    # seconds to skip a model after "503 overloaded" or a timeout

    def __init__(self, client, models: list[str], name: str, extra: dict | None = None, clock=time.monotonic):
        self.client = client  # openai.OpenAI(base_url=..., api_key=...), or a fake in tests
        # Tried in order: free tiers often return "503 overloaded" for one model while another works.
        self.models = models
        self.name = name
        self.extra = extra or {}  # provider-specific request options, e.g. Gemini's reasoning_effort
        # Circuit breaker: model -> time until which we skip it. Shared by all requests, so one user's
        # failure spares the next users the same slow failure.
        self.cooldown_until: dict[str, float] = {}
        self.clock = clock  # injectable, so tests can move time forward

    def models_to_try(self) -> list[str]:
        """Models not cooling down, in order. If every model is cooling down, try them all anyway."""
        now = self.clock()
        ready = [m for m in self.models if self.cooldown_until.get(m, 0) <= now]
        return ready or self.models

    def complete(self, system, user_context, messages, tools):
        import openai

        # OpenAI-style APIs take the system prompt as the first message; it isn't stored in history.
        system_message = {"role": "system", "content": f"{system}\n\n{user_context}"}
        last_error: Exception | None = None
        all_rate_limited = True
        for model in self.models_to_try():
            started = time.monotonic()
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[system_message, *messages],
                    tools=[to_openai_tool(t) for t in tools],
                    **self.extra,
                )
                log.info("%s/%s answered in %.1fs", self.name, model, time.monotonic() - started)
                break
            except openai.RateLimitError as e:
                # Free-tier quotas are per model (e.g. 5 requests/minute), so another model may still have room.
                log.warning("%s/%s rate limited, skipping it for %ds", self.name, model, self.RATE_LIMIT_COOLDOWN)
                self.cooldown_until[model] = self.clock() + self.RATE_LIMIT_COOLDOWN
                last_error = e
            except (openai.InternalServerError, openai.APITimeoutError) as e:
                log.warning("%s/%s failed after %.1fs (%s), skipping it for %ds", self.name, model,
                            time.monotonic() - started, type(e).__name__, self.OVERLOAD_COOLDOWN)
                self.cooldown_until[model] = self.clock() + self.OVERLOAD_COOLDOWN
                last_error, all_rate_limited = e, False
            except (openai.APIStatusError, openai.APIConnectionError) as e:
                raise LLMError(str(e)) from e
        else:
            if all_rate_limited:
                raise LLMRateLimited(f"all models rate limited: {last_error}") from last_error
            raise LLMError(f"all models failed: {last_error}") from last_error

        choice = response.choices[0]
        message = choice.message
        calls = []
        stored_calls = []
        for call in message.tool_calls or []:
            call_id = call.id or f"call_{uuid.uuid4().hex[:12]}"  # some providers omit ids
            calls.append(ToolCall(call_id, call.function.name, parse_arguments(call.function.arguments)))
            # Store the call EXACTLY as received, including fields we don't know about. Gemini puts a
            # required "thought signature" in extra_content and rejects the next request without it.
            stored_calls.append(call.model_dump(exclude_none=True) | {"id": call_id})

        stored = {"role": "assistant", "content": message.content or ""}
        if stored_calls:
            stored["tool_calls"] = stored_calls
        return ModelTurn(
            message=stored,
            text=(message.content or "").strip(),
            tool_calls=calls,
            refused=choice.finish_reason == "content_filter",
        )

    def tool_results(self, results):
        # OpenAI style: one "tool" message per result. There's no is_error field, so say it in the text.
        return [
            {"role": "tool", "tool_call_id": r.call_id, "content": f"Error: {r.output}" if r.is_error else r.output}
            for r in results
        ]


def to_openai_tool(tool: dict) -> dict:
    """Our tool definitions use Anthropic's shape; OpenAI-style APIs wrap them as "functions"."""
    return {"type": "function", "function": {
        "name": tool["name"], "description": tool["description"], "parameters": tool["input_schema"],
    }}


def parse_arguments(raw: str | None) -> dict | None:
    """Tool arguments arrive as a JSON string. Invalid JSON -> None (the agent reports it to the model)."""
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


# --- choosing a provider from the environment ---

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# Tried in order. Checked against the live API in September 2026: newer models were often
# "overloaded" on the free tier, so a reliable one comes first and the "latest" alias is a fallback.
GEMINI_DEFAULT_MODELS = [
    "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-flash-latest", "gemini-3.7-flash", "gemini-flash-lite-latest",
]


def models_from_env(default: list[str]) -> list[str]:
    """LLM_MODEL can name one model or a comma-separated fallback list."""
    value = os.getenv("LLM_MODEL")
    return [m.strip() for m in value.split(",") if m.strip()] if value else default


def provider_from_env() -> LLMProvider:
    """LLM_PROVIDER picks explicitly; otherwise use whichever key is set (Gemini first - it's free)."""
    choice = (os.getenv("LLM_PROVIDER") or "").lower()
    gemini_key = os.getenv("GEMINI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")

    if choice == "gemini" or (not choice and gemini_key):
        if not gemini_key:
            raise LLMNotConfigured("LLM_PROVIDER=gemini but GEMINI_API_KEY is not set")
        import openai
        # Short timeout and one retry per model: with fallback models, failing fast beats waiting.
        client = openai.OpenAI(base_url=GEMINI_BASE_URL, api_key=gemini_key, timeout=45, max_retries=1)
        return OpenAICompatibleProvider(
            client, models_from_env(GEMINI_DEFAULT_MODELS), "gemini",
            # Chat and simple tool calls don't need deep thinking: "low" is faster and uses less quota.
            extra={"reasoning_effort": "low"},
        )

    if choice == "openai-compatible":
        # Any other OpenAI-style API, e.g. Groq, OpenRouter or a local Ollama.
        base_url, models = os.getenv("LLM_BASE_URL"), models_from_env([])
        if not base_url or not models:
            raise LLMNotConfigured("LLM_PROVIDER=openai-compatible needs LLM_BASE_URL and LLM_MODEL")
        import openai
        client = openai.OpenAI(base_url=base_url, api_key=os.getenv("LLM_API_KEY") or "not-needed")
        return OpenAICompatibleProvider(client, models, "openai-compatible")

    if choice == "anthropic" or (not choice and anthropic_key):
        if not anthropic_key:
            raise LLMNotConfigured("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")
        import anthropic
        return AnthropicProvider(anthropic.Anthropic())

    raise LLMNotConfigured("No AI provider is configured: set GEMINI_API_KEY (free) or ANTHROPIC_API_KEY")
