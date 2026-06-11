from __future__ import annotations


class FakeProviderStream:
    def __init__(self, *, failure: bool = False, proposals: bool = False) -> None:
        self.failure = failure
        self.proposals = proposals
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
        final_event = {
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
        if self.proposals:
            final_event["proposalBatch"] = {
                "proposals": [
                    {
                        "proposalId": "proposal_replace_intro",
                        "actionType": "replace_text",
                        "currentText": "Synthetic sentence with passive wording.",
                        "proposedText": "Synthetic sentence with direct wording.",
                        "surroundingText": "Synthetic paragraph context for active review.",
                        "rationale": "Make the sentence clearer.",
                        "targetHint": {
                            "originalTextHash": "sha256:synthetic-original-intro",
                            "targetRange": {"start": 12, "end": 52},
                        },
                    },
                    {
                        "proposalId": "proposal_replace_summary",
                        "actionType": "replace_text",
                        "currentText": "Synthetic summary that repeats itself.",
                        "proposedText": "Synthetic summary with repetition removed.",
                        "surroundingText": "Synthetic paragraph context for second review.",
                        "rationale": "Remove repetition.",
                        "targetHint": {
                            "originalTextHash": "sha256:synthetic-original-summary",
                            "targetRange": {"start": 64, "end": 102},
                        },
                    },
                ]
            }
        yield final_event
