"""Wire contract between buyer and seller over MIP-003 (/start_job, /status).

input_data uses only string values so it fits the quickstart template's
`input_data: dict[str, str]` and the pip-masumi hashing unchanged.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from common.documents import Document
from common.hashing import package_hash
from common.invoice import ExtractedInvoice

# Returned by the seller's GET /input_schema (MIP-003 typed-array format).
INPUT_SCHEMA: dict[str, Any] = {
    "input_data": [
        {
            "id": "documents_json",
            "type": "textarea",
            "name": "Documents",
            "data": {
                "description": "JSON array of {filename, content_base64}. ISDOC (XML) required, PDF optional."
            },
        },
        {
            "id": "package_sha256",
            "type": "string",
            "name": "Package SHA-256",
            "data": {"description": "common.hashing.package_hash over per-document sha256 digests."},
        },
    ]
}


def new_purchaser_id() -> str:
    """identifierFromPurchaser: Masumi requires hex, 14-26 chars."""
    return secrets.token_hex(8)


class JobInput(BaseModel):
    documents: list[Document] = Field(min_length=1, max_length=50)
    package_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _package_hash_matches(self) -> JobInput:
        actual = package_hash(d.doc_hash for d in self.documents)
        if actual != self.package_sha256:
            raise ValueError("package_sha256 does not match the documents")
        return self

    @classmethod
    def build(cls, documents: list[Document]) -> JobInput:
        return cls(documents=documents, package_sha256=package_hash(d.doc_hash for d in documents))

    def to_input_data(self) -> dict[str, str]:
        """The exact dict sent as /start_job input_data and hashed into inputHash."""
        docs = [d.model_dump(mode="json") for d in self.documents]
        return {
            "documents_json": json.dumps(docs, separators=(",", ":"), ensure_ascii=False),
            "package_sha256": self.package_sha256,
        }

    @classmethod
    def from_input_data(cls, input_data: Mapping[str, Any]) -> JobInput:
        docs = json.loads(input_data["documents_json"])
        return cls(documents=[Document(**d) for d in docs], package_sha256=input_data["package_sha256"])


class JobResult(BaseModel):
    """Serialized with to_result_string() into MIP-003 /status `result`."""

    seller_name: str
    package_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    invoices: list[ExtractedInvoice]

    def to_result_string(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_result_string(cls, result: str) -> JobResult:
        return cls.model_validate_json(result)


class JobStatus(StrEnum):
    AWAITING_PAYMENT = "awaiting_payment"
    AWAITING_INPUT = "awaiting_input"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StartJobResponse(BaseModel):
    """Seller's /start_job answer; the buyer copies it into Masumi POST /purchase.

    Times are unix milliseconds as strings, exactly as the Payment Service
    returns them and as POST /purchase expects them.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    job_id: str = Field(validation_alias=AliasChoices("job_id", "id"))
    blockchain_identifier: str = Field(validation_alias=AliasChoices("blockchainIdentifier", "blockchain_identifier"))
    agent_identifier: str = Field(validation_alias=AliasChoices("agentIdentifier", "agent_identifier"))
    seller_vkey: str = Field(validation_alias=AliasChoices("sellerVKey", "sellerVkey", "seller_vkey"))
    identifier_from_purchaser: str = Field(
        validation_alias=AliasChoices("identifierFromPurchaser", "identifier_from_purchaser")
    )
    input_hash: str = Field(validation_alias=AliasChoices("input_hash", "inputHash"))
    pay_by_time: str = Field(validation_alias=AliasChoices("payByTime", "pay_by_time"))
    submit_result_time: str = Field(validation_alias=AliasChoices("submitResultTime", "submit_result_time"))
    unlock_time: str = Field(validation_alias=AliasChoices("unlockTime", "unlock_time"))
    external_dispute_unlock_time: str = Field(
        validation_alias=AliasChoices("externalDisputeUnlockTime", "external_dispute_unlock_time")
    )

    @field_validator("pay_by_time", "submit_result_time", "unlock_time", "external_dispute_unlock_time", mode="before")
    @classmethod
    def _int_to_str(cls, value: Any) -> Any:
        return str(value) if isinstance(value, int) else value


class StatusResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    job_id: str | None = None
    status: JobStatus
    result: str | None = None  # JobResult.to_result_string() when completed
