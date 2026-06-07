from __future__ import annotations


class FakeProviderStream:
    def __init__(self, *, failure: bool = False) -> None:
        self.failure = failure
        self.requests: list[dict] = []

    async def stream(self, request: dict):
        self.requests.append(request)
        if self.failure:
            yield {
                "type": "error",
                "provider": "openai",
                "model": "fake-stream-model",
                "error": {
                    "code": "PROVIDER_UNAVAILABLE",
                    "category": "unavailable",
                    "message": "The provider stream is unavailable.",
                    "dependencyStatus": "unavailable",
                },
            }
            return

        yield {
            "type": "assistant.delta",
            "provider": "openai",
            "model": "fake-stream-model",
            "delta": "Here is ",
        }
        yield {
            "type": "assistant.delta",
            "provider": "openai",
            "model": "fake-stream-model",
            "delta": "a streamed answer.",
        }
        yield {
            "type": "assistant.final",
            "provider": "openai",
            "model": "fake-stream-model",
            "finishReason": "stop",
            "usage": {
                "inputTokens": 4,
                "outputTokens": 6,
                "totalTokens": 10,
            },
        }
