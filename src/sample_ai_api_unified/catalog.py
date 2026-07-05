"""Static catalog of capabilities, engines, models, and provider credentials.

Engine selector strings and model lists mirror the ai-api-unified provider
registry (src/ai_api_unified/ai_provider_registry.py). Users can always type a
custom model name, so these lists are conveniences rather than gates.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class EnvKey:
    name: str
    secret: bool = True
    optional: bool = False
    default: str = ""
    # When set, the value must name an existing file (e.g. a service-account
    # JSON), not just be non-empty.
    must_be_file: bool = False


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    env_keys: tuple[EnvKey, ...]
    key_url: str
    note: str = ""


PROVIDERS: dict[str, Provider] = {
    "openai": Provider(
        key="openai",
        label="OpenAI",
        env_keys=(EnvKey("OPENAI_API_KEY"),),
        key_url="https://platform.openai.com/api-keys",
    ),
    "google": Provider(
        key="google",
        label="Google Gemini",
        env_keys=(
            EnvKey("GOOGLE_GEMINI_API_KEY"),
            EnvKey("GOOGLE_AUTH_METHOD", secret=False, optional=True, default="api_key"),
        ),
        key_url="https://aistudio.google.com/apikey",
    ),
    "aws": Provider(
        key="aws",
        label="AWS Bedrock",
        env_keys=(
            EnvKey("AWS_ACCESS_KEY_ID", secret=False),
            EnvKey("AWS_SECRET_ACCESS_KEY"),
            EnvKey("AWS_SESSION_TOKEN", optional=True),
            EnvKey("AWS_REGION", secret=False, optional=True, default="us-east-1"),
        ),
        key_url="https://console.aws.amazon.com/iam/home#/security_credentials",
        note="Session tokens expire; refresh them if Bedrock calls start failing.",
    ),
    "azure": Provider(
        key="azure",
        label="Azure Speech",
        env_keys=(
            EnvKey("MICROSOFT_COGNITIVE_SERVICES_API_KEY"),
            EnvKey("MICROSOFT_COGNITIVE_SERVICES_REGION", secret=False),
        ),
        key_url="https://portal.azure.com/#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub/~/SpeechServices",
    ),
    "elevenlabs": Provider(
        key="elevenlabs",
        label="ElevenLabs",
        env_keys=(EnvKey("ELEVEN_LABS_API_KEY"),),
        key_url="https://elevenlabs.io/app/settings/api-keys",
    ),
}


@dataclass(frozen=True)
class Engine:
    selector: str
    provider: str
    models: tuple[str, ...] = ()
    default_model: str = ""
    note: str = ""


@dataclass(frozen=True)
class Capability:
    key: str
    label: str
    engine_env: str
    model_env: str
    engines: tuple[Engine, ...] = field(default=())


CAPABILITIES: dict[str, Capability] = {
    "completions": Capability(
        key="completions",
        label="Completions",
        engine_env="COMPLETIONS_ENGINE",
        model_env="COMPLETIONS_MODEL_NAME",
        engines=(
            Engine(
                "openai",
                "openai",
                (
                    "gpt-5",
                    "gpt-5-mini",
                    "gpt-5-nano",
                    "gpt-4.1",
                    "gpt-4.1-mini",
                    "gpt-4.1-nano",
                    # o4-mini-high (in the library's list) is a ChatGPT UI label,
                    # not an API model ID, so it is deliberately omitted here.
                    "o4-mini",
                    "gpt-4o",
                    "gpt-4o-mini",
                ),
                "gpt-4o-mini",
            ),
            Engine(
                "google-gemini",
                "google",
                (
                    "gemini-2.5-pro",
                    "gemini-2.5-flash",
                    "gemini-2.5-flash-lite",
                    "gemini-2.0-flash",
                    "gemini-2.0-flash-001",
                    "gemini-2.0-flash-lite",
                    "gemini-2.0-flash-lite-001",
                    "gemini-1.5-pro-002",
                    "gemini-1.5-flash-002",
                ),
                "gemini-2.5-flash",
            ),
            Engine(
                "nova",
                "aws",
                (
                    "amazon.nova-micro-v1:0",
                    "amazon.nova-lite-v1:0",
                    "amazon.nova-pro-v1:0",
                    "amazon.nova-premier-v1:0",
                ),
                "amazon.nova-lite-v1:0",
                note="Routed through AWS Bedrock",
            ),
            Engine(
                "anthropic",
                "aws",
                ("us.anthropic.claude-3-5-haiku-20241022-v1:0",),
                "us.anthropic.claude-3-5-haiku-20241022-v1:0",
                note="Routed through AWS Bedrock",
            ),
            Engine(
                "llama",
                "aws",
                # us.-prefixed cross-region inference profiles; on-demand
                # invocation of the bare meta.* IDs is rejected in most regions.
                ("us.meta.llama3-1-70b-instruct-v1:0", "us.meta.llama3-1-8b-instruct-v1:0"),
                "us.meta.llama3-1-8b-instruct-v1:0",
                note="Bedrock alias; any Bedrock Llama model ID works",
            ),
            Engine(
                "mistral",
                "aws",
                ("mistral.mistral-large-2402-v1:0", "mistral.mistral-small-2402-v1:0"),
                "mistral.mistral-small-2402-v1:0",
                note="Bedrock alias; any Bedrock Mistral model ID works",
            ),
            Engine(
                "cohere",
                "aws",
                ("cohere.command-r-plus-v1:0", "cohere.command-r-v1:0"),
                "cohere.command-r-v1:0",
                note="Bedrock alias; any Bedrock Cohere model ID works",
            ),
            Engine(
                "ai21",
                "aws",
                # AWS lists the Jamba 1.5 models as legacy, so no default is
                # suggested; enter a current Bedrock AI21 model ID.
                (),
                "",
                note="Bedrock alias; enter a current Bedrock AI21 model ID",
            ),
        ),
    ),
    "embeddings": Capability(
        key="embeddings",
        label="Embeddings",
        engine_env="EMBEDDING_ENGINE",
        model_env="EMBEDDING_MODEL_NAME",
        engines=(
            Engine(
                "openai",
                "openai",
                ("text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"),
                "text-embedding-3-small",
            ),
            Engine(
                "google-gemini",
                "google",
                ("gemini-embedding-001", "gemini-embedding-2"),
                "gemini-embedding-001",
                note="gemini-embedding-2 adds multimodal input",
            ),
            Engine(
                "titan",
                "aws",
                ("amazon.titan-embed-text-v2:0", "amazon.titan-embed-text-v1"),
                "amazon.titan-embed-text-v2:0",
                note="Routed through AWS Bedrock",
            ),
        ),
    ),
    "images": Capability(
        key="images",
        label="Image generation",
        engine_env="IMAGE_ENGINE",
        model_env="IMAGE_MODEL_NAME",
        engines=(
            Engine("openai", "openai", ("gpt-image-1", "dall-e-3", "dall-e-2"), "gpt-image-1"),
            Engine(
                "google-gemini",
                "google",
                (
                    "imagen-4.0-generate-001",
                    "imagen-4.0-fast-generate-001",
                    "imagen-4.0-ultra-generate-001",
                    "gemini-2.5-flash-image",
                    "gemini-3-pro-image-preview",
                    "gemini-3.1-flash-image-preview",
                ),
                "imagen-4.0-generate-001",
            ),
            Engine(
                "nova-canvas",
                "aws",
                ("amazon.nova-canvas-v1:0",),
                "amazon.nova-canvas-v1:0",
                note="Routed through AWS Bedrock",
            ),
        ),
    ),
    "videos": Capability(
        key="videos",
        label="Video generation",
        engine_env="VIDEO_ENGINE",
        model_env="VIDEO_MODEL_NAME",
        engines=(
            Engine("openai", "openai", ("sora-2", "sora-2-pro"), "sora-2"),
            Engine(
                "google-gemini",
                "google",
                (
                    # veo-3.1-*-preview models are not published on Vertex
                    # (they 404), so the catalog lists only GA models that run.
                    "veo-3.0-generate-001",
                    "veo-3.0-fast-generate-001",
                    "veo-2.0-generate-001",
                ),
                # The library's own DEFAULT_VIDEO_MODEL is a preview model that
                # Vertex rejects with 404 (not a published model). Default to a
                # GA model so video generation is runnable out of the box.
                "veo-3.0-fast-generate-001",
            ),
            Engine(
                "nova-reel",
                "aws",
                ("amazon.nova-reel-v1:1",),
                "amazon.nova-reel-v1:1",
                note="Requires BEDROCK_VIDEO_OUTPUT_S3_URI",
            ),
        ),
    ),
    "voice": Capability(
        key="voice",
        label="Voice (TTS / STT)",
        engine_env="AI_VOICE_ENGINE",
        model_env="DEFAULT_GEMINI_TTS_MODEL",
        engines=(
            Engine(
                "openai",
                "openai",
                note="TTS models tts-1-hd / tts-1 / gpt-4o-mini-tts; STT whisper-1",
            ),
            Engine(
                "google",
                "google",
                # No default_model: selecting the engine must not overwrite a
                # user's DEFAULT_GEMINI_TTS_MODEL; the model submenu still
                # offers these.
                ("gemini-2.5-pro-tts", "gemini-2.5-flash-tts"),
                note="Model set via DEFAULT_GEMINI_TTS_MODEL",
            ),
            Engine("azure", "azure"),
            Engine("elevenlabs", "elevenlabs"),
        ),
    ),
}


def engine_for(capability_key: str, selector: str) -> Engine | None:
    for engine in CAPABILITIES[capability_key].engines:
        if engine.selector == selector:
            return engine
    return None


def provider_for_engine(capability_key: str, selector: str) -> Provider | None:
    engine = engine_for(capability_key, selector)
    return PROVIDERS.get(engine.provider) if engine else None


# In service-account mode the library authenticates with a JSON credentials
# file and never reads GOOGLE_GEMINI_API_KEY, so the API key is not required.
GOOGLE_SERVICE_ACCOUNT_KEYS: tuple[EnvKey, ...] = (
    EnvKey("GOOGLE_APPLICATION_CREDENTIALS", secret=False, must_be_file=True),
)


def google_uses_service_account() -> bool:
    """True when Google auth is configured for service-account credentials
    (GOOGLE_APPLICATION_CREDENTIALS) rather than an API key."""
    return os.environ.get("GOOGLE_AUTH_METHOD", "api_key").strip().lower() == "service_account"


# Backwards-compatible private alias.
_google_uses_service_account = google_uses_service_account


def required_env_keys(provider: Provider) -> tuple[EnvKey, ...]:
    """The env keys a provider needs, honoring Google's service-account mode
    where GOOGLE_APPLICATION_CREDENTIALS replaces the API key."""
    if provider.key == "google" and _google_uses_service_account():
        return GOOGLE_SERVICE_ACCOUNT_KEYS
    return provider.env_keys


def missing_keys(provider: Provider) -> list[EnvKey]:
    missing: list[EnvKey] = []
    for key in required_env_keys(provider):
        if key.optional:
            continue
        value = os.environ.get(key.name, "").strip()
        if not value or (key.must_be_file and not Path(value).is_file()):
            missing.append(key)
    return missing


def provider_configured(provider: Provider) -> bool:
    return not missing_keys(provider)
