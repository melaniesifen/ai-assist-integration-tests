from __future__ import annotations

import argparse
import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SERVICE_SRC_PATHS = (
    WORKSPACE_ROOT / "ai-assist-orchestration-service" / "src",
    WORKSPACE_ROOT / "ai-assist-session-events-service" / "src",
)
for service_src_path in SERVICE_SRC_PATHS:
    path_text = str(service_src_path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from ai_assist_orchestration import OrchestrationError, create_command_service
from ai_assist_session_events import (
    create_assistant_delta_event,
    create_assistant_final_event,
    create_progress_event,
    create_safe_error_event,
    create_stream_log_record,
    format_sse_event,
    validate_session_event,
)

from .fake_context import AllowPolicy, FakeContextService, PromptBuilder
from .fake_identity import FakeIdentity
from .fake_provider import FakeProviderStream

EVENT_TYPE_PROGRESS = "progress"
EVENT_TYPE_ASSISTANT_DELTA = "assistant.delta"
EVENT_TYPE_ASSISTANT_FINAL = "assistant.final"
EVENT_TYPE_ERROR = "error"
TERMINAL_EVENT_TYPES = {EVENT_TYPE_ASSISTANT_FINAL, EVENT_TYPE_ERROR}
SAFE_AUDIT_FORBIDDEN_TERMS = (
    "providerKey",
    "apiKey",
    "oauthToken",
    "accessToken",
    "refreshToken",
    "authorization",
    "bearerToken",
    "documentText",
    "selectedText",
    "raw document",
    "raw prompt",
)


class EventBridge:
    def __init__(self, identity: FakeIdentity, *, clock: Callable[[], str] | None = None) -> None:
        self.identity = identity
        self.clock = clock or (lambda: "2026-06-07T00:00:00.000Z")
        self.events: list[dict[str, Any]] = []
        self.stream_logs: list[dict[str, Any]] = []
        self._sequence = 0

    async def publish(self, event: dict[str, Any]) -> None:
        session_event = self._to_session_event(event)
        validation = validate_session_event(session_event)
        if not validation["valid"]:
            raise OrchestrationError(
                code="SESSION_EVENT_INVALID",
                category="VALIDATION",
                message="Session event failed validation.",
                metadata={"eventType": event.get("type")},
            )
        self.events.append(session_event)

    def reset(self) -> None:
        self.events.clear()
        self.stream_logs.clear()
        self._sequence = 0

    def open_stream_log(self) -> None:
        self.stream_logs.append(
            create_stream_log_record(
                "stream.open",
                {
                    "tenantId": self.identity.tenant_id,
                    "userId": self.identity.user_id,
                    "sessionId": self.identity.session_id,
                    "requestId": self.identity.request_id,
                    "correlationId": self.identity.correlation_id,
                    "route": "/api/session-events",
                    "statusCode": 200,
                },
                now=self.clock,
            )
        )

    def close_stream_log(self) -> None:
        self.stream_logs.append(
            create_stream_log_record(
                "stream.close",
                {
                    "tenantId": self.identity.tenant_id,
                    "userId": self.identity.user_id,
                    "sessionId": self.identity.session_id,
                    "requestId": self.identity.request_id,
                    "correlationId": self.identity.correlation_id,
                    "route": "/api/session-events",
                    "statusCode": 200,
                    "disconnectReason": "server_complete",
                },
                now=self.clock,
            )
        )

    def sse_frames(self) -> list[str]:
        return [format_sse_event(event) for event in self.events]

    def _next_envelope(self, flat_event: dict[str, Any]) -> dict[str, Any]:
        self._sequence += 1
        return {
            "eventId": f"event_{self._sequence:03d}",
            "tenantId": self.identity.tenant_id,
            "userId": self.identity.user_id,
            "sessionId": flat_event.get("sessionId") or self.identity.session_id,
            "requestId": flat_event.get("requestId") or self.identity.request_id,
            "correlationId": flat_event.get("correlationId") or self.identity.correlation_id,
            "sequence": self._sequence,
        }

    def _to_session_event(self, flat_event: dict[str, Any]) -> dict[str, Any]:
        envelope = self._next_envelope(flat_event)
        event_type = flat_event.get("type")
        if event_type == EVENT_TYPE_PROGRESS:
            return create_progress_event(
                envelope,
                stage=flat_event["stage"],
                status=flat_event["status"],
                message_code=flat_event["messageCode"],
                now=self.clock,
            )
        if event_type == EVENT_TYPE_ASSISTANT_DELTA:
            return create_assistant_delta_event(
                envelope,
                message_id=flat_event["messageId"],
                delta=flat_event.get("delta", ""),
                index=flat_event.get("index", 0),
                now=self.clock,
            )
        if event_type == EVENT_TYPE_ASSISTANT_FINAL:
            return create_assistant_final_event(
                envelope,
                message_id=flat_event["messageId"],
                finish_reason=flat_event.get("finishReason") or "stop",
                usage=flat_event.get("usage"),
                now=self.clock,
            )
        if event_type == EVENT_TYPE_ERROR:
            return create_safe_error_event(
                envelope,
                error_code=flat_event["errorCode"],
                category=flat_event["category"],
                retryable=flat_event["retryable"],
                message=flat_event["message"],
                metadata=flat_event.get("metadata"),
                now=self.clock,
            )
        raise OrchestrationError(
            code="SESSION_EVENT_UNSUPPORTED",
            category="VALIDATION",
            message="Session event type is not supported by the harness.",
            metadata={"eventType": event_type},
        )


class HarnessApp:
    def __init__(self) -> None:
        self.identity = FakeIdentity()
        self.bridge = EventBridge(self.identity)

    async def run_command(self, *, mode: str = "happy") -> dict[str, Any]:
        self.bridge.reset()
        context_service = FakeContextService(unavailable=mode == "context_failure")
        provider = FakeProviderStream(failure=mode == "provider_failure")
        service = create_command_service(
            context_service=context_service,
            provider_registry={"openai": provider},
            event_publisher=self.bridge,
            policy_service=AllowPolicy(),
            prompt_builder=PromptBuilder(),
        )
        try:
            result = await service.run_assistant_command(self.identity.auth_subject, self.identity.command(mode=mode))
            status = "completed"
            error = None
        except OrchestrationError as caught:
            result = None
            status = "failed"
            error = {"code": caught.code, "category": caught.category, "message": caught.message}
        return {
            "status": status,
            "result": result,
            "error": error,
            "sessionId": self.identity.session_id,
            "eventStreamUrl": f"/api/session-events?sessionId={self.identity.session_id}",
            "eventCount": len(self.bridge.events),
            "events": self.bridge.events,
            "safety": self.safety_report(),
        }

    def safety_report(self) -> dict[str, Any]:
        event_text = json.dumps(self.bridge.events, sort_keys=True)
        log_text = json.dumps(self.bridge.stream_logs, sort_keys=True)
        forbidden_hits = [term for term in SAFE_AUDIT_FORBIDDEN_TERMS if term in event_text or term in log_text]
        return {
            "metadataOnlyLogs": not forbidden_hits,
            "forbiddenHits": forbidden_hits,
            "streamLogCount": len(self.bridge.stream_logs),
        }


def create_handler(app: HarnessApp):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._write_response(200, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/session-events":
                query = parse_qs(parsed.query)
                session_id = query.get("sessionId", [""])[0]
                if session_id != app.identity.session_id:
                    self._write_json(404, {"error": "session_not_found"})
                    return
                app.bridge.open_stream_log()
                body = "".join(app.bridge.sse_frames()).encode("utf-8")
                app.bridge.close_stream_log()
                self._write_response(200, body, "text/event-stream; charset=utf-8")
                return
            self._write_json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/assistant-command":
                self._write_json(404, {"error": "not_found"})
                return
            body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._write_json(400, {"error": "invalid_json"})
                return
            mode = payload.get("mode") if isinstance(payload, dict) else "happy"
            if mode not in {"happy", "provider_failure", "context_failure"}:
                self._write_json(400, {"error": "unsupported_mode"})
                return
            result = asyncio.run(app.run_command(mode=mode))
            self._write_json(202, result)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def _write_json(self, status: int, payload: dict[str, Any]) -> None:
            self._write_response(status, json.dumps(payload, separators=(",", ":")).encode("utf-8"), "application/json")

        def _write_response(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve(host: str, port: int) -> None:
    app = HarnessApp()
    server = ThreadingHTTPServer((host, port), create_handler(app))
    print(f"Serving assistant stream harness at http://{host}:{port}/")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local assistant stream harness server.")
    parser.add_argument("--serve", action="store_true", help="Start the local HTTP/SSE demo server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.serve:
        serve(args.host, args.port)
        return
    app = HarnessApp()
    result = asyncio.run(app.run_command(mode="happy"))
    print(json.dumps(result, indent=2, sort_keys=True))


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Assistant Stream Harness</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; color: #111827; }
    main { max-width: 960px; margin: 0 auto; }
    button { margin-right: 0.5rem; padding: 0.55rem 0.8rem; border: 1px solid #374151; background: #fff; border-radius: 6px; cursor: pointer; }
    section { border-top: 1px solid #d1d5db; margin-top: 1.5rem; padding-top: 1rem; }
    .event { padding: 0.5rem 0; border-bottom: 1px solid #e5e7eb; }
    .event strong { display: inline-block; min-width: 9rem; }
    .error { color: #b91c1c; }
    .final { color: #047857; }
    code { background: #f3f4f6; padding: 0.1rem 0.25rem; border-radius: 4px; }
  </style>
</head>
<body>
<main>
  <h1>Assistant Stream Harness</h1>
  <p>Local fake-backed command, orchestration, session event, SSE, and UI path.</p>
  <button id="send">Send command</button>
  <button id="fail">Run provider failure</button>
  <section>
    <h2>Command</h2>
    <p id="command-state">No command sent.</p>
  </section>
  <section>
    <h2>Events</h2>
    <div id="events"></div>
  </section>
  <section>
    <h2>Safety</h2>
    <p id="safety">No safety report yet.</p>
  </section>
</main>
  <script>
const events = document.getElementById("events");
const commandState = document.getElementById("command-state");
const safety = document.getElementById("safety");
const seenEventIds = new Set();

document.getElementById("send").addEventListener("click", () => run("happy"));
document.getElementById("fail").addEventListener("click", () => run("provider_failure"));

async function run(mode) {
  events.innerHTML = "";
  seenEventIds.clear();
  commandState.textContent = "Sending command...";
  safety.textContent = "Waiting for safety report...";
  const response = await fetch("/api/assistant-command", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({mode})
  });
  const body = await response.json();
  commandState.textContent = `${body.status} with ${body.eventCount} event(s)`;
  safety.textContent = body.safety.metadataOnlyLogs ? "metadata only" : `forbidden hits: ${body.safety.forbiddenHits.join(", ")}`;
  openStream(body.eventStreamUrl);
}

function openStream(url) {
  const source = new EventSource(url);
  for (const type of ["progress", "assistant.delta", "assistant.final", "error"]) {
    source.addEventListener(type, (message) => {
      if (!message.data) return;
      appendEvent(type, JSON.parse(message.data));
    });
  }
  source.onerror = () => source.close();
}

function appendEvent(type, event) {
  if (!event.eventId || seenEventIds.has(event.eventId)) return;
  seenEventIds.add(event.eventId);
  const row = document.createElement("div");
  row.className = `event ${type === "error" ? "error" : ""} ${type === "assistant.final" ? "final" : ""}`;
  const label = document.createElement("strong");
  label.textContent = type;
  const code = document.createElement("code");
  code.textContent = event.eventId;
  const text = event.payload.messageCode || event.payload.delta || event.payload.finishReason || event.payload.errorCode || "";
  row.append(label, code, document.createTextNode(` ${text}`));
  events.appendChild(row);
}
window.appendEvent = appendEvent;
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
