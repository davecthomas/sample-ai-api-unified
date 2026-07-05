# sample-ai-api-unified

A **Textual full-screen TUI** that exercises every capability of
[`ai-api-unified`](https://pypi.org/project/ai-api-unified/) with real provider
calls. Use it to explore the library, compare providers and models, and see
the middleware system at work.

The TUI has sidebar navigation, a collapsible observability pane, and modal
dialogs, with a screen for each capability: completions, structured responses,
embeddings, image generation, video generation, voice, middleware, and
providers/config. On every screen the controls sit at the top, the primary
action button sits directly below the input it acts on, and the response fills
the rest of the height in its own scrollable region so long completions are
never clipped. The observability pane collapses by default (toggle with `o`) to
keep that space for the response.

## What it covers

| Capability | Library surface |
| --- | --- |
| Completions | `AIFactory.get_ai_completions_client()`, `send_prompt`, `send_prompt_streaming` (live token streaming), system prompts, image description via prompt media params |
| Structured responses | `AIStructuredPrompt`, `strict_schema_prompt`, `StructuredResponseTokenLimitError` guard rail |
| Embeddings | `generate_embeddings`, batches, cosine similarity, multimodal embeddings (`gemini-embedding-2`), capabilities descriptor |
| Image generation | `generate_images` with per-provider properties (aspect ratio, size) |
| Video generation | Blocking `generate_video`, explicit submit/poll/download job control, frame extraction |
| Voice | TTS through your speakers with per-provider voice pickers, speech-to-text roundtrip |
| Middleware | Form-based profile editor that generates the YAML config, live observability event pane, PII redaction demos with fabricated PII |
| Providers & models | Engine/model switching at runtime, in-app API-key onboarding saved to `.env` |

Every provider call renders a live pane showing elapsed time and, when the
observability middleware is enabled, the metadata events the library emits.

In the TUI, the completions, structured, image, video, and voice screens each
have a **Generate** button that uses the completions API to write a fresh
sample prompt (or, for structured, a fresh source text). Every screen also
shows the exact prompt sent to the provider alongside its result — the
structured screen displays the full `strict_schema_prompt` text.

The completions screen has both **Send** (the full reply arrives at once) and
**Stream** (`send_prompt_streaming`), which renders the response token by token
as the provider produces it, with a live cursor and a final chunk count. Ask for
something longer (a story, an explanation) to watch it arrive. Streaming is
unavailable while PII redaction middleware is enabled — the library cannot
guarantee redaction across chunk boundaries — and the screen says so if you try.

The embeddings screen's **Related & rank** button ties the two capabilities
together: enter a phrase (e.g. "dogs like to sniff things"), and the completions
model writes five topically related sentences, each is embedded, and the screen
lists them ranked by cosine similarity to your phrase — a hands-on view of what
embedding distance measures.

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

### Google authentication

Google has two auth modes, selected by `GOOGLE_AUTH_METHOD`. Set up whichever
mode you use:

- **`api_key`** (default) — set `GOOGLE_GEMINI_API_KEY`.
- **`service_account`** — set `GOOGLE_APPLICATION_CREDENTIALS` to a
  service-account JSON key file (plus `GOOGLE_PROJECT_ID` and `GOOGLE_LOCATION`);
  `GOOGLE_GEMINI_API_KEY` is then unused for auth.

Which mode each Google capability requires (and the same table for every other
provider's key requirements) is a library-level constraint, documented in the
[`ai-api-unified` README's Google authentication section](https://github.com/davecthomas/ai-api-unified#readme).
The short version: voice needs `service_account`, while multimodal-image
embeddings and video-with-download need `api_key`.

To reconcile that split, this app lets you keep `service_account` as your base
(for voice) and also set a `GOOGLE_GEMINI_API_KEY`: the Multimodal and Video
screens then run just those two calls under a temporary `api_key` override,
restoring `GOOGLE_AUTH_METHOD` afterward. Nothing is persisted, so your saved
defaults never change.

The app recognizes both modes: in `service_account` mode Google reads as
configured once the credentials file exists, without prompting for an API key.
Keep the JSON key file out of version control (`*.json` is gitignored).

## Run

```bash
make run          # Textual TUI, local checkout (default)
make run-pypi     # upgrades to the latest PyPI release first, then runs the TUI
make which        # print which library source and version is active
```

The local checkout path defaults to `../ai_api_unified`; override with
`make run LOCAL_LIB=/path/to/checkout`.

### TUI key bindings

| Key | Action |
| --- | --- |
| `c` | Completions screen |
| `e` | Embeddings screen |
| `p` | Providers & models screen |
| `o` | Expand/collapse the observability pane |
| `y` | Copy the current result (or error) to the clipboard |
| `q` | Quit |
| `Ctrl+P` | Command palette |

Click a sidebar entry or use the keys above to switch screens. Buttons and list
items respond to both mouse and keyboard. Long provider calls run on a
background thread so the UI stays responsive, and the collapsible pane streams
observability events when that middleware is enabled — press `o` (or click its
header) to open it.

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
| Videos | `openai` (`sora-2`, `sora-2-pro`), `google-gemini` (Developer-API Veo models: `veo-3.1-generate-preview`, `veo-3.1-fast-generate-preview`, `veo-3.1-lite-generate-preview`), `nova-reel` |
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

- **Google voice fails with 403/401 under an API key**: the Gemini TTS/STT
  endpoints reject API keys ("API keys are not supported by this API" or
  "Expected OAuth2 access token"). Use `GOOGLE_AUTH_METHOD=service_account`
  with a service-account JSON key (see [Google authentication](#google-authentication))
  on a project where the Cloud Text-to-Speech, Cloud Speech-to-Text, and
  Vertex AI APIs are enabled and billing is attached.
- **Google 403 "API has not been used in project N before or it is disabled"**:
  enable the named API on that project at
  `https://console.developers.google.com/apis/api/<service>/overview?project=<N>`
  (the exact URL is printed in the error), then retry after a minute.
- **Bedrock engines fail with credential errors**: AWS session tokens
  (`AWS_SESSION_TOKEN`) expire; refresh them and update `.env` via the
  Providers & models menu.
- **OpenAI voice**: ai-api-unified 2.6.0's `AIVoiceOpenAI` references an
  undefined `user` field; the app shims it at client creation until the
  library ships a fix.
- **Imagen or Veo failures on a fresh key**: image and video generation need
  a billing-enabled Google project; free-tier AI Studio keys may be rejected.
- **`Model is not found: models/veo-...` (404)**: the two Google clients serve
  different Veo catalogs — the Developer (api-key) client has the `veo-3.1-*`
  preview family, while `veo-3.0-*`/`veo-2.0-*` GA names are Vertex-only. The
  app's video path always calls through the Developer client (its download needs
  the Files API), so the catalog lists the `veo-3.1-*` models and the video
  screen heals a stale Vertex-only `VIDEO_MODEL_NAME` to the Developer-API
  default before the call.
- **`This method is only supported in the Gemini Developer client` (video)**:
  Google video download needs `api_key` auth (see the library's Google
  authentication section, linked above). Under `service_account`, the video
  screen runs the call with a temporary `api_key` override when
  `GOOGLE_GEMINI_API_KEY` is set (restored afterward); with no key set it says so.

## Logs

The app writes a datestamped observability log to `./logs/observability-<date>.log`
(gitignored) each session. It captures the middleware's observability events plus
the library's own INFO/ERROR output, so a failed call — a video download, a
provider init error — can be inspected after the fact. The path is also recorded
as the first line in the observability pane.

## Development

```bash
make test      # unit tests (no network)
make lint      # ruff + black --check
make format
make assets    # regenerate the bundled sample images
```

## License

MIT
