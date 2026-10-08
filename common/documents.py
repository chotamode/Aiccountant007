"""Documents the client hands over to the accounting firm."""

from __future__ import annotations

import base64
import binascii
from enum import StrEnum
from functools import cached_property

from pydantic import BaseModel, ConfigDict, Field, field_validator

from common.hashing import doc_hash


class DocumentFormat(StrEnum):
    ISDOC = "isdoc"  # Czech e-invoice XML, required
    PDF = "pdf"  # needs OCR (Apify), optional
    UNKNOWN = "unknown"


class Document(BaseModel):
    """One file as it travels inside the /start_job input.

    Only `filename` and `content_base64` are serialized; everything else is
    derived, so the Masumi input hash depends on the file bytes and name only.
    """

    model_config = ConfigDict(frozen=True)

    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)

    @field_validator("content_base64")
    @classmethod
    def _must_be_base64(cls, value: str) -> str:
        try:
            base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("content_base64 is not valid base64") from exc
        return value

    @classmethod
    def from_bytes(cls, filename: str, content: bytes) -> Document:
        return cls(filename=filename, content_base64=base64.b64encode(content).decode("ascii"))

    @cached_property
    def content(self) -> bytes:
        return base64.b64decode(self.content_base64)

    @cached_property
    def doc_hash(self) -> str:
        return doc_hash(self.content)

    @property
    def format(self) -> DocumentFormat:
        name = self.filename.lower()
        if name.endswith((".isdoc", ".xml")):
            return DocumentFormat.ISDOC
        if name.endswith(".pdf"):
            return DocumentFormat.PDF
        return DocumentFormat.UNKNOWN


class DocumentManifestEntry(BaseModel):
    """What the dashboard and the vault show instead of the raw bytes."""

    filename: str
    doc_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    format: DocumentFormat

    @classmethod
    def of(cls, document: Document) -> DocumentManifestEntry:
        return cls(
            filename=document.filename,
            doc_hash=document.doc_hash,
            size_bytes=len(document.content),
            format=document.format,
        )
