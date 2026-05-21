from datetime import datetime

import jwt
import pytest
import uuid

from sqlalchemy.orm import Session

from tests.conftest import SimpleTestClient

from app.core.config import get_settings
from app.models import (
    ConsentLog,
    ConsentTemplate,
    ConsentTemplateTranslation,
    FAQ,
    FAQTranslation,
    Listing,
    PageDescription,
    PageDescriptionTranslation,
    Tutorial,
    TutorialTranslation,
)
from app.services.qr import create_qr_token, decode_qr_token

settings = get_settings()


def _create_listing(db: Session) -> Listing:
    slug = f"test-listing-{uuid.uuid4().hex[:8]}"
    listing = Listing(name="Test Listing", slug=slug)
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def _create_published_consent(db: Session, listing: Listing) -> ConsentTemplate:
    template = ConsentTemplate(listing_id=listing.id, version=1, status="published")
    db.add(template)
    db.flush()
    translation_en = ConsentTemplateTranslation(
        template=template,
        language_code="en",
        title="Consent",
        body="English body",
    )
    translation_es = ConsentTemplateTranslation(
        template=template,
        language_code="es",
        title="Consentimiento",
        body="Cuerpo en español",
    )
    db.add_all([translation_en, translation_es])
    db.commit()
    db.refresh(template)
    return template


def _create_guide_content(db: Session, listing: Listing) -> None:
    faq = FAQ(listing_id=listing.id, is_active=True)
    db.add(faq)
    db.flush()
    db.add_all(
        [
            FAQTranslation(
                faq=faq,
                language_code="en",
                question="Q1",
                answer="A1",
                links=[{"label": "Link", "url": "https://example.com"}],
            ),
            FAQTranslation(
                faq=faq,
                language_code="es",
                question="P1",
                answer="R1",
                links=[{"label": "Enlace", "url": "https://example.com/es"}],
            ),
        ]
    )
    tutorial = Tutorial(listing_id=listing.id, is_active=True)
    db.add(tutorial)
    db.flush()
    db.add_all(
        [
            TutorialTranslation(
                tutorial=tutorial,
                language_code="en",
                title="How to",
                description="English",
                video_url="https://example.com/video",
            ),
        ]
    )
    db.commit()


def _create_page_description(db: Session, listing: Listing) -> PageDescription:
    description = PageDescription(listing_id=listing.id, is_active=True)
    db.add(description)
    db.flush()
    db.add_all(
        [
            PageDescriptionTranslation(
                page_description=description,
                language_code="en",
                body="Welcome to the property.",
            ),
            PageDescriptionTranslation(
                page_description=description,
                language_code="es",
                body="Bienvenido a la propiedad.",
            ),
        ]
    )
    db.commit()
    db.refresh(description)
    return description


def _create_specific_guide_content(
    db: Session, listing: Listing, specific_item: str
) -> None:
    faq = FAQ(listing_id=listing.id, is_active=True, specific_item=specific_item)
    db.add(faq)
    db.flush()
    db.add(
        FAQTranslation(
            faq=faq,
            language_code="en",
            question="Parking?",
            answer="Follow signs.",
            links=[{"label": "Map", "url": "https://example.com/map"}],
        )
    )
    tutorial = Tutorial(
        listing_id=listing.id, is_active=True, specific_item=specific_item
    )
    db.add(tutorial)
    db.flush()
    db.add(
        TutorialTranslation(
            tutorial=tutorial,
            language_code="en",
            title="Parking tutorial",
            description="Video",
            video_url="https://example.com/parking",
        )
    )
    description = PageDescription(
        listing_id=listing.id, is_active=True, specific_item=specific_item
    )
    db.add(description)
    db.flush()
    db.add(
        PageDescriptionTranslation(
            page_description=description,
            language_code="en",
            body="Parking instructions",
        )
    )
    db.commit()


def test_qr_token_signing_and_validation(db_session: Session):
    listing = _create_listing(db_session)
    token = create_qr_token(listing.id)
    decoded = decode_qr_token(token)
    assert decoded["listing_id"] == listing.id
    assert decoded["require_consent"] is True


def test_consent_submission_with_stale_version(client: SimpleTestClient, db_session: Session):
    listing = _create_listing(db_session)
    template = _create_published_consent(db_session, listing)

    stale_payload = {
        "template_id": template.id,
        "template_version": template.version - 1,
        "language_code": "en",
        "decision": "accept",
        "guest_name": "Isaac Otunla",
        "guest_nationality": "Nigerian",
        "email": "guest@example.com",
        "marketing_consent": False,
    }
    response = client.post(
        f"/public/listings/{listing.id}/consent",
        json=stale_payload,
    )
    assert response.status_code == 409


def test_consent_submission_success(client: SimpleTestClient, db_session: Session):
    listing = _create_listing(db_session)
    template = _create_published_consent(db_session, listing)
    payload = {
        "template_id": template.id,
        "template_version": template.version,
        "language_code": "en",
        "decision": "accept",
        "guest_name": "Isaac Otunla",
        "guest_nationality": "Nigerian",
        "email": "guest@example.com",
        "marketing_consent": True,
    }
    response = client.post(
        f"/public/listings/{listing.id}/consent",
        json=payload,
        headers={"user-agent": "pytest"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "accept"
    assert data["guest_name"] == "Isaac Otunla"
    assert data["guest_nationality"] == "Nigerian"
    assert data["email"] == "guest@example.com"
    assert data["ip_address"]
    assert data["marketing_consent"] is True
    assert data["marketing_consent_recorded_at"]
    log = db_session.query(ConsentLog).first()
    assert log is not None
    assert log.template_version == template.version
    assert log.guest_name == "Isaac Otunla"
    assert log.guest_nationality == "Nigerian"
    assert log.email == "guest@example.com"
    assert log.marketing_consent is True
    assert log.marketing_consent_recorded_at is not None


def test_faq_and_tutorial_language_fallback(client: SimpleTestClient, db_session: Session):
    listing = _create_listing(db_session)
    _create_published_consent(db_session, listing)
    _create_guide_content(db_session, listing)
    _create_page_description(db_session, listing)

    faq_response = client.get(f"/public/listings/{listing.id}/faqs", params={"language": "fr"})
    assert faq_response.status_code == 200
    faq_data = faq_response.json()
    assert faq_data["items"][0]["language_code"] == "en"
    assert faq_data["items"][0]["links"][0]["url"] == "https://example.com"

    tutorial_response = client.get(
        f"/public/listings/{listing.id}/tutorials", params={"language": "fr"}
    )
    assert tutorial_response.status_code == 200
    tutorial_data = tutorial_response.json()
    assert tutorial_data["items"][0]["language_code"] == "en"

    description_response = client.get(
        f"/public/listings/{listing.id}/page-descriptions",
        params={"language": "fr"},
    )
    assert description_response.status_code == 200
    description_data = description_response.json()
    assert description_data["items"][0]["language_code"] == "en"


def test_specific_item_routes(client: SimpleTestClient, db_session: Session):
    listing = _create_listing(db_session)
    _create_published_consent(db_session, listing)
    _create_guide_content(db_session, listing)
    _create_page_description(db_session, listing)
    _create_specific_guide_content(db_session, listing, "parking")

    faq_response = client.get(f"/public/listings/{listing.id}/faqs")
    assert faq_response.status_code == 200
    assert all(item["question"] != "Parking?" for item in faq_response.json()["items"])

    faq_specific_response = client.get(
        f"/public/listings/{listing.id}/parking/faqs"
    )
    assert faq_specific_response.status_code == 200
    faq_specific_items = faq_specific_response.json()["items"]
    assert faq_specific_items[0]["question"] == "Parking?"

    tutorial_response = client.get(f"/public/listings/{listing.id}/tutorials")
    assert tutorial_response.status_code == 200
    assert all(
        item["title"] != "Parking tutorial"
        for item in tutorial_response.json()["items"]
    )

    tutorial_specific_response = client.get(
        f"/public/listings/{listing.id}/parking/tutorials"
    )
    assert tutorial_specific_response.status_code == 200
    assert tutorial_specific_response.json()["items"][0]["title"] == "Parking tutorial"

    description_response = client.get(f"/public/listings/{listing.id}/page-descriptions")
    assert description_response.status_code == 200
    assert all(
        item["body"] != "Parking instructions"
        for item in description_response.json()["items"]
    )

    description_specific_response = client.get(
        f"/public/listings/{listing.id}/parking/page-descriptions"
    )
    assert description_specific_response.status_code == 200
    assert (
        description_specific_response.json()["items"][0]["body"]
        == "Parking instructions"
    )
