#!/usr/bin/env python3
"""
SourceOS model/adapter catalog entry admission validator.

Implements the AdmitEntry contract from contracts/sourceos/model-catalog-entry.v0.1.ts.
Every check is a hard gate — a single failure denies. No silent admission or silent denial.
The admission result is always emitted as a provenance record regardless of outcome.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "model-catalog-entry.v0.1.schema.json"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Denial reasons match AdmissionDenialReason in the TypeScript contract.
CONTENT_HASH_MISMATCH = "content_hash_mismatch"
ATTESTATION_INVALID = "attestation_invalid"
BASE_VERSION_MISMATCH = "base_version_mismatch"
CAPABILITY_NOT_GRANTED = "capability_not_granted"
MISSING_EPISTEMIC_LABEL = "missing_epistemic_label"
EPISTEMIC_REJECTED = "epistemic_rejected"
STEERING_DIFF_UNSUPPORTED = "steering_diff_unsupported"
EGRESS_TARGET_NOT_PERMITTED = "egress_target_not_permitted"
OBSERVABILITY_SINK_UNINITIALIZED = "observability_sink_uninitialized"
CLUSTER_NOT_ADMITTED = "cluster_not_admitted"

INADMISSIBLE_EPISTEMIC = {"rejected"}
REQUIRES_DIFF = {"full", "local"}


@dataclass
class AdmissionResult:
    admitted: bool
    entry_id: str
    denials: list[str] = field(default_factory=list)
    evidence_ref: str | None = None
    cluster_admission_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "admitted": self.admitted,
            "entryId": self.entry_id,
            "denials": self.denials,
            "evidenceRef": self.evidence_ref,
        }
        if self.cluster_admission_ref:
            result["clusterAdmissionRef"] = self.cluster_admission_ref
        return result


def _is_valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.match(value))


def admit_entry(
    entry: dict[str, Any],
    *,
    delivered_bytes: bytes | None = None,
) -> AdmissionResult:
    """
    Admit or deny a catalog entry. All checks are hard gates.

    delivered_bytes: if provided, the artifact content hash is verified against
    the delivered payload. Omit for static/structural admission (e.g. CI validation).
    The structural checks always run; hash verification runs only when bytes are present.
    """
    entry_id = entry.get("id", "<unknown>")
    denials: list[str] = []

    # ── Gate 1: content_hash_mismatch ──────────────────────────────────────
    # Structural: contentHash must be a valid 64-char lowercase hex sha256.
    # Runtime: when delivered_bytes are present, verify hash against payload.
    artifact = entry.get("artifact", {})
    content_hash = artifact.get("contentHash", "")
    if not _is_valid_sha256(content_hash):
        denials.append(CONTENT_HASH_MISMATCH)
    elif delivered_bytes is not None:
        actual = hashlib.sha256(delivered_bytes).hexdigest()
        if actual != content_hash:
            denials.append(CONTENT_HASH_MISMATCH)

    # Encryption is an invariant, not a flag.
    if artifact.get("encrypted") is not True:
        denials.append(CONTENT_HASH_MISMATCH)  # artifact integrity failure

    # ── Gate 2: attestation_invalid ────────────────────────────────────────
    # Signer identity, signature, and hash-chain must all be present and non-empty.
    attestation = entry.get("attestation", {})
    attest_failures = False
    if not isinstance(attestation.get("signer"), str) or not attestation["signer"].strip():
        attest_failures = True
    if not isinstance(attestation.get("signature"), str) or not attestation["signature"].strip():
        attest_failures = True
    hash_chain = attestation.get("hashChain", [])
    if not isinstance(hash_chain, list) or len(hash_chain) < 1:
        attest_failures = True
    if attest_failures:
        denials.append(ATTESTATION_INVALID)

    # ── Gate 3: base_version_mismatch ──────────────────────────────────────
    # Adapters, steering, and guardrail artifacts must declare a fully-specified
    # base binding (non-empty baseModelId + baseVersion + valid baseContentHash).
    # Base artifacts are self-binding; their baseModelId may be empty.
    kind = entry.get("kind", "")
    base_binding = entry.get("baseBinding", {})
    if kind != "base":
        if not isinstance(base_binding.get("baseModelId"), str) or not base_binding["baseModelId"].strip():
            denials.append(BASE_VERSION_MISMATCH)
        elif not isinstance(base_binding.get("baseVersion"), str) or not base_binding["baseVersion"].strip():
            denials.append(BASE_VERSION_MISMATCH)
        elif not _is_valid_sha256(base_binding.get("baseContentHash", "")):
            denials.append(BASE_VERSION_MISMATCH)

    # ── Gate 4: capability_not_granted ─────────────────────────────────────
    # highPrivilege entries require at least one explicit requiredPermission declared.
    capability = entry.get("capability", {})
    if capability.get("highPrivilege") is True:
        perms = capability.get("requiredPermissions", [])
        if not isinstance(perms, list) or len(perms) == 0:
            denials.append(CAPABILITY_NOT_GRANTED)

    # ── Gate 5: missing_epistemic_label ────────────────────────────────────
    evaluation = entry.get("evaluation", {})
    epistemic = evaluation.get("epistemicLevel")
    if not isinstance(epistemic, str) or not epistemic.strip():
        denials.append(MISSING_EPISTEMIC_LABEL)

    # ── Gate 6: epistemic_rejected ─────────────────────────────────────────
    # Rejected entries are retained for audit but are never loadable.
    elif epistemic in INADMISSIBLE_EPISTEMIC:
        denials.append(EPISTEMIC_REJECTED)

    # ── Gate 7: steering_diff_unsupported ──────────────────────────────────
    # When steeringTier is "full" or "local", the entry MUST declare it can emit
    # a steered-vs-baseline diff.
    interp = entry.get("interpretability", {})
    tier = interp.get("steeringTier", "none")
    if tier in REQUIRES_DIFF and interp.get("emitsSteeringDiff") is not True:
        denials.append(STEERING_DIFF_UNSUPPORTED)

    # ── Gate 8: egress_target_not_permitted ────────────────────────────────
    # If permitsEgress is true, every declared target must have a non-empty
    # permittedPhases list. A target with no phases declared is undeclared egress.
    egress = entry.get("egress", {})
    if egress.get("permitsEgress") is True:
        for target in egress.get("targets", []):
            phases = target.get("permittedPhases", [])
            if not isinstance(phases, list) or len(phases) == 0:
                denials.append(EGRESS_TARGET_NOT_PERMITTED)
                break

    # ── Gate 9: observability_sink_uninitialized ───────────────────────────
    # sinkInitializesBeforeIO must be the literal true. Any other value means
    # model IO is reachable before the provenance sink is up.
    observability = entry.get("observability", {})
    if observability.get("sinkInitializesBeforeIO") is not True:
        denials.append(OBSERVABILITY_SINK_UNINITIALIZED)

    # ── Gate 10: cluster_not_admitted ──────────────────────────────────────
    # clusterAdmissionRef explicitly set to "" means the operator declared a cluster
    # binding but provided no pack reference. Omitting the field entirely is allowed
    # (synthetic/pre-cluster entries). An empty string is a declared-but-empty ref.
    cluster_ref = entry.get("clusterAdmissionRef")
    if isinstance(cluster_ref, str) and cluster_ref.strip() == "":
        denials.append(CLUSTER_NOT_ADMITTED)

    admitted = len(denials) == 0
    evidence_ref = (
        f"model-router:admission:{entry_id}:{'admitted' if admitted else 'denied'}"
    )
    return AdmissionResult(
        admitted=admitted,
        entry_id=entry_id,
        denials=denials,
        evidence_ref=evidence_ref,
        cluster_admission_ref=cluster_ref if admitted and cluster_ref else None,
    )


def validate_file(path: Path, *, delivered_bytes: bytes | None = None) -> AdmissionResult:
    entry = json.loads(path.read_text(encoding="utf-8"))
    # Strip _comment keys (used in denial fixtures) before processing.
    entry = {k: v for k, v in entry.items() if not k.startswith("_")}
    return admit_entry(entry, delivered_bytes=delivered_bytes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Admit or deny a model catalog entry")
    parser.add_argument("entry", type=Path, help="Path to the JSON entry file")
    parser.add_argument(
        "--artifact", type=Path, default=None,
        help="Path to the raw artifact bytes for content-hash verification (optional)"
    )
    parser.add_argument("--expect-denied", action="store_true", help="Exit 0 only if denied")
    args = parser.parse_args()

    delivered_bytes: bytes | None = None
    if args.artifact:
        delivered_bytes = args.artifact.read_bytes()

    result = validate_file(args.entry, delivered_bytes=delivered_bytes)
    print(json.dumps(result.to_dict(), indent=2))

    if args.expect_denied:
        return 0 if not result.admitted else 1
    return 0 if result.admitted else 1


if __name__ == "__main__":
    sys.exit(main())
