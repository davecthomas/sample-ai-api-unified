"""Menu-driven middleware profile editor.

Users pick settings from menus; this module renders them to the YAML shape
ai-api-unified expects (middleware_config.py) and points
AI_MIDDLEWARE_CONFIG_PATH at the generated file. Nobody edits YAML by hand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import envfile, paths

DIRECTIONS = ("input_only", "output_only", "input_output")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
DETECTION_PROFILES = ("low_memory", "balanced", "high_accuracy")
PII_ENTITIES = ("NAME", "PHONE", "EMAIL", "SSN", "ADDRESS", "DOB", "CC_LAST4")


@dataclass(frozen=True)
class ObservabilityProfile:
    enabled: bool = True
    direction: str = "input_output"
    capabilities: tuple[str, ...] = ()  # empty tuple means all capabilities
    log_level: str = "INFO"
    token_count_mode: str = "provider_or_estimate"
    emit_error_events: bool = True


@dataclass(frozen=True)
class PiiProfile:
    enabled: bool = False
    direction: str = "input_only"
    strict_mode: bool = False
    detection_profile: str = "balanced"
    default_redaction_label: str = "REDACTED"
    # Entities the user wants redacted. The library YAML expresses the inverse:
    # its `allowed_entities` are categories allowed through UNredacted.
    redact_entities: tuple[str, ...] = PII_ENTITIES


@dataclass(frozen=True)
class MiddlewareProfile:
    observability: ObservabilityProfile = field(default_factory=ObservabilityProfile)
    pii: PiiProfile = field(default_factory=PiiProfile)


def to_yaml_dict(profile: MiddlewareProfile) -> dict:
    observability_settings: dict = {
        "direction": profile.observability.direction,
        "log_level": profile.observability.log_level,
        "token_count_mode": profile.observability.token_count_mode,
        "emit_error_events": profile.observability.emit_error_events,
    }
    if profile.observability.capabilities:
        observability_settings["capabilities"] = list(profile.observability.capabilities)

    pii_settings: dict = {
        "direction": profile.pii.direction,
        "strict_mode": profile.pii.strict_mode,
        "detection_profile": profile.pii.detection_profile,
        "default_redaction_label": profile.pii.default_redaction_label,
        "allowed_entities": [
            entity for entity in PII_ENTITIES if entity not in profile.pii.redact_entities
        ],
    }

    return {
        "middleware": [
            {
                "name": "observability",
                "enabled": profile.observability.enabled,
                "settings": observability_settings,
            },
            {
                "name": "pii_redaction",
                "enabled": profile.pii.enabled,
                "settings": pii_settings,
            },
        ]
    }


# Path defaults resolve at call time (not def time) so paths.MIDDLEWARE_YAML_PATH
# can be redirected by tests or future config.


def write_profile(profile: MiddlewareProfile, path: Path | None = None) -> Path:
    path = path or paths.MIDDLEWARE_YAML_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(to_yaml_dict(profile), sort_keys=False))
    envfile.set_env_values({"AI_MIDDLEWARE_CONFIG_PATH": str(path)})
    return path


def read_profile(path: Path | None = None) -> MiddlewareProfile:
    path = path or paths.MIDDLEWARE_YAML_PATH
    if not path.exists():
        return MiddlewareProfile()
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return MiddlewareProfile()

    observability = ObservabilityProfile()
    pii = PiiProfile()
    for entry in data.get("middleware", []):
        settings = entry.get("settings") or {}
        if entry.get("name") == "observability":
            observability = ObservabilityProfile(
                enabled=bool(entry.get("enabled", False)),
                direction=settings.get("direction") or observability.direction,
                # `or ()` also covers a present-but-null YAML key, which the
                # library itself tolerates.
                capabilities=tuple(settings.get("capabilities") or ()),
                log_level=settings.get("log_level", observability.log_level),
                token_count_mode=settings.get("token_count_mode", observability.token_count_mode),
                emit_error_events=bool(
                    settings.get("emit_error_events", observability.emit_error_events)
                ),
            )
        elif entry.get("name") == "pii_redaction":
            pii = PiiProfile(
                enabled=bool(entry.get("enabled", False)),
                direction=settings.get("direction", pii.direction),
                strict_mode=bool(settings.get("strict_mode", pii.strict_mode)),
                detection_profile=settings.get("detection_profile", pii.detection_profile),
                default_redaction_label=settings.get(
                    "default_redaction_label", pii.default_redaction_label
                ),
                redact_entities=tuple(
                    entity
                    for entity in PII_ENTITIES
                    if entity not in (settings.get("allowed_entities") or ())
                ),
            )
    return MiddlewareProfile(observability=observability, pii=pii)
