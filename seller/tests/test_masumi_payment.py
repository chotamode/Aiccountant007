"""Tests for seller/masumi_payment.py using a fake Payment Service node."""

from __future__ import annotations

import httpx
import pytest

from seller import masumi_payment
from seller.masumi_payment import MasumiPaymentError


def test_validate_config(monkeypatch):
    monkeypatch.delenv("PAYMENT_SERVICE_URL", raising=False)
    monkeypatch.delenv("PAYMENT_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_IDENTIFIER", raising=False)

    with pytest.raises(MasumiPaymentError, match="PAYMENT_SERVICE_URL"):
        masumi_payment.validate_config()

    monkeypatch.setenv("PAYMENT_SERVICE_URL", "http://node:3001")
    with pytest.raises(MasumiPaymentError, match="PAYMENT_API_KEY"):
        masumi_payment.validate_config()

    monkeypatch.setenv("PAYMENT_API_KEY", "key-1")
    with pytest.raises(MasumiPaymentError, match="AGENT_IDENTIFIER"):
        masumi_payment.validate_config()

    monkeypatch.setenv("AGENT_IDENTIFIER", "agent-1")
    # Should not raise now
    masumi_payment.validate_config()


def test_wait_funds_locked_retries_transient_error(monkeypatch):
    monkeypatch.setenv("PAYMENT_SERVICE_URL", "http://node:3001")
    monkeypatch.setenv("PAYMENT_API_KEY", "key-1")

    call_count = 0

    def mock_post(url, json=None, headers=None, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ConnectError("Connection refused")
        return httpx.Response(200, json={"data": {"onChainState": "FundsLocked"}})

    monkeypatch.setattr(httpx, "post", mock_post)

    # Should retry through the first error and succeed on the second attempt
    masumi_payment.wait_funds_locked("test-bc-id", timeout=5.0, poll_interval=0.01)
    assert call_count >= 2


def test_submit_result_retries(monkeypatch):
    monkeypatch.setenv("PAYMENT_SERVICE_URL", "http://node:3001")
    monkeypatch.setenv("PAYMENT_API_KEY", "key-1")

    call_count = 0

    def mock_post(url, json=None, headers=None, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.ReadTimeout("Timeout")
        return httpx.Response(200, json={"data": {"status": "success"}})

    monkeypatch.setattr(httpx, "post", mock_post)

    masumi_payment.submit_result(
        "test-bc-id",
        "purchaser-123",
        {"input": "val"},
        "result-string",
        max_retries=5,
        retry_interval=0.01,
    )
    assert call_count == 3


def test_authorize_refund_retries(monkeypatch):
    monkeypatch.setenv("PAYMENT_SERVICE_URL", "http://node:3001")
    monkeypatch.setenv("PAYMENT_API_KEY", "key-1")

    call_count = 0

    def mock_post(url, json=None, headers=None, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500, text="internal error")
        return httpx.Response(200, json={"data": {"status": "success"}})

    monkeypatch.setattr(httpx, "post", mock_post)

    masumi_payment.authorize_refund("test-bc-id", max_retries=3, retry_interval=0.01)
    assert call_count == 2
