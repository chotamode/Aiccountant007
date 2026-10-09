"""B3: Mip003Adapter against the real seller.app (PAYMENT_MODE=off) through TestClient."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from buyer.seller_adapter import (
    BODY_PREVIEW_CHARS,
    Mip003Adapter,
    SellerAdapter,
    SellerAdapterError,
    SellerAvailability,
)
from common.documents import Document
from common.hashing import masumi_input_hash
from common.mip003 import JobInput, JobResult, JobStatus
from seller.app import create_app
from seller.profiles import HONEST, SLOPPY, FirmProfile

FIXTURES = Path(__file__).resolve().parents[2] / "seller" / "tests" / "fixtures"
PURCHASER_ID = "abcdef0123456789"  # hex, 14-26 chars, as Masumi wants
BASE_URL = "http://seller.test"

Handler = Callable[[httpx.Request], httpx.Response]


def make_job_input() -> JobInput:
    paths = sorted(FIXTURES.glob("*.isdoc"))
    assert paths, f"no ISDOC fixtures in {FIXTURES}"
    return JobInput.build([Document.from_bytes(p.name, p.read_bytes()) for p in paths])


def real_seller(profile: FirmProfile) -> Mip003Adapter:
    """The actual seller app, in-process: no network."""
    return Mip003Adapter(BASE_URL, client=TestClient(create_app(profile, payment_mode="off")))  # type: ignore[arg-type]


def fake_seller(handler: Handler) -> Mip003Adapter:
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=BASE_URL)
    return Mip003Adapter(BASE_URL, client=client)


def refuse_connection(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


@pytest.mark.parametrize("profile", [HONEST, SLOPPY], ids=lambda p: p.key)
def test_full_cycle(profile: FirmProfile) -> None:
    adapter = real_seller(profile)
    job_input = make_job_input()

    assert adapter.availability() == SellerAvailability(
        name=profile.name, profile=profile.key, price_lovelace=profile.price_lovelace, payment_mode="off"
    )

    seller: SellerAdapter = adapter  # start and status are all the buyer needs from any seller
    start = seller.start(job_input, PURCHASER_ID)
    assert start.identifier_from_purchaser == PURCHASER_ID
    assert start.input_hash == masumi_input_hash(job_input.to_input_data(), PURCHASER_ID)

    status = seller.status(start.job_id)
    assert status.job_id == start.job_id
    assert status.status == JobStatus.COMPLETED
    assert status.result is not None
    result = JobResult.from_result_string(status.result)
    assert result.seller_name == profile.name
    assert result.package_sha256 == job_input.package_sha256
    assert len(result.invoices) == len(job_input.documents)


def test_unknown_job_id_is_an_adapter_error() -> None:
    with pytest.raises(SellerAdapterError, match="404"):
        real_seller(HONEST).status("no-such-job")


def test_transport_failure_is_an_adapter_error() -> None:
    adapter = fake_seller(refuse_connection)
    with pytest.raises(SellerAdapterError, match="ConnectError"):
        adapter.availability()
    with pytest.raises(SellerAdapterError, match="ConnectError"):
        adapter.start(make_job_input(), PURCHASER_ID)
    with pytest.raises(SellerAdapterError, match="ConnectError"):
        adapter.status("job-1")


def test_non_2xx_message_has_the_status_and_only_the_start_of_the_body() -> None:
    adapter = fake_seller(lambda request: httpx.Response(503, text="x" * 1000))
    with pytest.raises(SellerAdapterError) as info:
        adapter.availability()
    message = str(info.value)
    assert "503" in message
    assert "x" * BODY_PREVIEW_CHARS in message
    assert "x" * (BODY_PREVIEW_CHARS + 1) not in message


def test_answer_that_is_not_json_is_an_adapter_error() -> None:
    adapter = fake_seller(lambda request: httpx.Response(200, text="<html>maintenance</html>"))
    with pytest.raises(SellerAdapterError, match="unparsable"):
        adapter.availability()


@pytest.mark.parametrize(
    ("call", "payload"),
    [
        (lambda a: a.availability(), ["not", "an", "object"]),
        (lambda a: a.availability(), {"status": "available"}),  # no agentName, no price
        (lambda a: a.availability(), {"agentName": "X", "price_lovelace": -1}),
        (lambda a: a.start(make_job_input(), PURCHASER_ID), {"job_id": "j1"}),  # no payment fields
        (lambda a: a.status("j1"), {"status": "exploded"}),
    ],
    ids=["list", "no-name", "negative-price", "short-start", "unknown-status"],
)
def test_answer_of_the_wrong_shape_is_an_adapter_error(
    call: Callable[[Mip003Adapter], object], payload: object
) -> None:
    adapter = fake_seller(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(SellerAdapterError, match="unparsable"):
        call(adapter)


def test_requests_follow_mip003() -> None:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(500)

    adapter = fake_seller(record)
    job_input = make_job_input()
    for call in (lambda: adapter.start(job_input, PURCHASER_ID), lambda: adapter.status("a b&job_id=2")):
        with pytest.raises(SellerAdapterError, match="500"):
            call()

    start, status = seen
    assert (start.method, start.url.path) == ("POST", "/start_job")
    assert json.loads(start.content) == {
        "identifier_from_purchaser": PURCHASER_ID,
        "input_data": job_input.to_input_data(),
    }
    assert (status.method, status.url.path) == ("GET", "/status")
    assert status.url.params.multi_items() == [("job_id", "a b&job_id=2")]


def test_dispute_endpoint_authorizes_for_sloppy() -> None:
    from common.checks import Check, CheckCode, Severity, VerificationReport

    adapter = real_seller(SLOPPY)
    job_input = make_job_input()
    start = adapter.start(job_input, PURCHASER_ID)

    report = VerificationReport(
        seller_id=SLOPPY.name,
        package_sha256=job_input.package_sha256,
        checks=[
            Check(
                code=CheckCode.VAT_RATE_ALLOWED,
                passed=False,
                severity=Severity.ERROR,
                message="bad rate",
            )
        ],
    )

    ans = adapter.dispute(start.job_id, report)
    assert ans.authorized
    assert ans.simulated

