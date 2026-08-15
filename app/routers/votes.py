"""
Votes Router — /votes
======================
Student submits a vote. Same anonymity pattern as nominations:
eligibility checked via identity layer, vote stored in content layer with
no voter reference, inserted with random timing noise.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.routers.deps import StudentDep
from app.services import content_service, identity_service

router = APIRouter(prefix="/votes", tags=["votes"])


class VoteSubmit(BaseModel):
    category_id: str
    ballot_entry_id: str


@router.post("/", status_code=status.HTTP_201_CREATED)
async def submit_vote(current_user: StudentDep, body: VoteSubmit):
    """
    Student casts a vote.

    Anonymity flow:
    1. JWT sub (hashed_matric) used ONLY for eligibility + has_voted check.
    2. Vote inserted in content layer with NO voter reference.
    3. has_voted flag flipped on identity record.
    4. Steps 2 and 3 are separate DB operations — never linked.
    """
    hashed_matric = current_user["sub"]

    # 1. Category exists and voting is open
    cat = await content_service.get_category(body.category_id)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    if not cat.voting_is_open:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voting is not currently open for this category",
        )

    # 2. Ballot entry exists in this category
    entries = await content_service.get_ballot(body.category_id)
    entry_ids = {str(e.id) for e in entries}
    if body.ballot_entry_id not in entry_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ballot entry for this category",
        )

    # 3. Eligibility check (identity layer)
    voter = await identity_service.get_voter_by_hash(hashed_matric)
    if not voter:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not eligible to vote")

    # 4. Duplicate vote check
    already_voted = any(
        r.category_id == body.category_id and r.has_voted
        for r in voter.vote_records
    )
    if already_voted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already voted in this category",
        )

    # 5. Insert vote (content layer — no voter reference)
    await content_service.submit_vote(
        category_id=body.category_id,
        ballot_entry_id=body.ballot_entry_id,
    )

    # 6. Mark voted flag (identity layer — separate operation)
    await identity_service.mark_voted_by_hash(hashed_matric, body.category_id)

    return {"message": "Vote cast anonymously"}
