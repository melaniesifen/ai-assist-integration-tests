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

## Safe Apply Vertical

- [x] Extend the existing assistant stream harness for safe apply behavior.
- [x] Add fake Google Docs document mutation state for safe replace behavior.
- [x] Add approved action apply behavior through orchestration and the fake connector.
- [x] Prove first apply mutates the fake document exactly once and emits `APPLIED`.
- [x] Prove same idempotency key returns the original result and does not mutate twice.
- [x] Prove stale revision returns `CONFLICTED` and leaves fake document state unchanged.
- [x] Emit and validate `action.status_changed` for applied and conflicted paths.
- [x] Render browser-facing applied, replay, conflicted, fake-document, and safety states.
- [x] Verify emitted events and stream logs exclude action payload plaintext outside active review/apply state.
- [x] Keep runtime names product-generic.
- [x] Keep the one-command harness runner covering assistant stream, proposed-action, and safe-apply flows.

## Planned Evolution

- Extend the same harness for live connector smoke coverage only after the deterministic safe-apply milestone is complete.
- Keep one `scripts/run-tests` command as the repo grows.
