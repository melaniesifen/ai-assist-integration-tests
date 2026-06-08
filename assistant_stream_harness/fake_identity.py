from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FakeIdentity:
    tenant_id: str = "tenant_demo"
    user_id: str = "user_demo"
    session_id: str = "session_demo"
    request_id: str = "request_demo"
    correlation_id: str = "correlation_demo"

    @property
    def auth_subject(self) -> dict[str, str]:
        return {"tenantId": self.tenant_id, "userId": self.user_id}

    def command(self, *, mode: str = "happy", provider: str = "openai") -> dict[str, str]:
        return {
            "commandId": f"command_{mode}",
            "requestId": self.request_id,
            "correlationId": self.correlation_id,
            "sessionId": self.session_id,
            "provider": provider,
            "resourceId": "google_doc_demo",
            "contextMode": "SELECTION",
            "secretRef": "session_secret_demo",
        }

    def action_decision(self, action_id: str) -> dict[str, str]:
        return {
            "actionId": action_id,
            "requestId": self.request_id,
            "correlationId": self.correlation_id,
            "sessionId": self.session_id,
            "resourceId": "google_doc_demo",
        }
