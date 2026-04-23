from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


DEFAULT_TARGET_LANGUAGES = ["es", "ru", "uk", "pt", "it", "fr", "pl", "nl"]


class LocalizationKind(str, Enum):
    CONSENT = "consent"
    FAQ = "faq"
    TUTORIAL = "tutorial"
    PAGE_DESCRIPTION = "page_description"


class LocalizationRequest(BaseModel):
    kind: LocalizationKind
    source_translation: dict[str, Any]
    existing_translations: list[dict[str, Any]] = Field(default_factory=list)
    target_languages: list[str] = Field(default_factory=lambda: DEFAULT_TARGET_LANGUAGES.copy())


class LocalizationResponse(BaseModel):
    translations: list[dict[str, Any]]
