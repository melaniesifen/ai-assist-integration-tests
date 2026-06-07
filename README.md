# AI Assist Integration Tests

This repo owns local cross-repo integration harnesses for AI Assist milestone
flows. The first harness proves the Ask And Stream path:

```text
user command -> orchestration -> context/read path -> provider adapter
-> session-events/SSE -> web UI
```

The harness uses local fakes and injected dependencies. It does not call real
cloud, Google Docs, OAuth, provider, KMS, database, or secret-storage services.

## Run

```sh
scripts/run-m5-harness.sh
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
