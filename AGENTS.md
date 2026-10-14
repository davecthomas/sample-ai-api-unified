# AGENTS.md

Guide for AI coding agents working in this repository.

## What this repo is

`sample-ai-api-unified` is a runnable Python sample app for the
[`ai-api-unified`](https://pypi.org/project/ai-api-unified/) library. It is a
Textual terminal UI (TUI) that calls real providers (OpenAI, Anthropic Claude,
Google Gemini, AWS Bedrock, Azure, ElevenLabs) through the library's single API.
Each screen covers one capability: completions, conversations with tool calling,
structured output, embeddings, image generation, video generation, voice,
middleware, and providers. The providers screen also sets up model fallback.

It is a demo and a manual test bed for the library, not a library itself.

## Layout

- `src/sample_ai_api_unified/tui/screens/` — one screen per capability
- `src/sample_ai_api_unified/catalog.py` — engines and models offered in the
  menus; `tests/test_catalog_registry_sync.py` keeps it in sync with the library
- `src/sample_ai_api_unified/state.py`, `envfile.py` — runtime engine/model
  selection, persisted to `.env` and applied to `os.environ`
- `src/sample_ai_api_unified/fallback.py` — model fallback chain settings
  (`COMPLETIONS_FALLBACKS`, `COMPLETIONS_FALLBACK_ON`)
- `env_template` — every setting the app reads, with comments

## How the library is wired

The library reads its configuration from the environment on every
`AIFactory` call. The app changes engines, models, retry policy, and the
fallback chain by writing `.env` and `os.environ`. It does not pass
constructor arguments.

The library is not declared in `pyproject.toml`. `make use-local` installs the
sibling `../ai_api_unified` checkout in editable mode, and `make use-pypi`
installs the latest release.

## Commands

```bash
make setup-local   # deps + editable local library with all extras
make run           # launch the TUI
make test          # offline unit tests (no network, no API keys)
make lint          # ruff + black --check
```

Tests must stay offline: fake the factory with `monkeypatch`, as
`tests/test_conversation.py` and `tests/test_fallback.py` do.
