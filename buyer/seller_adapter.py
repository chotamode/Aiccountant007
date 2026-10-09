"""One interface to sellers: the SellerAdapter Protocol and Mip003Adapter for our own firms.

A SokosumiAdapter is cut for now: no key and no recorded fixtures.

Seller answers are untrusted input. They are only parsed through the pydantic
models of common/, never executed, and every failure surfaces as SellerAdapterError.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, TypeVar

import httpx
from pydantic import AliasChoices, BaseModel, Field, ValidationError

from common.mip003 import JobInput, StartJobResponse, StatusResponse

BODY_PREVIEW_CHARS = 200

_Model = TypeVar("_Model", bound=BaseModel)


class SellerAdapterError(Exception):
    """The seller is unreachable, answered with a non-2xx status or with something unparsable."""


class SellerAvailability(BaseModel):
    """Parsed GET /availability of our sellers (seller/app.py); other keys are ignored."""

    name: str = Field(validation_alias=AliasChoices("agentName", "name"))
    profile: str | None = None
    price_lovelace: int = Field(ge=0)
    payment_mode: str | None = None  # "off" = SIMULATED payments, "masumi" = real escrow


class DisputeResponse(BaseModel):
    job_id: str = ""
    authorized: bool = False
    pending: bool = False
    reason: str = ""
    message: str = ""
    simulated: bool = False

    def model_post_init(self, context: object, /) -> None:
        if not self.message and self.reason:
            self.message = self.reason
        elif not self.reason and self.message:
            self.reason = self.message


class SellerAdapter(Protocol):
    def start(self, job_input: JobInput, purchaser_id: str) -> StartJobResponse: ...

    def status(self, job_id: str) -> StatusResponse: ...

    def dispute(self, job_id: str, report: object) -> DisputeResponse: ...


class Mip003Adapter:
    """Our own firms, MIP-003 over HTTP.

    An injected client is used as is (tests pass a fastapi TestClient). Otherwise
    one is created for base_url with the given timeout.
    """

    def __init__(self, base_url: str, client: httpx.Client | None = None, timeout: float = 30.0) -> None:
        self.base_url = base_url
        self._client = client if client is not None else httpx.Client(base_url=base_url, timeout=timeout)

    def availability(self) -> SellerAvailability:
        return self._call(SellerAvailability, "GET", "/availability")

    def start(self, job_input: JobInput, purchaser_id: str) -> StartJobResponse:
        # input_data goes out exactly as to_input_data() returned it: inputHash is computed from it.
        body = {"identifier_from_purchaser": purchaser_id, "input_data": job_input.to_input_data()}
        return self._call(StartJobResponse, "POST", "/start_job", body=body)

    def status(self, job_id: str) -> StatusResponse:
        return self._call(StatusResponse, "GET", "/status", params={"job_id": job_id})

    def dispute(self, job_id: str, report: object) -> DisputeResponse:
        rep_data = report.model_dump(mode="json") if hasattr(report, "model_dump") else report
        body = {"job_id": job_id, "report": rep_data}
        return self._call(DisputeResponse, "POST", "/dispute", body=body)

    def _call(
        self,
        model: type[_Model],
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        body: Mapping[str, object] | None = None,
    ) -> _Model:
        where = f"{method} {self.base_url}{path}"
        try:
            response = self._client.request(method, path, params=params, json=body)
        except httpx.HTTPError as exc:
            raise SellerAdapterError(f"{where}: {type(exc).__name__}: {exc}") from exc
        preview = response.text[:BODY_PREVIEW_CHARS]
        if not response.is_success:
            raise SellerAdapterError(f"{where}: HTTP {response.status_code}: {preview!r}")
        try:
            return model.model_validate(response.json())
        except (ValueError, ValidationError) as exc:  # not JSON, or not the shape the model wants
            raise SellerAdapterError(f"{where}: unparsable answer: {preview!r}") from exc
