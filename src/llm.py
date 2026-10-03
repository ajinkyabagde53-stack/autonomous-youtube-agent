from __future__ import annotations

import json
import os
import re
from typing import Any

import anthropic

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "medium"
DEFAULT_MAX_TOKENS = 32000

# Re-runs a request the model declines on Anthropic's recommended fallback
# model instead of returning the refusal.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

STRING: dict[str, Any] = {"type": "string"}
NUMBER: dict[str, Any] = {"type": "number"}
STRING_LIST: dict[str, Any] = {"type": "array", "items": STRING}


def object_schema(properties: dict[str, Any]) -> dict[str, Any]:
    """JSON schema for an object whose listed properties are all required."""
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def list_of(item_schema: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": item_schema}


class LLMError(RuntimeError):
    """The model call failed or did not return a usable JSON object."""


class LLMUnavailable(LLMError):
    """No Anthropic API key is configured."""


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model text.

    Structured outputs should always return bare JSON; this also tolerates
    Markdown code fences and surrounding prose so a format slip raises a clear
    LLMError instead of leaking a {"raw": ...} payload downstream.
    """
    cleaned = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)

    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise LLMError("Model response did not contain a JSON object.") from None
        try:
            value = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"Model response was not valid JSON: {exc}") from None

    if not isinstance(value, dict):
        raise LLMError("Model response was JSON but not an object.")
    return value


class LLMClient:
    """Small provider wrapper so agents do not depend directly on SDK details."""

    def __init__(self, model: str | None = None, effort: str | None = None) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        # `or` rather than a getenv default: an empty line in .env yields "".
        self.model = model or os.getenv("CLAUDE_MODEL") or DEFAULT_MODEL
        self.effort = effort or os.getenv("CLAUDE_EFFORT") or DEFAULT_EFFORT
        self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None

    @property
    def available(self) -> bool:
        return self.client is not None

    def complete_json(
        self,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict[str, Any]:
        """Return a JSON object matching `schema`, or raise LLMError."""
        if not self.client:
            raise LLMUnavailable("ANTHROPIC_API_KEY is not set.")

        try:
            # Streaming keeps long generations clear of HTTP timeouts.
            with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": schema},
                },
                betas=[FALLBACK_BETA],
                fallbacks="default",
            ) as stream:
                response = stream.get_final_message()
        except anthropic.APIStatusError as exc:
            raise LLMError(
                f"Anthropic API returned {exc.status_code}: {exc.message}"
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError(f"Could not reach the Anthropic API: {exc}") from exc

        if response.stop_reason == "refusal":
            raise LLMError("The model declined this request.")
        if response.stop_reason == "max_tokens":
            raise LLMError(f"Model output was cut off at max_tokens={max_tokens}.")

        text = "".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        )
        result = parse_json_object(text)

        missing = [key for key in schema.get("required", []) if key not in result]
        if missing:
            raise LLMError(
                "Model response is missing required keys: " + ", ".join(missing)
            )
        return result
