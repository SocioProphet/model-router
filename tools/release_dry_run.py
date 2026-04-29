#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
VERSION = "0.1.0-dev"
INCLUDED_FILES = [
    "tools/model_router.py",
    "tools/validate_route_examples.py",
    "examples/route-request.example.json",
    "examples/route-policy.example.json",
    "examples/route-decision.example.json",
    "docs/MODEL_ROUTER.md",
    "Makefile",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    DIST.mkdir(exist_ok=True)
    files = []
    for rel in INCLUDED_FILES:
        path = ROOT / rel
        if not path.exists():
            raise FileNotFoundError(rel)
        files.append({"path": rel, "sha256": sha256(path), "bytes": path.stat().st_size})
    manifest = {
        "apiVersion": "release.socioprophet.dev/v1",
        "kind": "ReleaseDryRunManifest",
        "metadata": {
            "name": "model-router",
            "version": VERSION,
            "releaseKind": "dry-run",
            "generatedAt": "1970-01-01T00:00:00Z"
        },
        "spec": {
            "repo": "SocioProphet/model-router",
            "formula": "SocioProphet/homebrew-prophet/Formula/model-router.rb",
            "artifactPolicy": "development-source-bundle-only",
            "stableReleaseReady": False,
            "includedFiles": files,
            "excludedArtifacts": ["model-weights", "datasets", "secrets", "provider-credentials"],
            "promotionRequirements": ["versioned-github-release", "immutable-url", "sha256", "sbom", "provenance", "formula-test"],
        },
    }
    manifest_path = DIST / "model-router.release-dry-run.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksum_path = DIST / "model-router.release-dry-run.sha256"
    checksum_path.write_text(f"{sha256(manifest_path)}  {manifest_path.name}\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "checksum": str(checksum_path)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
