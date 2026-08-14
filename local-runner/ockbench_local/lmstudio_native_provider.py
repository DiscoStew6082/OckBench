"""OckBench provider for LM Studio's native v1 chat endpoint."""

from typing import Any, Dict, Optional

import httpx

from src.core.schemas import ModelResponse, TokenUsage
from src.models.base import BaseModelClient, classify_empty_response, raise_status_error
from src.models.registry import register_provider


@register_provider("lmstudio-native")
class LMStudioNativeClient(BaseModelClient):
    """Call ``POST /api/v1/chat`` with reasoning explicitly disabled."""

    protected_paths = ("model", "input", "stream", "reasoning", "store")
    provider_name = "lmstudio-native"

    def __init__(self, *, transport: Optional[httpx.AsyncBaseTransport] = None, **kwargs):
        super().__init__(**kwargs)
        endpoint = (self.base_url or "http://localhost:1234").rstrip("/")
        if endpoint.endswith("/v1"):
            endpoint = endpoint[:-3]
        self.chat_url = endpoint + "/api/v1/chat"
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(float(self.timeout), connect=30.0),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http_client.aclose()

    def build_request(self, prompt: str, max_output_tokens: int) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": max_output_tokens,
            "reasoning": "off",
            "store": False,
            "stream": False,
        }
        if self.temperature is not None:
            request["temperature"] = self.temperature
        if self.top_p is not None:
            request["top_p"] = self.top_p
        return request

    async def _dispatch(self, request: Dict[str, Any]) -> ModelResponse:
        response = await self._http_client.post(self.chat_url, json=request)
        if response.status_code != 200:
            raise_status_error(response.status_code, response.text)

        payload = response.json()
        output = payload.get("output") or []
        text = "".join(
            item.get("content", "")
            for item in output
            if isinstance(item, dict) and item.get("type") == "message"
        )

        stats = payload.get("stats") or {}
        prompt_tokens = max(int(stats.get("input_tokens") or 0), 0)
        output_tokens = max(int(stats.get("total_output_tokens") or 0), 0)
        reasoning_tokens = max(int(stats.get("reasoning_output_tokens") or 0), 0)
        answer_tokens = max(output_tokens - reasoning_tokens, 0)
        tokens = TokenUsage(
            prompt_tokens=prompt_tokens,
            answer_tokens=answer_tokens,
            reasoning_tokens=reasoning_tokens,
            output_tokens=output_tokens,
            total_tokens=prompt_tokens + output_tokens,
        )

        actual_model = payload.get("model_instance_id") or self.model
        if actual_model != self.model:
            error = f"model_instance_mismatch: requested={self.model} actual={actual_model}"
        elif reasoning_tokens > 0:
            error = f"reasoning_off_violation: provider reported {reasoning_tokens} reasoning tokens"
        else:
            error = classify_empty_response(
                text,
                output_tokens=output_tokens,
                reasoning_evidence=False,
                budget_exhausted=output_tokens >= int(request["max_output_tokens"]),
                detail="native_v1_chat",
            )

        return ModelResponse(
            text=text,
            tokens=tokens,
            latency=0,
            model=actual_model,
            error=error,
            finish_reason=None,
        )
