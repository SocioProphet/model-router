#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"localModelProfileAvailable","localServiceHealthy","memoryAvailableBytes","providerQuotaKnown","providerQuotaRemainingShare","providerErrorRate","providerLatencyP95Ms","estimatedInputTokens","estimatedOutputTokens"}

def main() -> int:
    paths = sorted((ROOT / "examples").glob("agent-execution-budget-resource-optimizer.*.json"))
    if not paths:
        print("ERR: no optimizer examples found", file=sys.stderr)
        return 2
    for path in paths:
        doc = json.loads(path.read_text(encoding="utf-8"))
        signals = set(doc.get("resourcePolicy", {}).get("requiredSignals", []))
        missing = REQUIRED - signals
        if missing:
            print(f"ERR: {path.relative_to(ROOT)} missing signals: {sorted(missing)}", file=sys.stderr)
            return 1
        if doc.get("budgetPolicy", {}).get("premiumReserveShare", 0) < 0.2:
            print(f"ERR: {path.relative_to(ROOT)} premium reserve too low", file=sys.stderr)
            return 1
        print(f"ok: {path.relative_to(ROOT)}")
    print("Agent execution budget/resource optimizer validation passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
