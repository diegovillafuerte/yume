"""Main API router for v1 endpoints."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    appointments,
    auth,
    availability,
    customers,
    locations,
    organizations,
    services,
    spots,
    staff,
    webhooks,
)
from app.config import get_settings

router = APIRouter()

# Include all sub-routers
router.include_router(admin.router)  # Admin routes
router.include_router(auth.router)  # Auth first (no org_id prefix)
router.include_router(organizations.router)
router.include_router(locations.router)
router.include_router(spots.router)
router.include_router(services.router)
router.include_router(staff.router)
router.include_router(customers.router)
router.include_router(appointments.router)
router.include_router(availability.router)
router.include_router(webhooks.router)

# Simulation endpoints - admin-auth protected, available in all environments
from app.api.v1 import simulate

router.include_router(simulate.router)


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "message": "Parlo API is running"}
