"""API v1 router."""

from fastapi import APIRouter

from app.api.v1 import accounts, admin, archive, auth, install, jobs

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(install.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(accounts.router)
api_router.include_router(jobs.router)
api_router.include_router(archive.archive_router)
api_router.include_router(archive.mails_router)
