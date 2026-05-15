"""Cross-language parity tests.

Each test loads the SAME JSON fixture used by Vitest on the TS side and
parses it through the generated Pydantic model. If Zod and Pydantic
diverge on identical bytes, parity is broken and this test fails.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from aeogen_shared import Site, Workspace


def _load(fixtures_dir: Path, name: str) -> dict[str, object]:
    raw = (fixtures_dir / name).read_text(encoding="utf8")
    data: dict[str, object] = json.loads(raw)
    return data


def test_site_fixture_parses(fixtures_dir: Path) -> None:
    data = _load(fixtures_dir, "site.valid.json")
    site = Site.model_validate(data)
    assert site.id == UUID("11111111-1111-4111-8111-111111111111")
    assert site.workspace_id == UUID("22222222-2222-4222-8222-222222222222")
    assert str(site.url).rstrip("/") == "https://example.com"
    assert site.default_language == "tr"
    assert site.sector == "fashion"


def test_workspace_fixture_parses(fixtures_dir: Path) -> None:
    data = _load(fixtures_dir, "workspace.valid.json")
    ws = Workspace.model_validate(data)
    assert ws.id == UUID("33333333-3333-4333-8333-333333333333")
    assert ws.org_id == UUID("44444444-4444-4444-8444-444444444444")
    assert ws.name == "Acme Agency Client #1"
    assert ws.slug == "acme-agency-client-1"
    assert ws.created_at.isoformat().startswith("2026-05-15T12:34:56")


def test_site_rejects_extra_key(fixtures_dir: Path) -> None:
    data = _load(fixtures_dir, "site.valid.json")
    data["injected_field"] = "should fail"
    with pytest.raises(ValidationError):
        Site.model_validate(data)
