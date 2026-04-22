from fastapi import APIRouter, Depends

from app.api.deps import get_current_admin
from app.schemas.localization import LocalizationRequest, LocalizationResponse
from app.services.localization import generate_localized_translations

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.post("/admin/localization/sync", response_model=LocalizationResponse, tags=["Admin"])
def sync_localized_content(payload: LocalizationRequest) -> LocalizationResponse:
    translations = generate_localized_translations(
        kind=payload.kind,
        source_translation=payload.source_translation,
        existing_translations=payload.existing_translations,
        target_languages=payload.target_languages,
    )
    return LocalizationResponse(translations=translations)
