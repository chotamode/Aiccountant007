"""Hash definitions shared by buyer and seller.

Both sides MUST compute hashes through these functions, otherwise the proof
of document hand-over and the Masumi input/output hashes will not match.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

import canonicaljson


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def doc_hash(content: bytes) -> str:
    """sha256 of the raw document bytes (after base64 decoding)."""
    return sha256_hex(content)


def package_hash(doc_hashes: Iterable[str]) -> str:
    """Order-independent hash of a document package.

    sha256 over the per-document hex digests, sorted and joined with "\\n".
    Duplicates are kept: sending the same file twice changes the package hash.
    """
    joined = "\n".join(sorted(doc_hashes))
    return sha256_hex(joined.encode("utf-8"))


def masumi_input_hash(input_data: Mapping[str, Any], identifier_from_purchaser: str) -> str:
    """MIP-004 input hash, identical to pip-masumi `create_masumi_input_hash`.

    sha256("<identifier_from_purchaser>;<canonical JSON of input_data>").
    Keep input_data free of floats: canonical JSON of floats is not portable.
    """
    canonical = canonicaljson.encode_canonical_json(dict(input_data)).decode("utf-8")
    return sha256_hex(f"{identifier_from_purchaser};{canonical}".encode())


def masumi_output_hash(output: str, identifier_from_purchaser: str) -> str:
    """MIP-004 output hash, identical to pip-masumi `create_masumi_output_hash`.

    The output string is JSON-escaped (without surrounding quotes) first.
    """
    escaped = json.dumps(output, ensure_ascii=False)[1:-1]
    return sha256_hex(f"{identifier_from_purchaser};{escaped}".encode())
