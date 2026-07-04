# ADR-0001 .env as canonical runtime config store with auto-quoted writes

Status: accepted
Date: 2026-07-03
Owners: 2355287-davecthomas
Must read: true
Supersedes: 
Superseded by: 
ai-generated: True
ai-model: claude-fable-5
ai-tool: claude
ai-surface: claude-code
ai-executor: local-agent

Purpose: .env as canonical runtime config store with auto-quoted writes
Derived from: [2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--env-canonical-runtime-config](../daily/2026-07-03/events/2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--env-canonical-runtime-config.md)

## Context

- The library resolves engines from the environment on every factory call, so runtime provider/model changes must persist somewhere the library re-reads immediately.
- Decision: `.env` is the single source of truth for provider API keys and engine/model selections. All writes go through the `envfile` helper, which uses `quote_mode="auto"` so values with spaces or `#` are quoted while simple values stay bare — keeping the file parseable by both python-dotenv and pydantic-settings.
- A zero-key `.env` is a supported starting state: first use of a provider triggers in-app key onboarding that shows where to get the key, prompts for it, saves it to `.env`, and reloads.

## Decision

- Engine/model/voice switches from any menu persist to `.env` and take effect immediately.
- In-app API-key onboarding writes keys to `.env` with provider key URLs shown to the user.
- `envfile.set_env_values` uses `quote_mode="auto"` after `"never"` was shown to corrupt `.env` for values containing spaces or `#` (root cause in commit b55591c).

## Consequences

- Promote to an ADR: `.env` as canonical runtime config store with the auto-quoting write contract.

## Source memory events

- [2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--env-canonical-runtime-config](../daily/2026-07-03/events/2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--env-canonical-runtime-config.md)

## Related code paths

- src/sample_ai_api_unified/envfile.py
- src/sample_ai_api_unified/onboarding.py
- env_template
