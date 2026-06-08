# AI Assist Integration Tests

This repo owns local cross-repo integration harnesses for AI Assist product
flows. It should evolve as each milestone adds behavior instead of creating
milestone-specific test repos or runtime packages.

The first covered vertical proves the assistant stream path:

```text
user command -> orchestration -> context/read path -> provider adapter
-> session-events/SSE -> web UI
```

The harness also covers the proposed-action review path:

```text
provider fake proposal -> orchestration proposed action -> action.proposed SSE
-> review card -> approve/reject HTTP command -> action.status_changed SSE
```

The harness uses local fakes and injected dependencies. It does not call real
cloud, Google Docs, OAuth, provider, KMS, database, or secret-storage services.

## Run

```sh
scripts/run-tests
```

## Demo

Start the local server:

```sh
python3 -m assistant_stream_harness.harness_server --serve --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765/
```

Use **Send command** to run the happy path. The UI opens the local SSE stream
and renders context progress, provider progress, assistant delta, and assistant
final events.

Use **Run provider failure** to show a safe dependency failure. The UI renders a
typed error event without exposing raw prompt, document content, provider keys,
OAuth tokens, or authorization headers.

Use **Create proposed actions** to make the fake provider return two synthetic
proposal outputs. The harness creates server-owned proposed actions, emits
`action.proposed` events over SSE, and renders review cards.

On each review card:

- **Approve** transitions the action to `APPROVED` and emits
  `action.status_changed`.
- **Reject** transitions the action to `REJECTED` and emits
  `action.status_changed`.
- **Expire** forces a stale action clock condition, then emits an `EXPIRED`
  status update.
- **Cross-session denial** sends the decision command with the wrong session ID
  and returns `ACTION_FORBIDDEN` without changing the action.

The **Safety** section reports whether stream logs and emitted events stayed
metadata-only. Synthetic review text appears only in the active review card
state, not in SSE events or stream lifecycle logs.
