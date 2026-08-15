from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.core.config import get_settings

settings = get_settings()

# We store the client at module level so it can be reused across requests
_client: AsyncIOMotorClient | None = None


async def connect_db():
    """Initialize Motor client and Beanie ODM.

    Collections are split into identity and content modules deliberately.
    Beanie document classes from both modules are registered here — but the
    models themselves have no cross-imports, enforcing separation at the
    code architecture level.
    """
    global _client

    # Import models here (not at top-level) to keep identity/content modules
    # isolated from each other — neither imports the other.
    from app.models.identity import EligibleVoter, AdminAccount
    from app.models.content import Category, Nomination, BallotEntry, Vote

    _client = AsyncIOMotorClient(settings.mongodb_uri)
    db = _client[settings.db_name]

    await init_beanie(
        database=db,
        document_models=[
            # Identity layer
            EligibleVoter,
            AdminAccount,
            # Content layer
            Category,
            Nomination,
            BallotEntry,
            Vote,
        ],
    )


async def disconnect_db():
    global _client
    if _client:
        _client.close()
        _client = None
