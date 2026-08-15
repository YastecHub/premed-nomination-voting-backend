"""
Pytest configuration for async FastAPI tests.
Uses an in-memory MongoDB via mongomock-motor for isolation.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
