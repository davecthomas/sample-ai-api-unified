# ADR-0003 Middleware configured via menu-generated YAML; UI inverts allowed_entities to a redact-list

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

Purpose: Middleware configured via menu-generated YAML; UI inverts allowed_entities to a redact-list
Derived from: [2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--middleware-yaml-profile-contract](../daily/2026-07-03/events/2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--middleware-yaml-profile-contract.md)

## Context

- The library consumes middleware config as YAML via `AI_MIDDLEWARE_CONFIG_PATH`; hand-editing YAML is error-prone in a demo setting.
- Decision: the middleware profile is edited exclusively through menus, and the app generates the YAML the library expects at `config/middleware.yaml`, pointing `AI_MIDDLEWARE_CONFIG_PATH` at it. The generated file, not the menus' in-memory state, is the contract with the library.
- Semantics decision: the library's `allowed_entities` field means "allowed through unredacted". The app deliberately inverts this at the UI boundary — users pick "entities to redact" and the app writes the complement — because redact-lists match user intuition even though the library speaks allow-lists.
- Corollary invariant (from the c6ba753 fix): any profile mutation the user confirms must be applied to the profile object before write-back; re-writing the just-read profile silently drops the change.

## Decision

- Menu-driven middleware profile editor generating `config/middleware.yaml`.
- Live observability event pane showing metadata-only input/output/error events per call.
- PII redaction demos over fabricated PII, with a live echo test proving providers only receive redacted text.
- Fix: `_ensure_observability_enabled` now flips `observability.enabled` to True before writing the profile.

## Consequences

- Promote to an ADR: menu-generated YAML as the middleware config contract, including the redaction-semantics inversion.

## Source memory events

- [2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--middleware-yaml-profile-contract](../daily/2026-07-03/events/2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--middleware-yaml-profile-contract.md)

## Related code paths

- src/sample_ai_api_unified/middleware_profile.py
- src/sample_ai_api_unified/demos/middleware_demo.py
- config/README.md
