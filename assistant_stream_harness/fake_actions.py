from __future__ import annotations


class FakePayloadVault:
    def __init__(self) -> None:
        self.payloads: dict[str, dict] = {}
        self._next_id = 1

    async def encrypt(self, payload: dict | None) -> dict[str, str]:
        ciphertext_ref = f"fake_ciphertext_{self._next_id:03d}"
        self._next_id += 1
        self.payloads[ciphertext_ref] = dict(payload or {})
        return {"ciphertextRef": ciphertext_ref}

    async def decrypt(self, encrypted_payload: dict) -> dict:
        return dict(self.payloads[encrypted_payload["ciphertextRef"]])

    def read_payload(self, encrypted_payload: dict) -> dict:
        return dict(self.payloads[encrypted_payload["ciphertextRef"]])


class AllowApplyConsent:
    async def validate_apply_consent(self, _request: dict) -> dict:
        return {"allowed": True}


class FakeActionConnector:
    async def validate_target(self, action: dict) -> dict:
        return {
            "valid": True,
            "verifiedTarget": {
                "resourceId": action["resourceId"],
                "resourceRevision": action["resourceRevision"],
            },
        }

    async def apply_action(self, request: dict) -> dict:
        return {"providerOperationId": f"fake_apply_{request['action']['actionId']}"}
