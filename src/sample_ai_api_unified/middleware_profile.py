"""Menu-driven middleware profile editor.

Users pick settings from menus; this module renders them to the YAML shape
ai-api-unified expects (middleware_config.py) and points
AI_MIDDLEWARE_CONFIG_PATH at the generated file. Nobody edits YAML by hand.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

from . import envfile, paths, ui

DIRECTIONS = ("input_only", "output_only", "input_output")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
TOKEN_COUNT_MODES = ("provider_only", "provider_or_estimate", "none")
OBSERVABILITY_CAPABILITIES = ("completions", "embeddings", "images", "videos", "tts")
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


def write_profile(profile: MiddlewareProfile, path: Path = paths.MIDDLEWARE_YAML_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(to_yaml_dict(profile), sort_keys=False))
    envfile.set_env_values({"AI_MIDDLEWARE_CONFIG_PATH": str(path)})
    return path


def read_profile(path: Path = paths.MIDDLEWARE_YAML_PATH) -> MiddlewareProfile:
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
                direction=settings.get("direction", observability.direction),
                capabilities=tuple(settings.get("capabilities", ())),
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
                    if entity not in settings.get("allowed_entities", ())
                ),
            )
    return MiddlewareProfile(observability=observability, pii=pii)


def _edit_observability(observability: ObservabilityProfile) -> ObservabilityProfile:
    while True:
        picked = ui.choose(
            "Observability settings",
            [
                ui.MenuOption(f"Enabled: {observability.enabled}", "enabled"),
                ui.MenuOption(f"Direction: {observability.direction}", "direction"),
                ui.MenuOption(
                    f"Capabilities: {', '.join(observability.capabilities) or 'all'}",
                    "capabilities",
                ),
                ui.MenuOption(f"Log level: {observability.log_level}", "log_level"),
                ui.MenuOption(f"Token counting: {observability.token_count_mode}", "tokens"),
                ui.MenuOption(f"Emit error events: {observability.emit_error_events}", "errors"),
            ],
            back_label="Done",
        )
        if picked is None:
            return observability
        if picked.value == "enabled":
            observability = replace(observability, enabled=not observability.enabled)
        elif picked.value == "direction":
            choice = ui.choose_value("Direction", DIRECTIONS)
            if choice:
                observability = replace(observability, direction=choice)
        elif picked.value == "capabilities":
            selected = ui.multi_toggle(
                "Capabilities (none selected = all)",
                OBSERVABILITY_CAPABILITIES,
                set(observability.capabilities),
            )
            ordered = tuple(c for c in OBSERVABILITY_CAPABILITIES if c in selected)
            observability = replace(observability, capabilities=ordered)
        elif picked.value == "log_level":
            choice = ui.choose_value("Log level", LOG_LEVELS)
            if choice:
                observability = replace(observability, log_level=choice)
        elif picked.value == "tokens":
            choice = ui.choose_value("Token count mode", TOKEN_COUNT_MODES)
            if choice:
                observability = replace(observability, token_count_mode=choice)
        elif picked.value == "errors":
            observability = replace(
                observability, emit_error_events=not observability.emit_error_events
            )


def _edit_pii(pii: PiiProfile) -> PiiProfile:
    while True:
        picked = ui.choose(
            "PII redaction settings",
            [
                ui.MenuOption(f"Enabled: {pii.enabled}", "enabled"),
                ui.MenuOption(f"Direction: {pii.direction}", "direction"),
                ui.MenuOption(f"Strict mode (fail closed): {pii.strict_mode}", "strict"),
                ui.MenuOption(f"Detection profile: {pii.detection_profile}", "profile"),
                ui.MenuOption(f"Redaction label: {pii.default_redaction_label}", "label"),
                ui.MenuOption(f"Redact: {', '.join(pii.redact_entities) or 'nothing'}", "entities"),
            ],
            back_label="Done",
        )
        if picked is None:
            return pii
        if picked.value == "enabled":
            pii = replace(pii, enabled=not pii.enabled)
        elif picked.value == "direction":
            choice = ui.choose_value("Direction", DIRECTIONS)
            if choice:
                pii = replace(pii, direction=choice)
        elif picked.value == "strict":
            pii = replace(pii, strict_mode=not pii.strict_mode)
        elif picked.value == "profile":
            choice = ui.choose_value("Detection profile", DETECTION_PROFILES)
            if choice:
                if choice == "high_accuracy":
                    ui.warn(
                        "high_accuracy needs the en_core_web_lg spaCy model "
                        "(poetry run python -m spacy download en_core_web_lg)."
                    )
                pii = replace(pii, detection_profile=choice)
        elif picked.value == "label":
            label = ui.ask("Redaction label", default=pii.default_redaction_label)
            if label:
                pii = replace(pii, default_redaction_label=label)
        elif picked.value == "entities":
            selected = ui.multi_toggle("Entities to redact", PII_ENTITIES, set(pii.redact_entities))
            ordered = tuple(e for e in PII_ENTITIES if e in selected)
            pii = replace(pii, redact_entities=ordered)


def edit_profile() -> MiddlewareProfile:
    """Full profile editor loop; saves and applies on exit."""
    profile = read_profile()
    while True:
        picked = ui.choose(
            "Middleware profile editor",
            [
                ui.MenuOption(
                    f"Observability ({'on' if profile.observability.enabled else 'off'})",
                    "observability",
                ),
                ui.MenuOption(f"PII redaction ({'on' if profile.pii.enabled else 'off'})", "pii"),
                ui.MenuOption("Save and apply", "save"),
            ],
            back_label="Cancel",
        )
        if picked is None:
            ui.warn("Profile changes discarded.")
            return read_profile()
        if picked.value == "observability":
            profile = replace(profile, observability=_edit_observability(profile.observability))
        elif picked.value == "pii":
            profile = replace(profile, pii=_edit_pii(profile.pii))
        elif picked.value == "save":
            path = write_profile(profile)
            ui.success(f"Profile written to {path} and AI_MIDDLEWARE_CONFIG_PATH updated.")
            return profile
