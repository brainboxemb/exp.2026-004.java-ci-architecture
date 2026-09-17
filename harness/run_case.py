#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
import tomllib

SCHEMA = "brainboxemb.java-ci-experiment-result"
SCHEMA_VERSION = 2


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tree_digest(root: Path, exclude_roots: set[str] | None = None) -> str:
    h = hashlib.sha256()
    files = []
    excluded = exclude_roots or set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if "target" in rel.parts:
            continue
        if rel.parts and rel.parts[0] in excluded:
            continue
        files.append(path)
    for path in sorted(files):
        rel = str(path.relative_to(root)).replace(os.sep, "/")
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(bytes.fromhex(sha256(path)))
        h.update(b"\0")
    return h.hexdigest()


def file_state(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {"sha256": sha256(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def snapshot_glob(root: Path, pattern: str) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for path in sorted(root.glob(pattern)):
        if path.is_file():
            result[str(path.relative_to(root))] = file_state(path)
    return result


def compare_snapshots(before: dict[str, dict[str, object]], after: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    changes = []
    for rel in sorted(set(before) | set(after)):
        b = before.get(rel)
        a = after.get(rel)
        changes.append({
            "path": rel,
            "before": b,
            "after": a,
            "content_changed": (b or {}).get("sha256") != (a or {}).get("sha256"),
            "mtime_changed": (b or {}).get("mtime_ns") != (a or {}).get("mtime_ns"),
        })
    return changes


def command_output(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return completed.stdout.strip()


def execute(command: list[str], cwd: Path, log: Path) -> dict[str, object]:
    start = time.monotonic_ns()
    with log.open("w", encoding="utf-8") as fh:
        completed = subprocess.run(command, cwd=cwd, text=True, stdout=fh, stderr=subprocess.STDOUT, check=False)
    duration_ms = (time.monotonic_ns() - start) // 1_000_000
    return {
        "executed": True,
        "exit_code": completed.returncode,
        "duration_ms": duration_ms,
        "log": log.name,
        "command": command,
    }


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


def apply_overlay(candidate_dir: Path, candidate: dict[str, object], work_root: Path) -> str | None:
    overlay_name = candidate.get("overlay")
    if not overlay_name:
        return None
    overlay = candidate_dir / str(overlay_name)
    if not overlay.is_dir():
        raise RuntimeError(f"candidate overlay does not exist: {overlay}")
    shutil.copytree(overlay, work_root, dirs_exist_ok=True)
    return tree_digest(overlay)


def candidate_command(candidate: dict[str, object], mode: str) -> list[str]:
    commands = candidate.get("commands")
    if isinstance(commands, dict):
        command = commands.get(mode)
    elif mode == "default":
        command = candidate.get("command")
    else:
        command = None
    if not isinstance(command, list) or not command:
        raise RuntimeError(f"candidate {candidate.get('id')} does not provide command mode {mode!r}")
    return [str(value) for value in command]


def change_map(items: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(item["path"]): item for item in items}


def collect_native_evidence(work_root: Path, result_dir: Path, patterns: list[str]) -> list[dict[str, object]]:
    collected: list[dict[str, object]] = []
    destination_root = result_dir / "native-evidence"
    seen: set[str] = set()
    for pattern in patterns:
        for path in sorted(work_root.glob(pattern)):
            if not path.is_file():
                continue
            rel = str(path.relative_to(work_root))
            if rel in seen:
                continue
            seen.add(rel)
            destination = destination_root / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            state = file_state(path)
            collected.append({"path": rel, **state})
    return collected


def add_change_assertions(
    assertions: list[dict[str, object]],
    expected: dict[str, object],
    artifact_changes: list[dict[str, object]],
    test_report_changes: list[dict[str, object]],
) -> None:
    artifact_map = change_map(artifact_changes)
    test_map = change_map(test_report_changes)

    for rel in [str(v) for v in expected.get("must_change_artifact_content", [])]:
        item = artifact_map.get(rel)
        assertions.append({
            "name": f"artifact-content-changed:{rel}",
            "kind": "correctness",
            "passed": bool(item and item.get("content_changed")),
        })

    for rel in [str(v) for v in expected.get("must_not_change_artifact_content", [])]:
        item = artifact_map.get(rel)
        assertions.append({
            "name": f"artifact-content-unchanged:{rel}",
            "kind": "correctness",
            "passed": bool(item is not None and not item.get("content_changed")),
        })

    for rel in [str(v) for v in expected.get("must_rewrite_test_reports", [])]:
        item = test_map.get(rel)
        assertions.append({
            "name": f"test-report-rewritten:{rel}",
            "kind": "correctness",
            "passed": bool(item and item.get("mtime_changed")),
        })

    for rel in [str(v) for v in expected.get("must_not_rewrite_test_reports", [])]:
        item = test_map.get(rel)
        assertions.append({
            "name": f"test-report-not-rewritten:{rel}",
            "kind": "correctness",
            "passed": bool(item is not None and not item.get("mtime_changed")),
        })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--results-dir", required=True)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    case_path = (repo / args.case).resolve()
    candidate_dir = repo / "candidates" / args.candidate
    candidate_path = candidate_dir / "candidate.toml"
    case = tomllib.loads(case_path.read_text(encoding="utf-8"))
    candidate = tomllib.loads(candidate_path.read_text(encoding="utf-8"))

    requested_source_revision = os.environ.get("EXPERIMENT_SOURCE_REVISION")
    checked_out_sha = command_output(["git", "rev-parse", "HEAD"], repo)
    if requested_source_revision and checked_out_sha != requested_source_revision:
        raise SystemExit(
            f"checked-out source {checked_out_sha} does not match requested exact source {requested_source_revision}"
        )

    result_dir = (repo / args.results_dir).resolve()
    if result_dir.exists():
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True)

    work_root = repo / ".experiment-work" / str(case["id"]) / str(candidate["id"])
    if work_root.exists():
        shutil.rmtree(work_root)
    shutil.copytree(repo / "fixture", work_root)
    candidate_overlay_sha256 = apply_overlay(candidate_dir, candidate, work_root)

    candidate_cwd = work_root / str(candidate.get("working_directory", "."))
    default_command = candidate_command(candidate, "default")
    setup = case.get("setup", {})
    setup_mode = str(setup.get("mode", "cold"))
    prime = None
    if setup_mode == "warm":
        prime_mode = str(setup.get("prime_command_mode", "default"))
        prime_command = candidate_command(candidate, prime_mode)
        prime = execute(prime_command, candidate_cwd, result_dir / "prime.log")
        prime["command_mode"] = prime_mode
        if prime["exit_code"] != 0:
            raise SystemExit(f"priming invocation failed; see {result_dir / 'prime.log'}")
    elif setup_mode != "cold":
        raise SystemExit(f"unsupported setup mode: {setup_mode}")

    artifacts_before = snapshot_glob(work_root, "*/target/*.jar")
    tests_before = snapshot_glob(work_root, "*/target/surefire-reports/TEST-*.xml")
    changed_files = apply_changes(work_root, list(case.get("changes", [])))
    input_exclude_roots = {str(v) for v in candidate.get("input_exclude_roots", [])}
    fixture_input_sha256 = tree_digest(work_root, input_exclude_roots)

    execution_mode = str(case.get("execution", {}).get("mode", "default"))
    measured_command = candidate_command(candidate, execution_mode)
    measured = execute(measured_command, candidate_cwd, result_dir / "measured.log")
    measured["command_mode"] = execution_mode
    artifacts_after = snapshot_glob(work_root, "*/target/*.jar")
    tests_after = snapshot_glob(work_root, "*/target/surefire-reports/TEST-*.xml")

    assertions: list[dict[str, object]] = []
    expected = case.get("expect", {})
    required_artifacts = [str(v) for v in expected.get("required_artifacts", [])]
    for rel in required_artifacts:
        ok = (work_root / rel).is_file()
        assertions.append({"name": f"artifact:{rel}", "kind": "correctness", "passed": ok})

    reports = sorted(work_root.glob("*/target/surefire-reports/TEST-*.xml"))
    expected_reports = int(expected.get("expected_test_reports", 0))
    if expected_reports:
        assertions.append({
            "name": "test-report-count",
            "kind": "correctness",
            "passed": len(reports) == expected_reports,
            "expected": expected_reports,
            "actual": len(reports),
        })

    expect_tests_pass = bool(expected.get("tests_pass", True))
    assertions.append({
        "name": "build-exit",
        "kind": "correctness",
        "passed": (measured["exit_code"] == 0) == expect_tests_pass,
        "exit_code": measured["exit_code"],
    })

    artifact_changes = compare_snapshots(artifacts_before, artifacts_after)
    test_report_changes = compare_snapshots(tests_before, tests_after)
    add_change_assertions(assertions, expected, artifact_changes, test_report_changes)

    native_evidence = collect_native_evidence(
        work_root,
        result_dir,
        [str(v) for v in candidate.get("evidence_globs", [])],
    )
    if bool(candidate.get("capabilities", {}).get("native_structured_evidence", False)):
        assertions.append({
            "name": "native-structured-evidence",
            "kind": "evidence",
            "passed": bool(native_evidence),
            "count": len(native_evidence),
        })

    passed = all(bool(item["passed"]) for item in assertions)
    candidate_maven = command_output([default_command[0], "--version"], candidate_cwd)

    result = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "case": case["id"],
        "case_title": case["title"],
        "question": case["question"],
        "candidate": candidate["id"],
        "candidate_title": candidate["title"],
        "candidate_capabilities": candidate.get("capabilities", {}),
        "status": "pass" if passed else "fail",
        "setup_mode": setup_mode,
        "execution_mode": execution_mode,
        "changed_files": changed_files,
        "prime": prime,
        "build": measured,
        "assertions": assertions,
        "observations": {
            "artifacts": artifact_changes,
            "test_reports": test_report_changes,
            "native_evidence": native_evidence,
        },
        "test_reports": [str(p.relative_to(work_root)) for p in reports],
        "toolchain": {
            "java": command_output(["java", "-version"], candidate_cwd),
            "candidate_maven": candidate_maven,
        },
        "provenance": {
            "repository_source_revision": checked_out_sha,
            "requested_source_revision": requested_source_revision,
            "github_event_sha": os.environ.get("GITHUB_SHA"),
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
            "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "case_definition_sha256": sha256(case_path),
            "candidate_definition_sha256": sha256(candidate_path),
            "candidate_overlay_sha256": candidate_overlay_sha256,
            "fixture_input_sha256": fixture_input_sha256,
        },
    }
    (result_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    summary = [
        f"# {case['id']} — {case['title']}",
        "",
        f"- Candidate: `{candidate['id']}`",
        f"- Status: **{result['status']}**",
        f"- Source revision: `{checked_out_sha}`",
        f"- Setup: `{setup_mode}`",
        f"- Execution mode: `{execution_mode}`",
        f"- Measured duration: {measured['duration_ms']} ms",
        f"- Changed fixture files: {', '.join(changed_files) if changed_files else '(none)'}",
        f"- Surefire reports: {len(reports)}",
        f"- Native evidence files: {len(native_evidence)}",
        f"- Fixture input SHA-256: `{fixture_input_sha256}`",
        "",
        "## Artifact observation",
        "",
    ]
    if artifact_changes:
        for item in artifact_changes:
            summary.append(
                f"- `{item['path']}`: content_changed={str(item['content_changed']).lower()}, "
                f"mtime_changed={str(item['mtime_changed']).lower()}"
            )
    else:
        summary.append("- No module JAR outputs were observed.")
    summary.extend(["", "## Test-report observation", ""])
    if test_report_changes:
        for item in test_report_changes:
            summary.append(
                f"- `{item['path']}`: content_changed={str(item['content_changed']).lower()}, "
                f"mtime_changed={str(item['mtime_changed']).lower()}"
            )
    else:
        summary.append("- No Surefire reports were observed before or after the measured invocation.")
    summary.extend(["", "## Assertions", ""])
    for assertion in assertions:
        summary.append(f"- {'PASS' if assertion['passed'] else 'FAIL'} — {assertion['name']}")
    (result_dir / "README.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    print(json.dumps({"case": case["id"], "candidate": candidate["id"], "status": result["status"], "result": str(result_dir / "result.json")}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
