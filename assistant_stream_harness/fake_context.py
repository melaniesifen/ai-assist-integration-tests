from __future__ import annotations


class FakeContextService:
    def __init__(self, *, unavailable: bool = False) -> None:
        self.unavailable = unavailable
        self.requests: list[dict] = []

    async def resolve_context(self, request: dict) -> dict:
        self.requests.append(request)
        if self.unavailable:
            return {
                "authorized": False,
                "reasonCode": "CONTEXT_DEPENDENCY_UNAVAILABLE",
            }
        return {
            "authorized": True,
            "contextMode": request["contextMode"],
            "resourceRef": {
                "provider": "google_docs",
                "resourceId": request["resourceId"],
                "resourceType": "document",
            },
            "provenance": {
                "connectorVerified": True,
                "resourceVersion": "revision_demo",
                "trustLevel": "connector_verified",
            },
            "metadata": {
                "selectionState": "available",
                "contentHash": "sha256:synthetic-context",
                "truncated": False,
            },
        }


class AllowPolicy:
    async def evaluate(self, _request: dict) -> dict:
        return {"decision": "ALLOW", "decisionId": "policy_demo_allow"}


class PromptBuilder:
    def build_prompt(self, request: dict) -> dict:
        command = request["command"]
        context = request["context"]
        return {
            "promptId": command["commandId"],
            "contextMode": context["contextMode"],
            "resourceId": context["resourceRef"]["resourceId"],
        }
