#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
import tomllib

SCHEMA = "brainboxemb.java-ci-experiment-result"
SCHEMA_VERSION = 1


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def snapshot_outputs(root: Path) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for path in sorted(root.glob("*/target/*.jar")):
        stat = path.stat()
        result[str(path.relative_to(root))] = {
            "sha256": sha256(path),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    return result


def command_output(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return completed.stdout.strip()


def execute(command: list[str], cwd: Path, log: Path) -> dict[str, object]:
    start = time.monotonic_ns()
    with log.open("w", encoding="utf-8") as fh:
        completed = subprocess.run(command, cwd=cwd, text=True, stdout=fh, stderr=subprocess.STDOUT, check=False)
    duration_ms = (time.monotonic_ns() - start) // 1_000_000
    return {"executed": True, "exit_code": completed.returncode, "duration_ms": duration_ms, "log": log.name}


def apply_changes(root: Path, changes: list[dict[str, object]]) -> list[str]:
    changed: list[str] = []
    for change in changes:
        rel = str(change["path"])
        path = root / rel
        if not path.is_file():
            raise RuntimeError(f"change target does not exist: {rel}")
        operation = str(change["operation"])
        text = path.read_text(encoding="utf-8")
        if operation == "append":
            text += str(change["text"])
        elif operation == "replace":
            find = str(change["find"])
            replacement = str(change["replace"])
            count = text.count(find)
            if count != 1:
                raise RuntimeError(f"replace in {rel} expected exactly one match, found {count}")
            text = text.replace(find, replacement, 1)
        else:
            raise RuntimeError(f"unsupported change operation: {operation}")
        path.write_text(text, encoding="utf-8")
        changed.append(rel)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--results-dir", required=True)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    case_path = (repo / args.case).resolve()
    candidate_path = repo / "candidates" / args.candidate / "candidate.toml"
    case = tomllib.loads(case_path.read_text(encoding="utf-8"))
    candidate = tomllib.loads(candidate_path.read_text(encoding="utf-8"))

    result_dir = (repo / args.results_dir).resolve()
    if result_dir.exists():
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True)

    work_root = repo / ".experiment-work" / str(case["id"]) / str(candidate["id"])
    if work_root.exists():
        shutil.rmtree(work_root)
    shutil.copytree(repo / "fixture", work_root)

    command = [str(v) for v in candidate["command"]]
    setup_mode = str(case.get("setup", {}).get("mode", "cold"))
    prime = None
    if setup_mode == "warm":
        prime = execute(command, work_root / str(candidate.get("working_directory", ".")), result_dir / "prime.log")
        if prime["exit_code"] != 0:
            raise SystemExit(f"priming invocation failed; see {result_dir / 'prime.log'}")
    elif setup_mode != "cold":
        raise SystemExit(f"unsupported setup mode: {setup_mode}")

    before = snapshot_outputs(work_root)
    changed_files = apply_changes(work_root, list(case.get("changes", [])))
    measured = execute(command, work_root / str(candidate.get("working_directory", ".")), result_dir / "measured.log")
    after = snapshot_outputs(work_root)

    assertions: list[dict[str, object]] = []
    expected = case.get("expect", {})
    required_artifacts = [str(v) for v in expected.get("required_artifacts", [])]
    for rel in required_artifacts:
        ok = (work_root / rel).is_file()
        assertions.append({"name": f"artifact:{rel}", "kind": "correctness", "passed": ok})

    reports = sorted(work_root.glob("*/target/surefire-reports/TEST-*.xml"))
    expected_reports = int(expected.get("expected_test_reports", 0))
    if expected_reports:
        assertions.append({"name": "test-report-count", "kind": "correctness", "passed": len(reports) == expected_reports, "expected": expected_reports, "actual": len(reports)})

    expect_tests_pass = bool(expected.get("tests_pass", True))
    assertions.append({"name": "build-exit", "kind": "correctness", "passed": (measured["exit_code"] == 0) == expect_tests_pass, "exit_code": measured["exit_code"]})

    output_changes = []
    for rel in sorted(set(before) | set(after)):
        b = before.get(rel)
        a = after.get(rel)
        output_changes.append({
            "path": rel,
            "before": b,
            "after": a,
            "content_changed": (b or {}).get("sha256") != (a or {}).get("sha256"),
            "mtime_changed": (b or {}).get("mtime_ns") != (a or {}).get("mtime_ns"),
        })

    passed = all(bool(item["passed"]) for item in assertions)
    result = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "case": case["id"],
        "case_title": case["title"],
        "question": case["question"],
        "candidate": candidate["id"],
        "candidate_title": candidate["title"],
        "status": "pass" if passed else "fail",
        "setup_mode": setup_mode,
        "changed_files": changed_files,
        "prime": prime,
        "build": measured,
        "assertions": assertions,
        "outputs": output_changes,
        "test_reports": [str(p.relative_to(work_root)) for p in reports],
        "toolchain": {
            "java": command_output(["java", "-version"], work_root),
            "maven": command_output(["mvn", "--version"], work_root),
        },
    }
    (result_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    summary = [
        f"# {case['id']} — {case['title']}",
        "",
        f"- Candidate: `{candidate['id']}`",
        f"- Status: **{result['status']}**",
        f"- Setup: `{setup_mode}`",
        f"- Measured duration: {measured['duration_ms']} ms",
        f"- Changed fixture files: {', '.join(changed_files) if changed_files else '(none)'}",
        f"- Surefire reports: {len(reports)}",
        "",
        "## Output observation",
        "",
    ]
    if output_changes:
        for item in output_changes:
            summary.append(f"- `{item['path']}`: content_changed={str(item['content_changed']).lower()}, mtime_changed={str(item['mtime_changed']).lower()}")
    else:
        summary.append("- No module JAR outputs were observed.")
    summary.extend(["", "## Assertions", ""])
    for assertion in assertions:
        summary.append(f"- {'PASS' if assertion['passed'] else 'FAIL'} — {assertion['name']}")
    (result_dir / "README.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    print(json.dumps({"case": case["id"], "candidate": candidate["id"], "status": result["status"], "result": str(result_dir / "result.json")}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
