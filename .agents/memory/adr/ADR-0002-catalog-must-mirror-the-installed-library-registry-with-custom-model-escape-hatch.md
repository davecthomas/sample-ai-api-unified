# ADR-0002 Catalog must mirror the installed library registry, with custom-model escape hatch

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

Purpose: Catalog must mirror the installed library registry, with custom-model escape hatch
Derived from: [2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--catalog-registry-sync-invariant](../daily/2026-07-03/events/2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--catalog-registry-sync-invariant.md)

## Context

- The app maintains its own catalog (`catalog.py`) of engines and models so menus can render without network calls, but a stale catalog would silently misrepresent the library.
- Decision: the catalog must expose every engine the library registry accepts and every model each provider implementation lists, and this invariant is enforced mechanically — a registry-sync test fails CI when the catalog drifts from the installed library.
- Companion decision: every model menu also accepts a custom model name, so newly released models are usable before the catalog updates. Catalog completeness is enforced, but the catalog is never a gate.

## Decision

- `catalog.py` enumerates engines and models per capability (completions, embeddings, images, videos, voice).
- `tests/test_catalog_registry_sync.py` asserts catalog/registry parity against the installed library version.
- All model menus take free-form custom model names.

## Consequences

- Promote to an ADR: catalog-registry parity invariant with custom-model escape hatch.

## Source memory events

- [2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--catalog-registry-sync-invariant](../daily/2026-07-03/events/2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--catalog-registry-sync-invariant.md)

## Related code paths

- src/sample_ai_api_unified/catalog.py
