from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.models.base import Base


def json_type():
    return JSON


class TimestampMixin:
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Listing(Base, TimestampMixin):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)

    faqs = relationship("FAQ", back_populates="listing", cascade="all, delete-orphan")
    tutorials = relationship("Tutorial", back_populates="listing", cascade="all, delete-orphan")
    consent_templates = relationship(
        "ConsentTemplate", back_populates="listing", cascade="all, delete-orphan"
    )
    page_descriptions = relationship(
        "PageDescription",
        back_populates="listing",
        cascade="all, delete-orphan",
    )
    specific_items = relationship(
        "SpecificItem", back_populates="listing", cascade="all, delete-orphan"
    )


class SpecificItem(Base, TimestampMixin):
    __tablename__ = "specific_items"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(
        Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)

    listing = relationship("Listing", back_populates="specific_items")

    __table_args__ = (
        UniqueConstraint("listing_id", "slug", name="uq_specific_item_slug"),
    )


class ConsentTemplateStatusEnum(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ConsentTemplate(Base, TimestampMixin):
    __tablename__ = "consent_templates"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False, default=ConsentTemplateStatusEnum.DRAFT.value)
    published_at = Column(DateTime(timezone=True), nullable=True)

    listing = relationship("Listing", back_populates="consent_templates")
    translations = relationship(
        "ConsentTemplateTranslation",
        back_populates="template",
        cascade="all, delete-orphan",
    )
    logs = relationship("ConsentLog", back_populates="template")

    __table_args__ = (UniqueConstraint("listing_id", "version", name="uq_template_version"),)


class ConsentTemplateTranslation(Base, TimestampMixin):
    __tablename__ = "consent_template_translations"

    id = Column(Integer, primary_key=True)
    template_id = Column(
        Integer, ForeignKey("consent_templates.id", ondelete="CASCADE"), nullable=False
    )
    language_code = Column(String(10), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)

    template = relationship("ConsentTemplate", back_populates="translations")

    __table_args__ = (
        UniqueConstraint("template_id", "language_code", name="uq_template_language"),
    )


class FAQ(Base, TimestampMixin):
    __tablename__ = "faqs"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    specific_item = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    listing = relationship("Listing", back_populates="faqs")
    translations = relationship(
        "FAQTranslation", back_populates="faq", cascade="all, delete-orphan"
    )


class FAQTranslation(Base, TimestampMixin):
    __tablename__ = "faq_translations"

    id = Column(Integer, primary_key=True)
    faq_id = Column(Integer, ForeignKey("faqs.id", ondelete="CASCADE"), nullable=False)
    language_code = Column(String(10), nullable=False)
    question = Column(String(255), nullable=False)
    answer = Column(Text, nullable=False)
    links = Column(json_type(), nullable=True)

    faq = relationship("FAQ", back_populates="translations")

    __table_args__ = (UniqueConstraint("faq_id", "language_code", name="uq_faq_language"),)


class Tutorial(Base, TimestampMixin):
    __tablename__ = "tutorials"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    specific_item = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    listing = relationship("Listing", back_populates="tutorials")
    translations = relationship(
        "TutorialTranslation", back_populates="tutorial", cascade="all, delete-orphan"
    )


class TutorialTranslation(Base, TimestampMixin):
    __tablename__ = "tutorial_translations"

    id = Column(Integer, primary_key=True)
    tutorial_id = Column(
        Integer, ForeignKey("tutorials.id", ondelete="CASCADE"), nullable=False
    )
    language_code = Column(String(10), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    video_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)

    tutorial = relationship("Tutorial", back_populates="translations")

    __table_args__ = (
        UniqueConstraint("tutorial_id", "language_code", name="uq_tutorial_language"),
    )


class ConsentLog(Base, TimestampMixin):
    __tablename__ = "consent_logs"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="SET NULL"), nullable=True)
    template_id = Column(
        Integer, ForeignKey("consent_templates.id", ondelete="SET NULL"), nullable=True
    )
    template_version = Column(Integer, nullable=False)
    language_code = Column(String(10), nullable=False)
    decision = Column(String(10), nullable=False)
    marketing_consent = Column(Boolean, nullable=False, default=False)
    marketing_consent_recorded_at = Column(DateTime(timezone=True), nullable=True)
    email = Column(String(255), nullable=True)
    ip_address = Column(String(255), nullable=True)
    user_agent = Column(String(500), nullable=True)

    template = relationship("ConsentTemplate", back_populates="logs")


class PageDescription(Base, TimestampMixin):
    __tablename__ = "page_descriptions"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    specific_item = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    listing = relationship("Listing", back_populates="page_descriptions")
    translations = relationship(
        "PageDescriptionTranslation",
        back_populates="page_description",
        cascade="all, delete-orphan",
    )


class PageDescriptionTranslation(Base, TimestampMixin):
    __tablename__ = "page_description_translations"

    id = Column(Integer, primary_key=True)
    page_description_id = Column(
        Integer, ForeignKey("page_descriptions.id", ondelete="CASCADE"), nullable=False
    )
    language_code = Column(String(10), nullable=False)
    body = Column(Text, nullable=False)

    page_description = relationship("PageDescription", back_populates="translations")

    __table_args__ = (
        UniqueConstraint(
            "page_description_id",
            "language_code",
            name="uq_page_description_language",
        ),
    )
class AdminRoleEnum(str, Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"


class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    role = Column(String(50), default=AdminRoleEnum.ADMIN.value, nullable=False)
    totp_secret = Column(String(64), nullable=True)
    totp_enabled = Column(Boolean, default=False, nullable=False)
    password_changed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    invites_created = relationship("AdminInvite", back_populates="created_by", foreign_keys="AdminInvite.created_by_id")
    invites_used = relationship("AdminInvite", back_populates="used_by", foreign_keys="AdminInvite.used_by_id")
    refresh_tokens = relationship("AdminRefreshToken", back_populates="user", cascade="all, delete-orphan")
    recovery_codes = relationship("AdminRecoveryCode", back_populates="user", cascade="all, delete-orphan")


class AdminInvite(Base, TimestampMixin):
    __tablename__ = "admin_invites"

    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, nullable=False, default=lambda: uuid4().hex)
    email = Column(String(255), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(Integer, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    used_by_id = Column(Integer, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    is_revoked = Column(Boolean, default=False, nullable=False)

    created_by = relationship("AdminUser", foreign_keys=[created_by_id], back_populates="invites_created")
    used_by = relationship("AdminUser", foreign_keys=[used_by_id], back_populates="invites_used")


class AdminRefreshToken(Base, TimestampMixin):
    __tablename__ = "admin_refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(128), nullable=False, unique=True)
    family_id = Column(String(64), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    replaced_by_id = Column(Integer, ForeignKey("admin_refresh_tokens.id", ondelete="SET NULL"), nullable=True)

    user = relationship("AdminUser", back_populates="refresh_tokens", foreign_keys=[user_id])
    replaced_by = relationship("AdminRefreshToken", remote_side=[id])


class AdminPasswordResetToken(Base, TimestampMixin):
    __tablename__ = "admin_password_reset_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(128), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("AdminUser")


class AdminRecoveryCode(Base, TimestampMixin):
    __tablename__ = "admin_recovery_codes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False)
    code_hash = Column(String(128), nullable=False, unique=True)
    used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("AdminUser", back_populates="recovery_codes")


class AdminAuditLog(Base, TimestampMixin):
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(100), nullable=False)
    ip_address = Column(String(255), nullable=True)
    details = Column(json_type(), nullable=True)

    user = relationship("AdminUser")
