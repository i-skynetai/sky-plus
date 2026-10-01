"""LiteLLM model provider (SP-021): any model LiteLLM can reach, behind the model port.

Structured output is requested natively when the model supports a JSON schema, as a JSON
object when it supports that, and by instruction otherwise; the parsed object lands in
`ModelResponse.structured` either way. Tool calls the model makes are mapped to plain
dicts in `ModelResponse.tool_calls`. Nothing from LiteLLM crosses the port.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")   # no network fetch at import
import litellm  # noqa: E402

from ..core.errors import ProviderError  # noqa: E402
from ..core.provider import Health, Manifest  # noqa: E402
from ..spi import ModelProvider, ModelResponse  # noqa: E402

VERSION = "0.2.0"
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
_PASS_THROUGH = ("api_base", "api_key", "api_version", "temperature", "max_tokens", "timeout",
                 "top_p", "seed", "mock_response", "extra_headers", "custom_llm_provider")

litellm.suppress_debug_info = True


def _parse_json(text: str) -> dict | None:
    for candidate in (text, (_JSON_BLOCK.search(text or "") or [None])[0] if _JSON_BLOCK.search(text or "") else None):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            continue
    return None


class LiteLLMModel(ModelProvider):
    manifest = Manifest(id="litellm", capability="model", version=VERSION,
                        provides={"completion": True, "structured": True, "tools": True, "streaming": False},
                        package="litellm",
                        description="any model LiteLLM can reach — OpenAI, Anthropic, Azure, Bedrock, Vertex, Ollama, vLLM, ...")

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.model: str = str(self.config.get("model") or "gpt-4o-mini")
        self.structured_mode: str = str(self.config.get("structured", "auto"))   # auto | json_schema | json_object | prompt
        self.options = {k: v for k, v in self.config.items() if k in _PASS_THROUGH}

    async def health(self) -> Health:
        if not self.model:
            return Health(ok=False, detail="no model configured")
        try:
            env = litellm.validate_environment(model=self.model, api_key=self.options.get("api_key"),
                                               api_base=self.options.get("api_base"))
        except Exception as exc:  # noqa: BLE001
            return Health(ok=True, detail=f"model {self.model}; could not check keys: {exc}")
        missing = env.get("missing_keys") or []
        if missing and not self.options.get("mock_response"):
            return Health(ok=False, detail=f"model {self.model}: missing {', '.join(missing)} in the environment",
                          checks={"missing_keys": missing})
        return Health(ok=True, detail=f"model {self.model}; keys present", checks={"model": self.model})

    def _structured_kwargs(self, schema: dict, messages: list[dict]) -> tuple[dict, list[dict]]:
        mode = self.structured_mode
        if mode == "auto":
            try:
                mode = "json_schema" if litellm.supports_response_schema(self.model) else "json_object"
            except Exception:  # noqa: BLE001
                mode = "prompt"
        if mode == "json_schema":
            return {"response_format": {"type": "json_schema",
                                        "json_schema": {"name": "response", "schema": schema}}}, messages
        instruction = {"role": "system", "content": "Reply with one JSON object matching this schema: " + json.dumps(schema)}
        if mode == "json_object":
            return {"response_format": {"type": "json_object"}}, [instruction, *messages]
        return {}, [instruction, *messages]

    async def complete(self, messages: list[dict], *, schema: dict | None = None, **options: Any) -> ModelResponse:
        kwargs: dict[str, Any] = {"model": self.model, **self.options}
        tools = options.pop("tools", None)
        kwargs.update(options)
        if tools:
            kwargs["tools"] = [_tool_spec(t) for t in tools]
        if schema:
            extra, messages = self._structured_kwargs(schema, messages)
            kwargs.update(extra)
        kwargs["messages"] = messages
        try:
            response = await litellm.acompletion(**kwargs)
        except Exception as exc:  # noqa: BLE001 — LiteLLM's many exception types become one
            raise ProviderError(f"model {self.model}: {type(exc).__name__}: {str(exc)[:300]}") from exc
        choice = response.choices[0]
        message = choice.message
        text = message.content or ""
        usage_obj = getattr(response, "usage", None)
        usage = {"input_tokens": int(getattr(usage_obj, "prompt_tokens", 0) or 0),
                 "output_tokens": int(getattr(usage_obj, "completion_tokens", 0) or 0), "cost_usd": 0.0}
        try:
            usage["cost_usd"] = float(litellm.completion_cost(completion_response=response) or 0.0)
        except Exception:  # noqa: BLE001 — an unknown model has no price; that is not an error
            pass
        tool_calls = []
        for call in getattr(message, "tool_calls", None) or []:
            fn = getattr(call, "function", None)
            raw_args = getattr(fn, "arguments", None) or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except json.JSONDecodeError:
                args = {"_raw": raw_args}
            tool_calls.append({"id": getattr(call, "id", None), "name": getattr(fn, "name", None), "arguments": args})
        return ModelResponse(text=text, model=str(getattr(response, "model", None) or self.model), usage=usage,
                             structured=_parse_json(text) if schema else None, tool_calls=tool_calls)


def _tool_spec(tool: Any) -> dict:
    if isinstance(tool, dict):
        return tool if tool.get("type") == "function" else {"type": "function", "function": tool}
    return {"type": "function", "function": {"name": tool.name, "description": tool.description,
                                             "parameters": tool.parameters or {"type": "object", "properties": {}}}}
