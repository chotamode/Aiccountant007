"""V1 criteria 1, 4, 5: both profiles serve MIP-003, a job completes, no keys in git."""

from __future__ import annotations

import re
from decimal import Decimal
import subprocess

import pytest
from fastapi.testclient import TestClient

from common.mip003 import INPUT_SCHEMA, JobInput, JobResult, StartJobResponse
from seller.app import create_app
from seller.profiles import HONEST, SLOPPY, load_profile
from seller.tests.conftest import REPO


@pytest.mark.parametrize("key,port", [("honest", 8001), ("sloppy", 8002)])
def test_profile_starts(monkeypatch, key, port):
    monkeypatch.setenv("FIRM_PROFILE", key)
    monkeypatch.setenv("PORT", str(port))
    client = TestClient(create_app(payment_mode="off"))
    r = client.get("/availability")
    assert r.status_code == 200
    assert r.json()["agentName"] == load_profile(key).name
    assert client.get("/input_schema").json() == INPUT_SCHEMA


@pytest.mark.parametrize("profile", [HONEST, SLOPPY])
def test_start_job_to_completed(fixture_documents, profile):
    client = TestClient(create_app(profile, payment_mode="off"))
    job = JobInput.build(fixture_documents)
    r = client.post("/start_job", json={"identifier_from_purchaser": "abcdef0123456789",
                                        "input_data": job.to_input_data()})
    assert r.status_code == 200, r.text
    start = StartJobResponse.model_validate(r.json())
    assert start.blockchain_identifier.startswith("SIMULATED-")
    assert int(start.pay_by_time) < int(start.submit_result_time) < int(start.unlock_time)

    status = client.get("/status", params={"job_id": start.job_id}).json()
    assert status["status"] == "completed"
    result = JobResult.from_result_string(status["result"])
    assert result.seller_name == profile.name
    assert result.package_sha256 == job.package_sha256
    assert len(result.invoices) == len(fixture_documents)

    ledger = client.get("/ledger").json()
    revenue = [e for e in ledger["entries"] if e["kind"] == "revenue"]
    assert [Decimal(e["amount"]) for e in revenue] == [Decimal(profile.price_lovelace) / 1_000_000]
    assert all(e["simulated"] for e in ledger["entries"])


def test_start_job_accepts_key_value_list(fixture_documents):
    client = TestClient(create_app(HONEST, payment_mode="off"))
    data = JobInput.build(fixture_documents).to_input_data()
    r = client.post("/start_job", json={"input_data": [{"key": k, "value": v} for k, v in data.items()]})
    assert r.status_code == 200, r.text


def test_bad_input_is_400():
    client = TestClient(create_app(HONEST, payment_mode="off"))
    r = client.post("/start_job", json={"input_data": {"documents_json": "[]", "package_sha256": "0" * 64}})
    assert r.status_code == 400
    assert client.get("/status", params={"job_id": "nope"}).status_code == 404


def test_example_output():
    client = TestClient(create_app(HONEST, payment_mode="off"))
    JobResult.from_result_string(client.get("/example_output.json").json()["result"])


SECRET = re.compile(r"(?i:mnemonic|api[_-]?key|admin[_-]?key|token)[ \t]*[=:][ \t]*['\"]?(?=[A-Z_]*[a-z0-9])[A-Za-z0-9_\-]{16,}")


def test_no_keys_in_repo():
    files = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    assert ".env" not in files
    leaks = []
    for name in files:
        path = REPO / name
        if path.suffix in {".py", ".md", ".toml", ".json", ".example", ".yml", ".yaml", ".env", ""}:
            text = path.read_text(errors="ignore")
            leaks += [f"{name}: {m.group(0)[:40]}" for m in SECRET.finditer(text)]
    assert not leaks, leaks
