"""
Identity Service — exclusively reads/writes the identity layer collections.

This service is the ONLY place in the codebase that touches eligible_voters
and admin_accounts. It exposes simple boolean/None returns to callers so that
routing code never needs to import identity models directly.
"""

from typing import Optional

from app.models.identity import EligibleVoter, AdminAccount
from app.core.security import hash_matric, verify_pin


# ---------------------------------------------------------------------------
# Student eligibility
# ---------------------------------------------------------------------------

async def get_voter(matric: str) -> Optional[EligibleVoter]:
    """Look up a voter by raw matric number (hashes internally)."""
    hashed = hash_matric(matric, admin=False)
    return await EligibleVoter.find_one(EligibleVoter.hashed_matric_id == hashed)


async def get_voter_by_hash(hashed_matric_id: str) -> Optional[EligibleVoter]:
    """Look up a voter directly by their pre-hashed matric ID (from JWT sub).
    Used by nominations/votes routers so raw matric never flows through them.
    """
    return await EligibleVoter.find_one(EligibleVoter.hashed_matric_id == hashed_matric_id)


async def is_eligible(matric: str) -> bool:
    """Return True if matric is in the eligible list."""
    return await get_voter(matric) is not None


async def has_nominated(matric: str, category_id: str) -> bool:
    voter = await get_voter(matric)
    if not voter:
        return False
    return any(r.category_id == category_id and r.has_nominated for r in voter.nomination_records)


async def has_voted(matric: str, category_id: str) -> bool:
    voter = await get_voter(matric)
    if not voter:
        return False
    return any(r.category_id == category_id and r.has_voted for r in voter.vote_records)


async def mark_nominated(matric: str, category_id: str) -> None:
    """Flip the has_nominated flag. Called AFTER the nomination is inserted."""
    voter = await get_voter(matric)
    if not voter:
        return
    for record in voter.nomination_records:
        if record.category_id == category_id:
            record.has_nominated = True
            await voter.save()
            return
    # No existing record for this category — add one
    from app.models.identity import NominationRecord
    voter.nomination_records.append(NominationRecord(category_id=category_id, has_nominated=True))
    await voter.save()


async def mark_nominated_by_hash(hashed_matric_id: str, category_id: str) -> None:
    """Flip has_nominated using pre-hashed matric from JWT sub."""
    voter = await get_voter_by_hash(hashed_matric_id)
    if not voter:
        return
    for record in voter.nomination_records:
        if record.category_id == category_id:
            record.has_nominated = True
            await voter.save()
            return
    from app.models.identity import NominationRecord
    voter.nomination_records.append(NominationRecord(category_id=category_id, has_nominated=True))
    await voter.save()


async def mark_voted(matric: str, category_id: str) -> None:
    """Flip the has_voted flag. Called AFTER the vote is inserted."""
    voter = await get_voter(matric)
    if not voter:
        return
    for record in voter.vote_records:
        if record.category_id == category_id:
            record.has_voted = True
            await voter.save()
            return
    from app.models.identity import VoteRecord
    voter.vote_records.append(VoteRecord(category_id=category_id, has_voted=True))
    await voter.save()


async def mark_voted_by_hash(hashed_matric_id: str, category_id: str) -> None:
    """Flip has_voted using pre-hashed matric from JWT sub."""
    voter = await get_voter_by_hash(hashed_matric_id)
    if not voter:
        return
    for record in voter.vote_records:
        if record.category_id == category_id:
            record.has_voted = True
            await voter.save()
            return
    from app.models.identity import VoteRecord
    voter.vote_records.append(VoteRecord(category_id=category_id, has_voted=True))
    await voter.save()


# ---------------------------------------------------------------------------
# Admin seed / bulk import
# ---------------------------------------------------------------------------

async def seed_voters(matric_list: list[str]) -> dict:
    """Hash and upsert a list of matric numbers into eligible_voters.

    Returns counts of inserted and already-existing records.
    """
    inserted = 0
    skipped = 0

    for matric in matric_list:
        matric = matric.strip()
        if not matric:
            continue
        hashed = hash_matric(matric, admin=False)
        existing = await EligibleVoter.find_one(EligibleVoter.hashed_matric_id == hashed)
        if existing:
            skipped += 1
        else:
            await EligibleVoter(hashed_matric_id=hashed).insert()
            inserted += 1

    return {"inserted": inserted, "skipped": skipped, "total": inserted + skipped}


# ---------------------------------------------------------------------------
# Identity stats (aggregate counts — never raw records)
# ---------------------------------------------------------------------------

async def get_identity_stats(category_ids: list[str]) -> dict:
    """Return aggregate counts only. Never returns hashed matric IDs."""
    total_eligible = await EligibleVoter.count()

    # Count voters who have nominated in at least one category
    total_nominated = await EligibleVoter.find(
        {"nomination_records": {"$elemMatch": {"has_nominated": True}}}
    ).count()

    # Count voters who have voted in at least one category
    total_voted = await EligibleVoter.find(
        {"vote_records": {"$elemMatch": {"has_voted": True}}}
    ).count()

    return {
        "total_eligible": total_eligible,
        "total_nominated": total_nominated,
        "total_voted": total_voted,
    }


# ---------------------------------------------------------------------------
# Admin authentication
# ---------------------------------------------------------------------------

async def authenticate_admin(matric: str, pin: str) -> Optional[AdminAccount]:
    """Verify admin matric + PIN. Returns the AdminAccount or None."""
    hashed = hash_matric(matric, admin=True)
    admin = await AdminAccount.find_one(
        AdminAccount.hashed_matric_id == hashed,
        AdminAccount.is_active == True,
    )
    if not admin:
        return None
    if not verify_pin(pin, admin.hashed_pin):
        return None
    return admin


async def create_admin(matric: str, pin: str, display_name: Optional[str] = None) -> AdminAccount:
    """Create an admin account. Should only be called via a protected bootstrap endpoint."""
    from app.core.security import hash_pin
    hashed_matric = hash_matric(matric, admin=True)
    hashed_pin_val = hash_pin(pin)
    admin = AdminAccount(
        hashed_matric_id=hashed_matric,
        hashed_pin=hashed_pin_val,
        display_name=display_name,
    )
    await admin.insert()
    return admin
