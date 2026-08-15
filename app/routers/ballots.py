"""
Ballots Router — /ballots
==========================
Admin: publish ballot from approved nominations.
Student: view published ballot for open voting categories.
"""

from fastapi import APIRouter, HTTPException, status

from app.routers.deps import AdminDep, StudentDep
from app.services import content_service

router = APIRouter(prefix="/ballots", tags=["ballots"])


@router.post("/publish/{category_id}", status_code=status.HTTP_201_CREATED)
async def publish_ballot(admin: AdminDep, category_id: str):
    """
    Admin: create ballot entries from all approved nominations.
    After this, the category's ballot_published flag is set to True,
    enabling the voting window to open.
    """
    cat = await content_service.get_category(category_id)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    entries = await content_service.publish_ballot(category_id)
    if not entries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No approved nominations found to publish",
        )

    return {
        "message": f"Ballot published with {len(entries)} entries",
        "entries": [{"id": str(e.id), "nominee_name": e.nominee_name} for e in entries],
    }


@router.get("/{category_id}")
async def get_ballot(current_user: StudentDep, category_id: str):
    """
    Get the published ballot for a category.
    Students can only view if voting is open.
    Admins can preview regardless of phase.
    """
    cat = await content_service.get_category(category_id)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    is_admin = current_user.get("role") == "admin"
    if not is_admin and not cat.voting_is_open:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voting is not currently open for this category",
        )

    if not cat.ballot_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ballot has not been published yet",
        )

    entries = await content_service.get_ballot(category_id)
    return {
        "category_id": category_id,
        "category_name": cat.name,
        "category_type": cat.type,
        "voting_close_at": cat.voting_close_at,
        "entries": [{"id": str(e.id), "nominee_name": e.nominee_name} for e in entries],
    }
