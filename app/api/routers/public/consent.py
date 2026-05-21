from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ConsentLog, ConsentTemplate, ConsentTemplateTranslation, Listing
from app.schemas.consent import ConsentDecisionCreate, ConsentDecisionOut

router = APIRouter()


def _get_latest_published_template(db: Session, listing_id: int) -> ConsentTemplate | None:
    return (
        db.query(ConsentTemplate)
        .filter(ConsentTemplate.listing_id == listing_id, ConsentTemplate.status == "published")
        .order_by(ConsentTemplate.version.desc())
        .first()
    )


@router.get("/public/listings/{listing_id}/consent", tags=["Public"])
def get_consent_template(listing_id: int, language: str = "en", db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    template = _get_latest_published_template(db, listing_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consent template not found")
    translation = (
        db.query(ConsentTemplateTranslation)
        .filter(
            ConsentTemplateTranslation.template_id == template.id,
            ConsentTemplateTranslation.language_code == language,
        )
        .first()
    )
    if not translation:
        translation = (
            db.query(ConsentTemplateTranslation)
            .filter(
                ConsentTemplateTranslation.template_id == template.id,
                ConsentTemplateTranslation.language_code == "en",
            )
            .first()
        )
    if not translation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consent translation not found")
    return {
        "template_id": template.id,
        "template_version": template.version,
        "status": template.status,
        "translation": {
            "language_code": translation.language_code,
            "title": translation.title,
            "body": translation.body,
        },
    }


@router.post("/public/listings/{listing_id}/consent", response_model=ConsentDecisionOut, tags=["Public"])
def submit_consent(
    listing_id: int,
    payload: ConsentDecisionCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    template = _get_latest_published_template(db, listing_id)
    if not template or template.id != payload.template_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid template")
    if template.version != payload.template_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Template version is stale")
    log = ConsentLog(
        listing_id=listing_id,
        template_id=template.id,
        template_version=template.version,
        language_code=payload.language_code,
        decision=payload.decision,
        marketing_consent=payload.marketing_consent,
        marketing_consent_recorded_at=datetime.now(timezone.utc),
        guest_name=payload.guest_name.strip(),
        guest_nationality=payload.guest_nationality.strip(),
        email=payload.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
