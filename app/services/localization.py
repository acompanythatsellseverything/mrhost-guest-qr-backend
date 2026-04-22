from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException, status

from app.core.config import Settings, get_settings
from app.schemas.localization import DEFAULT_TARGET_LANGUAGES, LocalizationKind


def _normalize_language_code(code: str) -> str:
    return code.strip().lower()


def _extract_targets(target_languages: list[str]) -> list[str]:
    requested = [_normalize_language_code(code) for code in target_languages if code.strip()]
    seen: set[str] = set()
    targets: list[str] = []

    for code in requested or DEFAULT_TARGET_LANGUAGES:
        if code == "en" or code in seen:
            continue
        seen.add(code)
        targets.append(code)

    return targets


def _validate_source_translation(kind: LocalizationKind, source_translation: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(source_translation)
    language_code = _normalize_language_code(str(normalized.get("language_code", "")))
    if language_code != "en":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An English translation is required as the source.",
        )

    normalized["language_code"] = "en"

    required_fields: dict[LocalizationKind, list[str]] = {
        LocalizationKind.CONSENT: ["title", "body"],
        LocalizationKind.FAQ: ["question", "answer"],
        LocalizationKind.TUTORIAL: ["title", "video_url"],
        LocalizationKind.PAGE_DESCRIPTION: ["body"],
    }

    missing = [field for field in required_fields[kind] if not str(normalized.get(field, "")).strip()]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"English source is missing required fields: {', '.join(missing)}",
        )

    if kind == LocalizationKind.FAQ:
        links = normalized.get("links") or []
        normalized["links"] = [
            {"label": str(link.get("label", "")), "url": str(link.get("url", ""))}
            for link in links
            if isinstance(link, dict)
        ]
    elif kind == LocalizationKind.TUTORIAL:
        normalized["description"] = str(normalized.get("description") or "")
        normalized["thumbnail_url"] = str(normalized.get("thumbnail_url") or "")

    return normalized


def _normalize_existing_translations(
    kind: LocalizationKind, existing_translations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    normalized_existing: list[dict[str, Any]] = []

    for translation in existing_translations:
        if not isinstance(translation, dict):
            continue

        code = _normalize_language_code(str(translation.get("language_code", "")))
        if not code or code == "en":
            continue

        entry = dict(translation)
        entry["language_code"] = code

        if kind == LocalizationKind.FAQ:
            links = entry.get("links") or []
            entry["links"] = [
                {"label": str(link.get("label", "")), "url": str(link.get("url", ""))}
                for link in links
                if isinstance(link, dict)
            ]
        elif kind == LocalizationKind.TUTORIAL:
            entry["description"] = str(entry.get("description") or "")
            entry["thumbnail_url"] = str(entry.get("thumbnail_url") or "")

        normalized_existing.append(entry)

    return normalized_existing


def _build_output_schema(kind: LocalizationKind) -> dict[str, Any]:
    if kind == LocalizationKind.CONSENT:
        translation_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "language_code": {"type": "string"},
                "title": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["language_code", "title", "body"],
        }
    elif kind == LocalizationKind.FAQ:
        translation_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "language_code": {"type": "string"},
                "question": {"type": "string"},
                "answer": {"type": "string"},
                "links": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "label": {"type": "string"},
                            "url": {"type": "string"},
                        },
                        "required": ["label", "url"],
                    },
                },
            },
            "required": ["language_code", "question", "answer", "links"],
        }
    elif kind == LocalizationKind.TUTORIAL:
        translation_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "language_code": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "video_url": {"type": "string"},
                "thumbnail_url": {"type": "string"},
            },
            "required": ["language_code", "title", "description", "video_url", "thumbnail_url"],
        }
    else:
        translation_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "language_code": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["language_code", "body"],
        }

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "translations": {
                "type": "array",
                "items": translation_schema,
            }
        },
        "required": ["translations"],
    }


def _build_prompt(
    kind: LocalizationKind,
    source_translation: dict[str, Any],
    existing_translations: list[dict[str, Any]],
    target_languages: list[str],
) -> str:
    kind_descriptions = {
        LocalizationKind.CONSENT: "guest consent form copy with title and body",
        LocalizationKind.FAQ: "guest FAQ content with question, answer, and optional related links",
        LocalizationKind.TUTORIAL: "guest tutorial content with title, description, and media URLs",
        LocalizationKind.PAGE_DESCRIPTION: "guest-facing page description copy",
    }

    return (
        "You are a localization assistant for a hospitality guest portal.\n"
        f"The content type is {kind_descriptions[kind]}.\n"
        "English is the canonical source. Translate the English source into the requested languages.\n"
        "Existing non-English translations may be incomplete or outdated. Use them only as reference for terminology.\n"
        "When the English source changes, update the target languages to match the English meaning.\n"
        "Preserve meaning, tone, line breaks, placeholders, and formatting.\n"
        "Do not invent details that are not present in the English source.\n"
        "Keep URLs exactly unchanged.\n"
        "For FAQ links, translate the label text but keep each URL identical.\n"
        "For tutorials, keep video_url and thumbnail_url identical to the English source.\n"
        "Return exactly one translation object for each requested target language.\n"
        f"Requested languages: {', '.join(target_languages)}.\n"
        f"English source JSON: {json.dumps(source_translation, ensure_ascii=False)}\n"
        f"Existing translations JSON: {json.dumps(existing_translations, ensure_ascii=False)}"
    )


def _extract_output_text(response_data: dict[str, Any]) -> str:
    choices = response_data.get("choices")
    if not isinstance(choices, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenRouter localization response did not include any choices.",
        )

    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="OpenRouter localization response did not include any text output.",
    )


def _request_openrouter_localization(
    *,
    settings: Settings,
    kind: LocalizationKind,
    prompt: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENROUTER_API_KEY is not configured on the backend.",
        )

    payload = {
        "model": settings.openrouter_translation_model,
        "messages": [
            {
                "role": "system",
                "content": "You produce translations that strictly follow the requested JSON schema.",
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": f"{kind.value}_translations",
                "schema": schema,
                "strict": True,
            },
        },
    }

    request = Request(
        f"{settings.openrouter_base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.public_frontend_base_url or "https://web.mrhost.top",
            "X-Title": settings.app_name,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=60) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenRouter localization request failed: {detail or exc.reason}",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach OpenRouter for localization: {exc.reason}",
        ) from exc

    output_text = _extract_output_text(response_data)
    try:
        return json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenRouter localization output was not valid JSON.",
        ) from exc


def generate_localized_translations(
    *,
    kind: LocalizationKind,
    source_translation: dict[str, Any],
    existing_translations: list[dict[str, Any]] | None = None,
    target_languages: list[str] | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    normalized_source = _validate_source_translation(kind, source_translation)
    normalized_existing = _normalize_existing_translations(kind, existing_translations or [])
    normalized_targets = _extract_targets(target_languages or DEFAULT_TARGET_LANGUAGES)
    if not normalized_targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one non-English target language is required.",
        )

    response_data = _request_openrouter_localization(
        settings=settings or get_settings(),
        kind=kind,
        prompt=_build_prompt(kind, normalized_source, normalized_existing, normalized_targets),
        schema=_build_output_schema(kind),
    )

    translations = response_data.get("translations")
    if not isinstance(translations, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenRouter localization response did not include a translations array.",
        )

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for translation in translations:
        if not isinstance(translation, dict):
            continue

        code = _normalize_language_code(str(translation.get("language_code", "")))
        if code not in normalized_targets or code in seen:
            continue

        entry = dict(translation)
        entry["language_code"] = code
        normalized.append(entry)
        seen.add(code)

    missing = [code for code in normalized_targets if code not in seen]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenRouter localization response was missing languages: {', '.join(missing)}",
        )

    return normalized
