"""
Content Service — exclusively reads/writes the content layer collections.

This service NEVER imports from app.models.identity or app.services.identity_service.
It works only with Category, Nomination, BallotEntry, and Vote documents.
"""

import asyncio
import random
from datetime import datetime, timezone
from typing import Optional

from rapidfuzz import fuzz

from app.models.content import Category, Nomination, BallotEntry, Vote


# ---------------------------------------------------------------------------
# Timing noise — prevents submission-order correlation attacks
# ---------------------------------------------------------------------------

async def _noise_delay():
    """Random 50–500ms delay before a content insert."""
    await asyncio.sleep(random.uniform(0.05, 0.5))


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

async def list_categories() -> list[Category]:
    return await Category.find_all().to_list()


async def get_category(category_id: str) -> Optional[Category]:
    from beanie import PydanticObjectId
    return await Category.get(PydanticObjectId(category_id))


async def create_category(
    name: str,
    type_: str,
    nomination_open_at: Optional[datetime] = None,
    nomination_close_at: Optional[datetime] = None,
    voting_open_at: Optional[datetime] = None,
    voting_close_at: Optional[datetime] = None,
) -> Category:
    cat = Category(
        name=name,
        type=type_,
        nomination_open_at=nomination_open_at,
        nomination_close_at=nomination_close_at,
        voting_open_at=voting_open_at,
        voting_close_at=voting_close_at,
    )
    await cat.insert()
    return cat


async def update_category(category_id: str, updates: dict) -> Optional[Category]:
    cat = await get_category(category_id)
    if not cat:
        return None
    updates["updated_at"] = datetime.now(timezone.utc)
    for key, value in updates.items():
        if hasattr(cat, key):
            setattr(cat, key, value)
    await cat.save()
    return cat


async def delete_category(category_id: str) -> bool:
    """Delete only if no nominations exist for this category."""
    nom_count = await Nomination.find(Nomination.category_id == category_id).count()
    if nom_count > 0:
        return False
    cat = await get_category(category_id)
    if not cat:
        return False
    await cat.delete()
    return True


# ---------------------------------------------------------------------------
# Nominations
# ---------------------------------------------------------------------------

async def submit_nomination(
    category_id: str,
    nominee_name: str,
    reason: Optional[str] = None,
) -> Nomination:
    """
    Insert a nomination with timing noise.
    NO submitter reference is stored — anonymity guaranteed at model level.
    """
    await _noise_delay()
    nom = Nomination(
        category_id=category_id,
        nominee_name=nominee_name.strip(),
        reason=reason.strip() if reason else None,
    )
    await nom.insert()
    return nom


async def list_nominations(
    category_id: str,
    status: Optional[str] = None,
) -> list[Nomination]:
    query = Nomination.find(Nomination.category_id == category_id)
    if status:
        query = query.find(Nomination.status == status)
    return await query.to_list()


async def list_nominations_with_duplicates(category_id: str) -> dict:
    """
    Return nominations for a category with fuzzy-duplicate hints.
    Uses rapidfuzz to flag pairs with >80% similarity ratio.
    """
    nominations = await list_nominations(category_id, status="pending")
    nom_dicts = [
        {"id": str(n.id), "nominee_name": n.nominee_name, "reason": n.reason, "status": n.status}
        for n in nominations
    ]

    # Build duplicate hint pairs
    duplicate_hints = []
    for i, a in enumerate(nom_dicts):
        for b in nom_dicts[i + 1:]:
            score = fuzz.ratio(a["nominee_name"].lower(), b["nominee_name"].lower())
            if score >= 80:
                duplicate_hints.append({
                    "nomination_a_id": a["id"],
                    "nomination_b_id": b["id"],
                    "name_a": a["nominee_name"],
                    "name_b": b["nominee_name"],
                    "similarity_score": round(score, 1),
                })

    return {"nominations": nom_dicts, "duplicate_hints": duplicate_hints}


async def update_nomination_status(
    nomination_id: str,
    status: str,
) -> Optional[Nomination]:
    from beanie import PydanticObjectId
    nom = await Nomination.get(PydanticObjectId(nomination_id))
    if not nom:
        return None
    nom.status = status
    await nom.save()
    return nom


async def merge_nominations(
    keep_id: str,
    discard_id: str,
    final_name: Optional[str] = None,
) -> Optional[Nomination]:
    """
    Merge two nominations: approve the 'keep' one (optionally rename it),
    mark the 'discard' one as merged → keep_id.
    """
    from beanie import PydanticObjectId
    keep = await Nomination.get(PydanticObjectId(keep_id))
    discard = await Nomination.get(PydanticObjectId(discard_id))
    if not keep or not discard:
        return None

    if final_name:
        keep.nominee_name = final_name.strip()
    keep.status = "approved"
    await keep.save()

    discard.status = "merged"
    discard.merged_into = keep_id
    await discard.save()

    return keep


# ---------------------------------------------------------------------------
# Ballots
# ---------------------------------------------------------------------------

async def publish_ballot(category_id: str) -> list[BallotEntry]:
    """
    Create BallotEntry documents from all approved nominations.
    Marks the category ballot_published = True.
    """
    approved = await list_nominations(category_id, status="approved")
    entries = []
    for nom in approved:
        # Avoid duplicate ballot entries for the same name
        existing = await BallotEntry.find_one(
            BallotEntry.category_id == category_id,
            BallotEntry.nominee_name == nom.nominee_name,
        )
        if not existing:
            entry = BallotEntry(category_id=category_id, nominee_name=nom.nominee_name)
            await entry.insert()
            entries.append(entry)

    # Mark category as published
    cat = await get_category(category_id)
    if cat:
        cat.ballot_published = True
        from datetime import timezone
        cat.updated_at = datetime.now(timezone.utc)
        await cat.save()

    return entries


async def get_ballot(category_id: str) -> list[BallotEntry]:
    return await BallotEntry.find(BallotEntry.category_id == category_id).to_list()


# ---------------------------------------------------------------------------
# Votes
# ---------------------------------------------------------------------------

async def submit_vote(category_id: str, ballot_entry_id: str) -> Vote:
    """
    Insert a vote with timing noise.
    NO voter reference is stored — anonymity guaranteed at model level.
    """
    await _noise_delay()
    vote = Vote(category_id=category_id, ballot_entry_id=ballot_entry_id)
    await vote.insert()
    return vote


# ---------------------------------------------------------------------------
# Results (aggregated only — never raw voter data)
# ---------------------------------------------------------------------------

async def get_results(category_id: str) -> list[dict]:
    """
    Return vote counts per ballot entry for a category.
    Uses MongoDB aggregation — never surfaces voter identity.
    """
    from motor.motor_asyncio import AsyncIOMotorCollection
    from beanie import PydanticObjectId

    pipeline = [
        {"$match": {"category_id": category_id}},
        {"$group": {"_id": "$ballot_entry_id", "vote_count": {"$sum": 1}}},
        {"$sort": {"vote_count": -1}},
    ]

    votes_collection = Vote.get_motor_collection()
    cursor = votes_collection.aggregate(pipeline)
    raw = await cursor.to_list(length=None)

    # Enrich with nominee names from ballot_entries
    results = []
    max_votes = raw[0]["vote_count"] if raw else 0

    for item in raw:
        entry = await BallotEntry.find_one(
            BallotEntry.category_id == category_id,
        )
        # Look up by ballot_entry_id
        try:
            entry = await BallotEntry.get(PydanticObjectId(item["_id"]))
            name = entry.nominee_name if entry else item["_id"]
        except Exception:
            name = item["_id"]

        results.append({
            "ballot_entry_id": item["_id"],
            "nominee_name": name,
            "vote_count": item["vote_count"],
            "is_winner": item["vote_count"] == max_votes and max_votes > 0,
        })

    # Also include ballot entries with 0 votes
    all_entries = await get_ballot(category_id)
    voted_ids = {r["ballot_entry_id"] for r in results}
    for entry in all_entries:
        entry_id = str(entry.id)
        if entry_id not in voted_ids:
            results.append({
                "ballot_entry_id": entry_id,
                "nominee_name": entry.nominee_name,
                "vote_count": 0,
                "is_winner": False,
            })

    return results


async def get_all_results() -> list[dict]:
    """Get results for all categories."""
    categories = await list_categories()
    all_results = []
    for cat in categories:
        cat_results = await get_results(str(cat.id))
        all_results.append({
            "category_id": str(cat.id),
            "category_name": cat.name,
            "category_type": cat.type,
            "results": cat_results,
        })
    return all_results
