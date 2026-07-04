# ADR-0004 Makefile is the canonical switch between local library checkout and PyPI release

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

Purpose: Makefile is the canonical switch between local library checkout and PyPI release
Derived from: [2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--library-source-switching](../daily/2026-07-03/events/2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--library-source-switching.md)

## Context

- The app exists to exercise `ai-api-unified` both as it is developed (local checkout) and as it ships (PyPI), so the library source must be swappable without editing project files.
- Decision: the Makefile is the canonical switch between the local editable checkout (default, `../ai_api_unified`, overridable via `LOCAL_LIB`) and the latest PyPI release; `make which` reports the active source. Neither pyproject nor code hardcodes one source.

## Decision

- `make setup-local` installs app deps plus an editable install of the local library checkout; `make setup-pypi` installs the latest release.
- `make run` uses the local checkout by default; `make run-pypi` upgrades to the latest PyPI release first; `make which` prints the active library source and version.
- Both setup targets install every provider extra and the spaCy model, so capability coverage is identical across sources.

## Consequences

- Promote to an ADR as a foundational dependency-management decision for this sample repo.

## Source memory events

- [2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--library-source-switching](../daily/2026-07-03/events/2026-07-03T15-26-49Z--2355287-davecthomas--bootstrap--library-source-switching.md)

## Related code paths

- Makefile
- pyproject.toml
- README.md
