"""
Nominations Router — /nominations
===================================
Student: submit one nomination per category.
Admin: list, approve, reject, merge nominations.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.routers.deps import AdminDep, StudentDep
from app.services import content_service, identity_service

router = APIRouter(prefix="/nominations", tags=["nominations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class NominationSubmit(BaseModel):
    category_id: str
    nominee_name: str = Field(..., min_length=2, max_length=120)
    reason: Optional[str] = Field(None, max_length=300)


class StatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected|pending)$")


class MergeRequest(BaseModel):
    keep_id: str
    discard_id: str
    final_name: Optional[str] = Field(None, max_length=120)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/", status_code=status.HTTP_201_CREATED)
async def submit_nomination(current_user: StudentDep, body: NominationSubmit):
    """
    Student submits a nomination.
    Eligibility and duplicate-submission checks happen against the identity
    layer (via identity_service). The nomination content is stored separately
    with no submitter reference.
    """
    hashed_matric = current_user["sub"]

    # 1. Check category exists and nominations are open
    cat = await content_service.get_category(body.category_id)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    if not cat.nomination_is_open:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nomination window is not currently open for this category",
        )

    # 2. Check eligibility (identity layer — uses hashed_matric from JWT)
    voter = await identity_service.get_voter_by_hash(hashed_matric)
    if not voter:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not eligible to nominate")

    # 3. Check has_nominated flag
    already_nominated = any(
        r.category_id == body.category_id and r.has_nominated
        for r in voter.nomination_records
    )
    if already_nominated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already submitted a nomination for this category",
        )

    # 4. Insert nomination (content layer — no submitter stored)
    await content_service.submit_nomination(
        category_id=body.category_id,
        nominee_name=body.nominee_name,
        reason=body.reason,
    )

    # 5. Mark nomination flag on identity record (separate operation, no link)
    await identity_service.mark_nominated_by_hash(hashed_matric, body.category_id)

    return {"message": "Nomination submitted anonymously"}


@router.get("/")
async def list_nominations(admin: AdminDep, category_id: str, status: Optional[str] = None):
    """
    Admin: list nominations for a category with optional status filter.
    If status is omitted and include_hints=true, returns fuzzy duplicate hints.
    """
    result = await content_service.list_nominations_with_duplicates(category_id)
    return result


@router.put("/{nomination_id}/status")
async def update_status(admin: AdminDep, nomination_id: str, body: StatusUpdate):
    nom = await content_service.update_nomination_status(nomination_id, body.status)
    if not nom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomination not found")
    return {"id": str(nom.id), "status": nom.status, "nominee_name": nom.nominee_name}


@router.post("/merge")
async def merge_nominations(admin: AdminDep, body: MergeRequest):
    """Merge two nominations — approve 'keep', mark 'discard' as merged."""
    result = await content_service.merge_nominations(
        body.keep_id, body.discard_id, body.final_name
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both nominations not found",
        )
    return {"id": str(result.id), "nominee_name": result.nominee_name, "status": result.status}
