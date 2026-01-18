"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

import pytest

# Add daemon directory to path for imports
daemon_path = Path(__file__).parent.parent / "daemon"
sys.path.insert(0, str(daemon_path))


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()
