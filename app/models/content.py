"""
CONTENT LAYER — models.content
================================
This module ONLY contains documents related to the nomination/voting content.

CRITICAL RULE: This module must NEVER import from app.models.identity.
               No document here stores a voter reference, session link,
               or any field that could be joined back to eligible_voters.

This is the second half of the anonymity guarantee: even a full dump of
these collections reveals zero information about who submitted what.
"""

from datetime import datetime, timezone
from typing import Literal, Optional

from beanie import Document
from pydantic import Field
from pymongo import IndexModel, ASCENDING


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Document: categories
# ---------------------------------------------------------------------------

class Category(Document):
    """
    Defines an award or leadership position category.

    Phase timing uses explicit open/close datetimes (admin-configurable)
    rather than hardcoded durations, with optional force-close override flags
    for emergency admin control.
    """

    name: str
    type: Literal["award", "position"]

    # Nomination phase window
    nomination_open_at: Optional[datetime] = None
    nomination_close_at: Optional[datetime] = None
    nomination_force_closed: bool = False  # Admin override — immediately closes

    # Voting phase window
    voting_open_at: Optional[datetime] = None
    voting_close_at: Optional[datetime] = None
    voting_force_closed: bool = False  # Admin override

    # Ballot state
    ballot_published: bool = False

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "categories"
        indexes = [
            IndexModel([("name", ASCENDING)]),
        ]

    @property
    def nomination_is_open(self) -> bool:
        if self.nomination_force_closed:
            return False
        now = _utcnow()
        open_at = _as_utc(self.nomination_open_at)
        close_at = _as_utc(self.nomination_close_at)
        if open_at and close_at:
            return open_at <= now <= close_at
        return False

    @property
    def voting_is_open(self) -> bool:
        if self.voting_force_closed or not self.ballot_published:
            return False
        now = _utcnow()
        open_at = _as_utc(self.voting_open_at)
        close_at = _as_utc(self.voting_close_at)
        if open_at and close_at:
            return open_at <= now <= close_at
        return False


# ---------------------------------------------------------------------------
# Document: nominations
# ---------------------------------------------------------------------------

class Nomination(Document):
    """
    A single nomination submitted by a student.

    ANONYMITY GUARANTEE: This document has NO submitter field, NO session ID,
    NO IP address, and NO timestamp correlated with the identity layer.
    The insert is delayed by a random 50–500ms server-side to prevent
    timing correlation with identity logs.
    """

    category_id: str  # ObjectId hex — string to prevent accidental Beanie relation
    nominee_name: str = Field(..., min_length=2, max_length=120)
    reason: Optional[str] = Field(None, max_length=300)
    status: Literal["pending", "approved", "rejected", "merged"] = "pending"
    merged_into: Optional[str] = None  # ObjectId hex of the winning nomination after merge

    # NO: submitter_id, session_id, ip_address, submitted_at

    class Settings:
        name = "nominations"
        indexes = [
            IndexModel([("category_id", ASCENDING)]),
            IndexModel([("category_id", ASCENDING), ("status", ASCENDING)]),
        ]


# ---------------------------------------------------------------------------
# Document: ballot_entries
# ---------------------------------------------------------------------------

class BallotEntry(Document):
    """
    A finalized, published nominee on a voting ballot.
    Created by admin from approved nominations.
    """

    category_id: str
    nominee_name: str = Field(..., min_length=2, max_length=120)

    class Settings:
        name = "ballot_entries"
        indexes = [
            IndexModel([("category_id", ASCENDING)]),
        ]


# ---------------------------------------------------------------------------
# Document: votes
# ---------------------------------------------------------------------------

class Vote(Document):
    """
    A single vote cast by a student.

    ANONYMITY GUARANTEE: This document has NO voter reference, NO session ID,
    NO IP address, and NO timestamp. The insert is delayed by a random
    50–500ms server-side to prevent timing correlation with identity logs.
    """

    category_id: str        # ObjectId hex
    ballot_entry_id: str    # ObjectId hex

    # NO: voter_id, session_id, ip_address, cast_at

    class Settings:
        name = "votes"
        indexes = [
            IndexModel([("category_id", ASCENDING)]),
            IndexModel([("ballot_entry_id", ASCENDING)]),
        ]
