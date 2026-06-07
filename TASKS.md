# Task Breakdown

Update this file as implementation progresses. Canonical cross-repo milestone
tracking lives in `../ai-assist-architecture/milestones/m5-ask-and-stream.md`.

## M5 Ask And Stream Harness

- [x] Create a dedicated sibling integration-test repo.
- [x] Add fake authenticated identity for tenant, user, session, request, and correlation IDs.
- [x] Add fake M4-compatible context/read path for approved context.
- [x] Add deterministic fake provider stream output.
- [x] Add a local event bridge that converts orchestration events into validated `SessionEvent` envelopes.
- [x] Add stdlib HTTP command and SSE endpoints.
- [x] Add a browser-facing local demo UI.
- [x] Cover one happy path and one provider dependency failure path.
- [x] Verify emitted events are metadata-safe outside active user-visible assistant output.
- [x] Add one-command harness runner.
