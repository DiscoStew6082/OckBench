import asyncio
import json

import httpx
import ockbench_local.lmstudio_native_provider  # noqa: F401

from src.models import create_provider


def test_native_provider_disables_reasoning_and_preserves_exact_usage():
    captured = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model_instance_id": "qwen3.5-9b-mtp",
                "output": [{"type": "message", "content": "READY"}],
                "stats": {
                    "input_tokens": 20,
                    "total_output_tokens": 2,
                    "reasoning_output_tokens": 0,
                    "tokens_per_second": 55.0,
                    "time_to_first_token_seconds": 0.17,
                },
            },
        )

    client = create_provider(
        "lmstudio-native",
        model="qwen3.5-9b-mtp",
        base_url="http://lmstudio:1234",
        api_key="dummy",
        timeout=120,
        wall_clock_timeout=180,
        max_retries=1,
        temperature=0.0,
        transport=httpx.MockTransport(handle),
    )

    response = asyncio.run(client.generate("Reply exactly READY", 32))
    asyncio.run(client.aclose())

    assert captured == {
        "url": "http://lmstudio:1234/api/v1/chat",
        "body": {
            "model": "qwen3.5-9b-mtp",
            "input": "Reply exactly READY",
            "max_output_tokens": 32,
            "reasoning": "off",
            "store": False,
            "stream": False,
            "temperature": 0.0,
        },
    }
    assert response.text == "READY"
    assert response.model == "qwen3.5-9b-mtp"
    assert response.tokens.prompt_tokens == 20
    assert response.tokens.answer_tokens == 2
    assert response.tokens.reasoning_tokens == 0
    assert response.tokens.output_tokens == 2
    assert response.tokens.total_tokens == 22
    assert response.error is None
    assert response.finish_reason is None
