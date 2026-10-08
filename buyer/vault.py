"""Document vault: what the client hands over, and the hashes that prove it.

doc_hash per file and package_sha256 over the package end up inside the
Masumi inputHash (docs/ARCHITECTURE.md, "Цепочка доказательств"). Hashing
goes through common.hashing only, so buyer and seller always agree.
"""

from __future__ import annotations

from pathlib import Path

from common.documents import Document, DocumentFormat, DocumentManifestEntry
from common.mip003 import JobInput


def _format(path: Path) -> DocumentFormat:
    # Document.format looks at the filename only, so no need to read the file yet.
    return Document.model_construct(filename=path.name).format


def load_documents(directory: str | Path, pattern: str = "*") -> list[Document]:
    """ISDOC and PDF files in `directory` matching `pattern`, sorted by filename.

    The order is fixed on purpose: documents_json keeps it and inputHash covers it.
    """
    paths = sorted(p for p in Path(directory).glob(pattern) if p.is_file())
    return [
        Document.from_bytes(p.name, p.read_bytes())
        for p in paths
        if _format(p) != DocumentFormat.UNKNOWN
    ]


def manifest(documents: list[Document]) -> list[DocumentManifestEntry]:
    """Name, hash, size and format of each file: what the dashboard shows instead of bytes."""
    return [DocumentManifestEntry.of(d) for d in documents]


def build_job_input(documents: list[Document]) -> JobInput:
    """The package as it goes into /start_job, with package_sha256 computed."""
    return JobInput.build(documents)
