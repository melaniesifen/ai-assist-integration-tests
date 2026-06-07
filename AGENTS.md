# AGENTS.md

## Repo Instructions

- This repo owns local cross-repo integration harnesses for AI Assist milestone flows.
- Keep harnesses deterministic and dependency-light.
- Do not call real cloud, Google Docs, OAuth, provider, KMS, database, or secret-storage services.
- Prefer Python stdlib unless a milestone explicitly needs a browser or package dependency.
- Add sibling service repos to `sys.path` only inside harness/test bootstrap code; do not vendor service code here.
- Keep runtime class, DTO, event, CSS, and log names product-generic. Milestone labels may appear in docs, test names, script names, and demo text.
- Keep local prompts, feedback, logs, coverage, dependency, and build output out of git history.

## Checks

Run:

```sh
scripts/run-m5-harness.sh
```
