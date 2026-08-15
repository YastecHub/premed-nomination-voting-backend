"""
Categories Router — /categories
=================================
Full CRUD for categories (admin) + read-only for students.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.routers.deps import AdminDep, StudentDep
from app.services import content_service

router = APIRouter(prefix="/categories", tags=["categories"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    type: str = Field(..., pattern="^(award|position)$")
    nomination_open_at: Optional[datetime] = None
    nomination_close_at: Optional[datetime] = None
    voting_open_at: Optional[datetime] = None
    voting_close_at: Optional[datetime] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    type: Optional[str] = Field(None, pattern="^(award|position)$")
    nomination_open_at: Optional[datetime] = None
    nomination_close_at: Optional[datetime] = None
    nomination_force_closed: Optional[bool] = None
    voting_open_at: Optional[datetime] = None
    voting_close_at: Optional[datetime] = None
    voting_force_closed: Optional[bool] = None
    ballot_published: Optional[bool] = None


def _serialize(cat) -> dict:
    return {
        "id": str(cat.id),
        "name": cat.name,
        "type": cat.type,
        "nomination_open_at": cat.nomination_open_at,
        "nomination_close_at": cat.nomination_close_at,
        "nomination_is_open": cat.nomination_is_open,
        "nomination_force_closed": cat.nomination_force_closed,
        "voting_open_at": cat.voting_open_at,
        "voting_close_at": cat.voting_close_at,
        "voting_is_open": cat.voting_is_open,
        "voting_force_closed": cat.voting_force_closed,
        "ballot_published": cat.ballot_published,
        "created_at": cat.created_at,
        "updated_at": cat.updated_at,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/")
async def list_categories(current_user: StudentDep):
    categories = await content_service.list_categories()
    return [_serialize(c) for c in categories]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_category(admin: AdminDep, body: CategoryCreate):
    cat = await content_service.create_category(
        name=body.name,
        type_=body.type,
        nomination_open_at=body.nomination_open_at,
        nomination_close_at=body.nomination_close_at,
        voting_open_at=body.voting_open_at,
        voting_close_at=body.voting_close_at,
    )
    return _serialize(cat)


@router.put("/{category_id}")
async def update_category(admin: AdminDep, category_id: str, body: CategoryUpdate):
    updates = body.model_dump(exclude_none=True)
    cat = await content_service.update_category(category_id, updates)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return _serialize(cat)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(admin: AdminDep, category_id: str):
    deleted = await content_service.delete_category(category_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete category with existing nominations",
        )
