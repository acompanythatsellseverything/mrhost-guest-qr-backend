from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import ConsentLog

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("/admin/consent-logs", tags=["Admin"])
def list_consent_logs(
    listing_id: Optional[int] = None,
    language: Optional[str] = None,
    decision: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    query = db.query(ConsentLog)
    conditions = []
    if listing_id is not None:
        conditions.append(ConsentLog.listing_id == listing_id)
    if language is not None:
        conditions.append(ConsentLog.language_code == language)
    if decision is not None:
        conditions.append(ConsentLog.decision == decision)
    if start is not None:
        conditions.append(ConsentLog.created_at >= start)
    if end is not None:
        conditions.append(ConsentLog.created_at <= end)
    if conditions:
        query = query.filter(and_(*conditions))
    logs = query.order_by(ConsentLog.created_at.desc()).all()
    return [
        {
            "id": log.id,
            "listing_id": log.listing_id,
            "template_id": log.template_id,
            "template_version": log.template_version,
            "language_code": log.language_code,
            "decision": log.decision,
            "marketing_consent": log.marketing_consent,
            "marketing_consent_recorded_at": log.marketing_consent_recorded_at,
            "email": log.email,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "created_at": log.created_at,
        }
        for log in logs
    ]
