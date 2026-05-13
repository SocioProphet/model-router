#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
REQUIRED_LANES = {"no-model","local-cheap","cheap","standard","high-end","pro"}

def main() -> int:
    paths = sorted((ROOT / "examples").glob("model-price-catalog.*.json"))
    if not paths:
        print("ERR: no model price catalogs found", file=sys.stderr)
        return 2
    for path in paths:
        doc = json.loads(path.read_text(encoding="utf-8"))
        lanes = {lane.get("laneId"): lane for lane in doc.get("lanes", [])}
        missing = REQUIRED_LANES - set(lanes)
        if missing:
            print(f"ERR: {path.relative_to(ROOT)} missing lanes: {sorted(missing)}", file=sys.stderr)
            return 1
        for lane_id, lane in lanes.items():
            profiles = lane.get("profiles", [])
            if not profiles:
                print(f"ERR: {path.relative_to(ROOT)} {lane_id} has no profiles", file=sys.stderr)
                return 1
            for profile in profiles:
                pricing = profile.get("pricing", {})
                for field in ("requestBaseCost", "inputPerMillion", "outputPerMillion", "minCost"):
                    if field not in pricing or float(pricing[field]) < 0:
                        print(f"ERR: {path.relative_to(ROOT)} invalid {lane_id}.{field}", file=sys.stderr)
                        return 1
        print(f"ok: {path.relative_to(ROOT)}")
    print("Model price catalog validation passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
