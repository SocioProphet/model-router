"""Tests for the SourceOS model catalog entry admission validator."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "validate_model_catalog_entry.py"

spec = importlib.util.spec_from_file_location("validate_model_catalog_entry", MODULE_PATH)
assert spec and spec.loader
_mod = importlib.util.module_from_spec(spec)
sys.modules["validate_model_catalog_entry"] = _mod
spec.loader.exec_module(_mod)

admit_entry = _mod.admit_entry
validate_file = _mod.validate_file

ADMITTED_PATH = ROOT / "examples" / "model-catalog-entry.admitted.json"
DENIED_EPISTEMIC_PATH = ROOT / "examples" / "model-catalog-entry.denied.epistemic-rejected.json"
DENIED_STEERING_PATH = ROOT / "examples" / "model-catalog-entry.denied.steering-diff-unsupported.json"


def _load(path: Path) -> dict:
    raw = json.loads(path.read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def _admitted() -> dict:
    return _load(ADMITTED_PATH)


# ── Admitted fixture ─────────────────────────────────────────────────────────

def test_admitted_fixture_passes():
    result = validate_file(ADMITTED_PATH)
    assert result.admitted, result.denials
    assert result.denials == []
    assert result.evidence_ref is not None
    assert "admitted" in result.evidence_ref


# ── Gate 1: content_hash_mismatch ────────────────────────────────────────────

def test_content_hash_not_hex_denies():
    entry = _admitted()
    entry["artifact"]["contentHash"] = "not-a-hash"
    result = admit_entry(entry)
    assert not result.admitted
    assert "content_hash_mismatch" in result.denials


def test_content_hash_too_short_denies():
    entry = _admitted()
    entry["artifact"]["contentHash"] = "deadbeef"
    result = admit_entry(entry)
    assert not result.admitted
    assert "content_hash_mismatch" in result.denials


def test_content_hash_uppercase_denies():
    entry = _admitted()
    entry["artifact"]["contentHash"] = "DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF"
    result = admit_entry(entry)
    assert not result.admitted
    assert "content_hash_mismatch" in result.denials


def test_encrypted_false_denies():
    entry = _admitted()
    entry["artifact"]["encrypted"] = False
    result = admit_entry(entry)
    assert not result.admitted
    assert "content_hash_mismatch" in result.denials


def test_delivered_bytes_hash_match_admits():
    import hashlib
    payload = b"example artifact payload"
    digest = hashlib.sha256(payload).hexdigest()
    entry = _admitted()
    entry["artifact"]["contentHash"] = digest
    result = admit_entry(entry, delivered_bytes=payload)
    assert result.admitted, result.denials


def test_delivered_bytes_hash_mismatch_denies():
    entry = _admitted()
    result = admit_entry(entry, delivered_bytes=b"wrong payload bytes")
    assert not result.admitted
    assert "content_hash_mismatch" in result.denials


# ── Gate 2: attestation_invalid ──────────────────────────────────────────────

def test_empty_signer_denies():
    entry = _admitted()
    entry["attestation"]["signer"] = ""
    result = admit_entry(entry)
    assert not result.admitted
    assert "attestation_invalid" in result.denials


def test_empty_signature_denies():
    entry = _admitted()
    entry["attestation"]["signature"] = ""
    result = admit_entry(entry)
    assert not result.admitted
    assert "attestation_invalid" in result.denials


def test_empty_hash_chain_denies():
    entry = _admitted()
    entry["attestation"]["hashChain"] = []
    result = admit_entry(entry)
    assert not result.admitted
    assert "attestation_invalid" in result.denials


# ── Gate 3: base_version_mismatch ────────────────────────────────────────────

def test_adapter_missing_base_model_id_denies():
    entry = _admitted()
    assert entry["kind"] == "adapter"
    entry["baseBinding"]["baseModelId"] = ""
    result = admit_entry(entry)
    assert not result.admitted
    assert "base_version_mismatch" in result.denials


def test_adapter_missing_base_version_denies():
    entry = _admitted()
    entry["baseBinding"]["baseVersion"] = ""
    result = admit_entry(entry)
    assert not result.admitted
    assert "base_version_mismatch" in result.denials


def test_adapter_invalid_base_content_hash_denies():
    entry = _admitted()
    entry["baseBinding"]["baseContentHash"] = "not-a-hash"
    result = admit_entry(entry)
    assert not result.admitted
    assert "base_version_mismatch" in result.denials


def test_base_kind_skips_base_version_check():
    entry = _admitted()
    entry["kind"] = "base"
    entry["baseBinding"]["baseModelId"] = ""
    result = admit_entry(entry)
    assert "base_version_mismatch" not in result.denials


# ── Gate 4: capability_not_granted ───────────────────────────────────────────

def test_high_privilege_empty_permissions_denies():
    entry = _admitted()
    entry["capability"]["highPrivilege"] = True
    entry["capability"]["requiredPermissions"] = []
    result = admit_entry(entry)
    assert not result.admitted
    assert "capability_not_granted" in result.denials


def test_high_privilege_with_permissions_admits():
    entry = _admitted()
    entry["capability"]["highPrivilege"] = True
    entry["capability"]["requiredPermissions"] = ["fs.read:/scoped"]
    result = admit_entry(entry)
    assert "capability_not_granted" not in result.denials


def test_low_privilege_empty_permissions_does_not_deny():
    entry = _admitted()
    entry["capability"]["highPrivilege"] = False
    entry["capability"]["requiredPermissions"] = []
    result = admit_entry(entry)
    assert "capability_not_granted" not in result.denials


# ── Gate 5: missing_epistemic_label ──────────────────────────────────────────

def test_missing_epistemic_label_denies():
    entry = _admitted()
    del entry["evaluation"]["epistemicLevel"]
    result = admit_entry(entry)
    assert not result.admitted
    assert "missing_epistemic_label" in result.denials


def test_empty_epistemic_label_denies():
    entry = _admitted()
    entry["evaluation"]["epistemicLevel"] = ""
    result = admit_entry(entry)
    assert not result.admitted
    assert "missing_epistemic_label" in result.denials


# ── Gate 6: epistemic_rejected ───────────────────────────────────────────────

def test_epistemic_rejected_fixture_denies():
    result = validate_file(DENIED_EPISTEMIC_PATH)
    assert not result.admitted
    assert "epistemic_rejected" in result.denials


def test_epistemic_rejected_value_denies():
    entry = _admitted()
    entry["evaluation"]["epistemicLevel"] = "rejected"
    result = admit_entry(entry)
    assert not result.admitted
    assert "epistemic_rejected" in result.denials


@pytest.mark.parametrize("level", ["proved", "bounded", "empirical", "synthetic", "speculative"])
def test_valid_epistemic_levels_do_not_deny(level: str):
    entry = _admitted()
    entry["evaluation"]["epistemicLevel"] = level
    result = admit_entry(entry)
    assert "epistemic_rejected" not in result.denials
    assert "missing_epistemic_label" not in result.denials


# ── Gate 7: steering_diff_unsupported ────────────────────────────────────────

def test_steering_diff_unsupported_fixture_denies():
    result = validate_file(DENIED_STEERING_PATH)
    assert not result.admitted
    assert "steering_diff_unsupported" in result.denials


@pytest.mark.parametrize("tier", ["full", "local"])
def test_active_steering_without_diff_denies(tier: str):
    entry = _admitted()
    entry["interpretability"]["steeringTier"] = tier
    entry["interpretability"]["emitsSteeringDiff"] = False
    result = admit_entry(entry)
    assert not result.admitted
    assert "steering_diff_unsupported" in result.denials


@pytest.mark.parametrize("tier", ["full", "local"])
def test_active_steering_with_diff_admits(tier: str):
    entry = _admitted()
    entry["interpretability"]["steeringTier"] = tier
    entry["interpretability"]["emitsSteeringDiff"] = True
    result = admit_entry(entry)
    assert "steering_diff_unsupported" not in result.denials


def test_steering_none_without_diff_does_not_deny():
    entry = _admitted()
    entry["interpretability"]["steeringTier"] = "none"
    entry["interpretability"]["emitsSteeringDiff"] = False
    result = admit_entry(entry)
    assert "steering_diff_unsupported" not in result.denials


# ── Admission result shape ────────────────────────────────────────────────────

def test_admission_result_has_evidence_ref():
    result = validate_file(ADMITTED_PATH)
    assert isinstance(result.evidence_ref, str)
    assert result.entry_id in result.evidence_ref


def test_denial_result_evidence_ref_says_denied():
    entry = _admitted()
    entry["evaluation"]["epistemicLevel"] = "rejected"
    result = admit_entry(entry)
    assert result.evidence_ref is not None
    assert "denied" in result.evidence_ref


def test_multiple_failures_emit_all_denials():
    entry = _admitted()
    entry["evaluation"]["epistemicLevel"] = "rejected"
    entry["interpretability"]["steeringTier"] = "full"
    entry["interpretability"]["emitsSteeringDiff"] = False
    result = admit_entry(entry)
    assert not result.admitted
    assert "epistemic_rejected" in result.denials
    assert "steering_diff_unsupported" in result.denials
