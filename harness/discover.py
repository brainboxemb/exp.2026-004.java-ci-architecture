#!/usr/bin/env python3
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cases = sorted(str(p.relative_to(root)) for p in (root / "tests" / "cases").glob("*.toml"))
candidates = sorted(p.name for p in (root / "candidates").iterdir() if (p / "candidate.toml").is_file())

if not cases:
    raise SystemExit("no testcases found")
if not candidates:
    raise SystemExit("no candidates found")

payloads = {"cases": json.dumps(cases, separators=(",", ":")), "candidates": json.dumps(candidates, separators=(",", ":"))}
output = os.environ.get("GITHUB_OUTPUT")
if output:
    with open(output, "a", encoding="utf-8") as fh:
        for key, value in payloads.items():
            fh.write(f"{key}={value}\n")
else:
    print(json.dumps({"cases": cases, "candidates": candidates}, indent=2))
