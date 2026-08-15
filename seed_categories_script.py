"""
Seed awards categories into MongoDB.
Run with:
    uv run python seed_categories_script.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import connect_db, disconnect_db
from app.models.content import Category


AWARDS_LIST = [
    # Leadership & Office
    {"name": "Best Class Representative", "type": "award"},
    {"name": "Best Assistant Class Representative", "type": "award"},
    {"name": "Most Active Person in Office (Outstanding Executive)", "type": "award"},
    {"name": "Most Helpful Student (Unsung Hero)", "type": "award"},

    # Academic
    {"name": "Brain of the Class (Academic Scholar)", "type": "award"},
    {"name": "Most Hardworking Student", "type": "award"},
    {"name": "The Lifesaver (Best Peer Tutor)", "type": "award"},
    {"name": "Most Likely to be a World-Class Specialist", "type": "award"},

    # Lifestyle & Personality
    {"name": "Most Friendly & Approachable", "type": "award"},
    {"name": "Best Dressed (Male)", "type": "award"},
    {"name": "Best Dressed (Female)", "type": "award"},
    {"name": "Entrepreneur of the Year", "type": "award"},
    {"name": "Most Creative & Multi-Talented", "type": "award"},
    {"name": "Sports Person of the Year", "type": "award"},

    # Fun & Relatable
    {"name": "Most Humorous (Class Comedian)", "type": "award"},
    {"name": "The Stealth Student (Rarely Seen, Always Passes)", "type": "award"},
    {"name": "Most Likely to Forget Lab Coat / Stethoscope", "type": "award"},
]


async def main():
    print("Connecting to MongoDB...")
    await connect_db()

    now = datetime.now(timezone.utc)
    # Open nominations immediately for 7 days
    nom_open = now - timedelta(hours=1)
    nom_close = now + timedelta(days=7)

    inserted = 0
    skipped = 0

    print(f"Checking and seeding {len(AWARDS_LIST)} categories...")

    for item in AWARDS_LIST:
        existing = await Category.find_one(Category.name == item["name"])
        if existing:
            skipped += 1
            print(f" - [SKIPPED] {item['name']} (already exists)")
        else:
            cat = Category(
                name=item["name"],
                type=item["type"],
                nomination_open_at=nom_open,
                nomination_close_at=nom_close,
                nomination_force_closed=False,
                voting_force_closed=False,
                ballot_published=False,
            )
            await cat.insert()
            inserted += 1
            print(f" + [INSERTED] {item['name']}")

    print("\n--- Seeding Summary ---")
    print(f"Total categories: {len(AWARDS_LIST)}")
    print(f"Inserted: {inserted}")
    print(f"Skipped:  {skipped}")

    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(main())
