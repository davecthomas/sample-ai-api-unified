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

The menus cover every provider implementation and every model each one lists;
the registry's remaining synonyms (`bedrock`/`nova` aliases, `rerank`,
`canvas`) route to the same providers and are reachable through the custom
engine option:

| Capability | Engines |
| --- | --- |
| Completions | `openai` (GPT-5/4.1/o4/4o families), `google-gemini` (all nine Gemini spec models), and the Bedrock-routed `nova`, `anthropic`, `llama`, `mistral`, `cohere`, `ai21` |
| Embeddings | `openai` (3 models), `google-gemini` (`gemini-embedding-001`, multimodal `gemini-embedding-2`), `titan` (v1, v2) |
| Images | `openai` (`gpt-image-1`, DALL-E 2/3), `google-gemini` (Imagen 4 standard/fast/ultra, Gemini image models), `nova-canvas` |
| Videos | `openai` (`sora-2`, `sora-2-pro`), `google-gemini` (all six Veo models), `nova-reel` |
| Voice | `openai`, `google` (Gemini TTS models), `azure`, `elevenlabs` |

Every model menu also takes a custom model name, so new releases are usable
before this catalog updates. A registry-sync test
(`tests/test_catalog_registry_sync.py`) fails if the catalog drifts from the
installed library.

## Middleware

The **Middleware** menu edits a profile through menus, writes the YAML the
library expects to `config/middleware.yaml`, and points
`AI_MIDDLEWARE_CONFIG_PATH` at it.

- **Observability**: metadata-only input/output/error events per call, shown
  live in the console pane and after each call.
- **PII redaction**: before/after tables over fabricated PII samples, plus a
  live echo test proving the provider only ever receives redacted text.

## Troubleshooting

- **Google voice returns 403 "Cloud Text-to-Speech API has not been used in
  project N before or it is disabled"**: the library serves all Google voices
  (including `gemini-*-tts`) through the Cloud Text-to-Speech API, which must
  be enabled on the project that owns your `GOOGLE_GEMINI_API_KEY`. Sign in
  with the Google account that created the key and enable it at
  `https://console.developers.google.com/apis/api/texttospeech.googleapis.com/overview?project=<N>`
  (the exact URL, with your project number, is printed in the error). Keys
  created in AI Studio belong to that account's auto-created
  `gen-lang-client-*` project.
- **Bedrock engines fail with credential errors**: AWS session tokens
  (`AWS_SESSION_TOKEN`) expire; refresh them and update `.env` via the
  Providers & models menu.
- **OpenAI voice**: ai-api-unified 2.6.0's `AIVoiceOpenAI` references an
  undefined `user` field; the app shims it at client creation until the
  library ships a fix.
- **Imagen or Veo failures on a fresh key**: image and video generation need
  a billing-enabled Google project; free-tier AI Studio keys may be rejected.

## Development

```bash
make test      # unit tests (no network)
make lint      # ruff + black --check
make format
make assets    # regenerate the bundled sample images
```

## License

MIT
