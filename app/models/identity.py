"""
IDENTITY LAYER — models.identity
=================================
This module ONLY contains documents related to voter identity and authentication.

CRITICAL RULE: This module must NEVER import from app.models.content.
               No query in any service should ever JOIN / $lookup between
               these collections and any content collection.

This separation is the architectural guarantee of anonymity:
a MongoDB $lookup between eligible_voters and votes/nominations is
never written, making re-linkage impossible at the application layer.
"""

from typing import Optional
from beanie import Document
from pydantic import BaseModel, Field
from pymongo import IndexModel, ASCENDING


# ---------------------------------------------------------------------------
# Sub-document: per-category nomination tracking
# ---------------------------------------------------------------------------

class NominationRecord(BaseModel):
    """Tracks whether this voter has nominated in a specific category.

    category_id is stored as a string (ObjectId hex) to avoid any accidental
    Beanie relationship resolution that might tempt cross-collection queries.
    """
    category_id: str  # ObjectId hex string
    has_nominated: bool = False


# ---------------------------------------------------------------------------
# Sub-document: per-category vote tracking
# ---------------------------------------------------------------------------

class VoteRecord(BaseModel):
    """Tracks whether this voter has voted in a specific category."""
    category_id: str  # ObjectId hex string
    has_voted: bool = False


# ---------------------------------------------------------------------------
# Document: eligible_voters
# ---------------------------------------------------------------------------

class EligibleVoter(Document):
    """
    Stores ONLY identity signals — never any content (what was nominated/voted).

    hashed_matric_id: SHA-256(matric.upper() + PEPPER)
                      Matric numbers are never stored in plaintext.
    nomination_records: list of {category_id, has_nominated} — boolean flags only
    vote_records:       list of {category_id, has_voted} — boolean flags only

    Timestamps are intentionally omitted from this document to prevent
    any timing correlation with content collections.
    """

    hashed_matric_id: str = Field(..., description="SHA-256 hash of matric + server pepper")
    nomination_records: list[NominationRecord] = Field(default_factory=list)
    vote_records: list[VoteRecord] = Field(default_factory=list)

    class Settings:
        name = "eligible_voters"
        indexes = [
            IndexModel([("hashed_matric_id", ASCENDING)], unique=True),
        ]


# ---------------------------------------------------------------------------
# Document: admin_accounts
# ---------------------------------------------------------------------------

class AdminAccount(Document):
    """
    Admin credentials — separate from EligibleVoter so admins are not
    conflated with the student voter pool.

    hashed_matric_id: SHA-256(matric.upper() + ADMIN_PEPPER)
                      Uses a *different* pepper than student matric hashes.
    hashed_pin:       bcrypt hash of the 6-digit admin PIN.
    is_active:        soft-disable an admin without deleting.
    """

    hashed_matric_id: str = Field(..., description="SHA-256 hash of admin matric + admin pepper")
    hashed_pin: str = Field(..., description="bcrypt hash of 6-digit PIN")
    display_name: Optional[str] = None
    is_active: bool = True

    class Settings:
        name = "admin_accounts"
        indexes = [
            IndexModel([("hashed_matric_id", ASCENDING)], unique=True),
        ]
