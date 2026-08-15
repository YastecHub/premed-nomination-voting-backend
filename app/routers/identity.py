"""
Identity Router — /identity
============================
Admin-only endpoints for seeding eligible voter lists and viewing stats.
"""

import csv
import io
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, status
from pydantic import BaseModel, Field

from app.routers.deps import AdminDep
from app.services import identity_service
from app.core.security import hash_matric, hash_pin

router = APIRouter(prefix="/identity", tags=["identity"])


# ---------------------------------------------------------------------------
# Seed voters
# ---------------------------------------------------------------------------

class SeedResponse(BaseModel):
    inserted: int
    skipped: int
    total: int


@router.post("/seed/csv", response_model=SeedResponse)
async def seed_from_csv(
    admin: AdminDep,
    file: UploadFile = File(...),
):
    """
    Upload a CSV file of matric numbers to seed the eligible voter list.
    The CSV should have one matric number per row (with or without a header).
    Matric numbers are hashed before storage — the file is never persisted.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV files accepted")

    content = await file.read()
    text = content.decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(text))

    matric_list = []
    for row in reader:
        for cell in row:
            value = cell.strip()
            if value and value.lower() not in ("matric", "matric_number", "matricno", "matric no"):
                matric_list.append(value)

    if not matric_list:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid matric numbers found in CSV")

    result = await identity_service.seed_voters(matric_list)
    return SeedResponse(**result)


class ManualSeedRequest(BaseModel):
    matric_numbers: list[str] = Field(..., min_length=1, max_length=500)


@router.post("/seed/manual", response_model=SeedResponse)
async def seed_manual(admin: AdminDep, body: ManualSeedRequest):
    """Manually enter a list of matric numbers to add to the eligible list."""
    result = await identity_service.seed_voters(body.matric_numbers)
    return SeedResponse(**result)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
async def get_stats(admin: AdminDep):
    """Return aggregate voter participation stats — no raw matric data."""
    stats = await identity_service.get_identity_stats([])
    return stats


# ---------------------------------------------------------------------------
# Admin bootstrap (first-time setup only)
# ---------------------------------------------------------------------------

class CreateAdminRequest(BaseModel):
    matric_number: str = Field(..., min_length=5, max_length=20)
    pin: str = Field(..., min_length=4, max_length=10)
    display_name: Optional[str] = None
    bootstrap_secret: str  # Must match BOOTSTRAP_SECRET env var


@router.post("/admin/create", status_code=status.HTTP_201_CREATED)
async def create_admin_account(body: CreateAdminRequest):
    """
    Create a new admin account. Protected by a bootstrap secret (not a JWT).
    Used only during initial setup.
    """
    import os
    bootstrap_secret = os.environ.get("BOOTSTRAP_SECRET", "")
    if not bootstrap_secret or body.bootstrap_secret != bootstrap_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid bootstrap secret")

    try:
        admin = await identity_service.create_admin(
            body.matric_number, body.pin, body.display_name
        )
        return {"message": "Admin created", "display_name": admin.display_name}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Admin with this matric number already exists",
        )
