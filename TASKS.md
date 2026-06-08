# Task Breakdown

Update this file as integration coverage evolves. Canonical cross-repo milestone
tracking stays in `../ai-assist-architecture/milestones/`.

## Assistant Stream Vertical

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

## Proposed Action Vertical

- [x] Extend the existing assistant stream harness for proposed-action behavior.
- [x] Add fake provider proposal output.
- [x] Add fake action dependencies for create, approve, reject, expire, and cross-session denial.
- [x] Emit and validate `action.proposed` and `action.status_changed` as full `SessionEvent` envelopes.
- [x] Render browser-facing review cards and action status updates.
- [x] Cover the happy path for propose, approve, reject, and status events.
- [x] Cover the failure path for cross-session denial.
- [x] Verify emitted events and stream logs exclude action payload plaintext outside active review-card state.
- [x] Keep runtime names product-generic.
- [x] Keep the one-command harness runner covering both assistant stream and proposed-action flows.

## Planned Evolution

- Extend the same harness for safe Google Docs apply behavior when that milestone starts.
- Keep one `scripts/run-tests` command as the repo grows.
