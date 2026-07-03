# sample-ai-api-unified

A menu-driven console app that exercises every capability of
[`ai-api-unified`](https://pypi.org/project/ai-api-unified/) with real provider
calls. Use it to explore the library, compare providers and models, and see
the middleware system at work.

## What it covers

| Menu | Library surface |
| --- | --- |
| Completions | `AIFactory.get_ai_completions_client()`, `send_prompt`, system prompts, image description via prompt media params |
| Structured responses | `AIStructuredPrompt`, `strict_schema_prompt`, `StructuredResponseTokenLimitError` guard rail |
| Embeddings | `generate_embeddings`, batches, cosine similarity, multimodal embeddings (`gemini-embedding-2`), capabilities descriptor |
| Image generation | `generate_images` with per-provider properties (aspect ratio, size) |
| Video generation | Blocking `generate_video`, explicit submit/poll/download job control, frame extraction |
| Voice | TTS through your speakers with per-provider voice pickers, speech-to-text roundtrip |
| Middleware | Menu-driven profile editor that generates the YAML config, live observability event pane, PII redaction demos with fabricated PII |
| Providers & models | Engine/model switching at runtime, in-app API-key onboarding saved to `.env` |

Every provider call renders a live pane showing elapsed time and, when the
observability middleware is enabled, the metadata events the library emits.

## Requirements

- Python 3.11–3.13 and [Poetry](https://python-poetry.org/)
- macOS `afplay` (or `ffplay`/`aplay` on Linux) for TTS playback
- API keys for the providers you want to try — the app walks you through
  getting and saving each key the first time you use a provider

## Setup

```bash
make setup-local   # app deps + editable install of the local ../ai_api_unified checkout
# or
make setup-pypi    # app deps + latest ai-api-unified release from PyPI
```

Both targets install every provider extra (OpenAI, Google Gemini, Bedrock,
Azure TTS, ElevenLabs, video frames, similarity, PII redaction) and the
`en_core_web_sm` spaCy model used by PII detection.

`make env` seeds `.env` from the local library checkout when one exists,
falling back to `env_template`. A `.env` with zero keys works: when you first
touch a provider, the app shows where to get a key, prompts for it, saves it
to `.env`, and reloads.

## Run

```bash
make run          # local checkout (default)
make run-pypi     # upgrades to the latest PyPI release first, then runs
make which        # print which library source and version is active
```

The local checkout path defaults to `../ai_api_unified`; override with
`make run LOCAL_LIB=/path/to/checkout`.

## Switching providers, models, and voices

Use **Providers & models** (or the switch options inside each capability menu)
to change engines and models at runtime. The library resolves engines from the
environment on every factory call, so changes apply immediately and persist to
`.env`. Voice menus list each provider's real voice catalog and play synthesis
through your speakers; no audio file is kept.

## Middleware

The **Middleware** menu edits a profile through menus, writes the YAML the
library expects to `config/middleware.yaml`, and points
`AI_MIDDLEWARE_CONFIG_PATH` at it.

- **Observability**: metadata-only input/output/error events per call, shown
  live in the console pane and after each call.
- **PII redaction**: before/after tables over fabricated PII samples, plus a
  live echo test proving the provider only ever receives redacted text.

## Development

```bash
make test      # unit tests (no network)
make lint      # ruff + black --check
make format
make assets    # regenerate the bundled sample images
```

## License

MIT
