from __future__ import annotations

from pathlib import Path

import pytest

from common.documents import Document

FIXTURES = Path(__file__).parent / "fixtures"
REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"


def documents_from(paths: list[Path]) -> list[Document]:
    return [Document.from_bytes(p.name, p.read_bytes()) for p in paths]


@pytest.fixture
def fixture_documents() -> list[Document]:
    return documents_from(sorted(FIXTURES.glob("*.isdoc")))
