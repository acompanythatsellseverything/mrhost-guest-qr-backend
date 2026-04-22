from fastapi import APIRouter

from app.api.routers.admin import auth as admin_auth
from app.api.routers.admin import consent as admin_consent
from app.api.routers.admin import faq as admin_faq
from app.api.routers.admin import listings as admin_listings
from app.api.routers.admin import localization as admin_localization
from app.api.routers.admin import logs as admin_logs
from app.api.routers.admin import page_description as admin_page_description
from app.api.routers.admin import specific_item as admin_specific_item
from app.api.routers.admin import qr as admin_qr
from app.api.routers.admin import tutorial as admin_tutorial
from app.api.routers.admin import users as admin_users
from app.api.routers.public import consent as public_consent
from app.api.routers.public import guide as public_guide
from app.api.routers.public import health as public_health

router = APIRouter()

router.include_router(public_health.router)
router.include_router(public_consent.router)
router.include_router(public_guide.router)

router.include_router(admin_auth.router)
router.include_router(admin_listings.router)
router.include_router(admin_localization.router)
router.include_router(admin_qr.router)
router.include_router(admin_consent.router)
router.include_router(admin_faq.router)
router.include_router(admin_page_description.router)
router.include_router(admin_tutorial.router)
router.include_router(admin_specific_item.router)
router.include_router(admin_logs.router)
router.include_router(admin_users.router)
