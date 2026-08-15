"""
Inspect and deduplicate eligible voters in MongoDB.
Ensures exactly the 126 pharmacy voters from voters.csv are in the database.
"""
import asyncio
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import connect_db, disconnect_db
from app.models.identity import EligibleVoter
from app.core.security import hash_matric


async def main():
    print("Connecting to MongoDB...")
    await connect_db()

    csv_path = os.path.join(os.path.dirname(__file__), "voters.csv")
    valid_matrics = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            m = row.get("matric_number", "").strip()
            if m:
                valid_matrics.append(m)

    print(f"Target count from voters.csv: {len(valid_matrics)}")

    # Check current DB count
    all_voters = await EligibleVoter.find_all().to_list()
    print(f"Current count in MongoDB eligible_voters: {len(all_voters)}")

    # Compute expected hashes
    expected_hashes = set(hash_matric(m) for m in valid_matrics)

    # Find duplicates or extra entries
    seen_hashes = set()
    duplicates_deleted = 0
    extras_deleted = 0

    for voter in all_voters:
        h = voter.hashed_matric_id
        if h in seen_hashes or h not in expected_hashes:
            await voter.delete()
            if h in seen_hashes:
                duplicates_deleted += 1
            else:
                extras_deleted += 1
        else:
            seen_hashes.add(h)

    # Insert any missing from valid_matrics
    missing_inserted = 0
    for h in expected_hashes:
        if h not in seen_hashes:
            new_voter = EligibleVoter(hashed_matric_id=h)
            await new_voter.insert()
            seen_hashes.add(h)
            missing_inserted += 1

    final_voters = await EligibleVoter.find_all().to_list()
    print("\n--- Deduplication / Cleanup Results ---")
    print(f"Duplicates removed: {duplicates_deleted}")
    print(f"Extraneous entries removed: {extras_deleted}")
    print(f"Missing inserted: {missing_inserted}")
    print(f"Final total eligible voters in DB: {len(final_voters)}")

    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(main())
