"""Pytest configuration for cross-language parity tests.

The TS test fixtures (`tests/fixtures/*.valid.json`) are the SAME bytes parsed
by both Vitest (Zod) and pytest (Pydantic). Keeping the fixture directory
shared is the whole point of the parity exercise: change the JSON once,
both languages must still accept it.
"""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Absolute path to the shared TS/Python fixture directory."""
    return Path(__file__).resolve().parent.parent / "fixtures"
