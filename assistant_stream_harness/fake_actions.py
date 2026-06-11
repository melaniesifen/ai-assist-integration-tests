from __future__ import annotations

from copy import deepcopy

DOCUMENT_ID = "google_doc_demo"
INITIAL_REVISION = "revision_demo"
INTRO_TEXT = "Synthetic sentence with passive wording."
SUMMARY_TEXT = "Synthetic summary that repeats itself."
INITIAL_DOCUMENT_TEXT = f"Intro text. {INTRO_TEXT} More text. {SUMMARY_TEXT}"
HASH_BY_TEXT = {
    INTRO_TEXT: "sha256:synthetic-original-intro",
    SUMMARY_TEXT: "sha256:synthetic-original-summary",
}


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


class FakeDocumentConnector:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.document = {
            "resourceId": DOCUMENT_ID,
            "revision": INITIAL_REVISION,
            "text": INITIAL_DOCUMENT_TEXT,
        }
        self.mutations: list[dict] = []
        self.validations: list[dict] = []
        self._next_revision = 2

    def force_stale_revision(self) -> None:
        self.document["revision"] = f"revision_external_{self._next_revision}"
        self._next_revision += 1

    async def validate_target(self, action: dict) -> dict:
        self.validations.append(
            {
                "actionId": action["actionId"],
                "resourceId": action["resourceId"],
                "expectedRevision": action["resourceRevision"],
            }
        )
        if action["resourceId"] != self.document["resourceId"]:
            return self._conflict(action, "RESOURCE_MISMATCH")
        if action["resourceRevision"] != self.document["revision"]:
            return self._conflict(action, "RESOURCE_STALE")
        target_range = action.get("targetRange")
        if not _valid_target_range(target_range, len(self.document["text"])):
            return self._conflict(action, "TARGET_RANGE_UNRESOLVED")
        current_text = self.document["text"][target_range["start"] : target_range["end"]]
        if HASH_BY_TEXT.get(current_text) != action["originalTextHash"]:
            return self._conflict(action, "ORIGINAL_TEXT_HASH_MISMATCH")
        return {
            "valid": True,
            "verifiedTarget": {
                "resourceId": action["resourceId"],
                "resourceRevision": action["resourceRevision"],
                "targetRange": dict(target_range),
                "originalTextHash": action["originalTextHash"],
            },
        }

    async def apply_action(self, request: dict) -> dict:
        action = request["action"]
        payload = request["payload"]
        verified_target = request["verifiedTarget"]
        target_range = verified_target["targetRange"]
        proposed_text = payload["proposedText"]
        before = self.document["text"]
        self.document["text"] = before[: target_range["start"]] + proposed_text + before[target_range["end"] :]
        self.document["revision"] = f"revision_demo_{self._next_revision}"
        self._next_revision += 1
        provider_operation_id = f"fake_apply_{action['actionId']}_{len(self.mutations) + 1}"
        self.mutations.append(
            {
                "actionId": action["actionId"],
                "idempotencyKey": request["idempotencyKey"],
                "providerOperationId": provider_operation_id,
                "resourceRevision": self.document["revision"],
            }
        )
        return {"providerOperationId": provider_operation_id, "resourceRevision": self.document["revision"]}

    def state(self) -> dict:
        return {
            "resourceId": self.document["resourceId"],
            "revision": self.document["revision"],
            "text": self.document["text"],
            "mutationCount": len(self.mutations),
            "mutations": deepcopy(self.mutations),
        }

    def _conflict(self, action: dict, reason_code: str) -> dict:
        return {
            "valid": False,
            "reasonCode": reason_code,
            "conflictDetails": {
                "reasonCode": reason_code,
                "resourceId": action.get("resourceId"),
                "expectedRevision": action.get("resourceRevision"),
                "currentRevision": self.document["revision"],
            },
        }


def _valid_target_range(value: object, document_length: int) -> bool:
    if not isinstance(value, dict):
        return False
    start = value.get("start")
    end = value.get("end")
    return isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= document_length
