#!/usr/bin/env python3
import json
import os
from pathlib import Path
import tomllib

root = Path(__file__).resolve().parents[1]
case_paths = sorted((root / "tests" / "cases").glob("*.toml"))
candidates = sorted(
    p.name for p in (root / "candidates").iterdir()
    if (p / "candidate.toml").is_file()
)

if not case_paths:
    raise SystemExit("no testcases found")
if not candidates:
    raise SystemExit("no candidates found")

local_cases = []
fresh_reuse_cases = []
fresh_miss_cases = []

for path in case_paths:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    rel = str(path.relative_to(root))
    mode = str(data.get("setup", {}).get("mode", "cold"))
    if mode in {"cold", "warm"}:
        local_cases.append(rel)
    elif mode == "fresh-cache-reuse":
        fresh_reuse_cases.append(rel)
    elif mode == "fresh-cache-miss":
        fresh_miss_cases.append(rel)
    else:
        raise SystemExit(f"unsupported testcase setup mode in {rel}: {mode}")

payloads = {
    "cases": json.dumps(local_cases, separators=(",", ":")),
    "fresh_reuse_cases": json.dumps(fresh_reuse_cases, separators=(",", ":")),
    "fresh_miss_cases": json.dumps(fresh_miss_cases, separators=(",", ":")),
    "candidates": json.dumps(candidates, separators=(",", ":")),
}
output = os.environ.get("GITHUB_OUTPUT")
if output:
    with open(output, "a", encoding="utf-8") as fh:
        for key, value in payloads.items():
            fh.write(f"{key}={value}\n")
else:
    print(json.dumps({
        "cases": local_cases,
        "fresh_reuse_cases": fresh_reuse_cases,
        "fresh_miss_cases": fresh_miss_cases,
        "candidates": candidates,
    }, indent=2))
