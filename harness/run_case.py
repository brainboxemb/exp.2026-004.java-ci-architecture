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
import xml.etree.ElementTree as ET
import zipfile
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


def tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    files = []
    for path in root.rglob("*"):
        if not path.is_file() or "target" in path.parts:
            continue
        files.append(path)
    for path in sorted(files):
        rel = str(path.relative_to(root)).replace(os.sep, "/")
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(bytes.fromhex(sha256(path)))
        h.update(b"\0")
    return h.hexdigest()


def archive_payload_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with zipfile.ZipFile(path) as archive:
        for info in sorted((item for item in archive.infolist() if not item.is_dir()), key=lambda item: item.filename):
            h.update(info.filename.encode("utf-8"))
            h.update(b"\0")
            h.update(archive.read(info.filename))
            h.update(b"\0")
    return h.hexdigest()


def file_state(path: Path, *, archive_payload: bool = False) -> dict[str, object]:
    stat = path.stat()
    state: dict[str, object] = {"sha256": sha256(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    if archive_payload:
        state["payload_sha256"] = archive_payload_sha256(path)
    return state


def snapshot_glob(root: Path, pattern: str, *, archive_payload: bool = False) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for path in sorted(root.glob(pattern)):
        if path.is_file():
            result[str(path.relative_to(root))] = file_state(path, archive_payload=archive_payload)
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
            "payload_changed": (b or {}).get("payload_sha256") != (a or {}).get("payload_sha256")
            if "payload_sha256" in (b or {}) or "payload_sha256" in (a or {})
            else None,
        })
    return changes


def changed_count(changes: list[dict[str, object]], field: str) -> int:
    return sum(1 for item in changes if bool(item[field]))


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


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if local_name(child.tag) == name:
            return child.text
    return None


def parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.strip().lower() == "true"


def capture_maven_cache_report(work_root: Path, result_dir: Path) -> dict[str, object] | None:
    report_dir = work_root / "target" / "maven-incremental"
    reports = sorted(
        report_dir.glob("cache-report*.xml") if report_dir.is_dir() else [],
        key=lambda path: path.stat().st_mtime_ns,
    )
    if not reports:
        return None

    source = reports[-1]
    retained = result_dir / "maven-build-cache-report.xml"
    shutil.copy2(source, retained)

    root = ET.parse(source).getroot()
    projects: list[dict[str, object]] = []
    for element in root.iter():
        if local_name(element.tag) != "project":
            continue
        projects.append({
            "group_id": child_text(element, "groupId"),
            "artifact_id": child_text(element, "artifactId"),
            "checksum": child_text(element, "checksum"),
            "checksum_matched": parse_bool(child_text(element, "checksumMatched")),
            "lifecycle_matched": parse_bool(child_text(element, "lifecycleMatched")),
            "plugins_matched": parse_bool(child_text(element, "pluginsMatched")),
            "source": child_text(element, "source"),
            "shared_to_remote": parse_bool(child_text(element, "sharedToRemote")),
            "url": child_text(element, "url"),
        })

    return {
        "report_file": retained.name,
        "report_source": str(source.relative_to(work_root)),
        "report_sha256": sha256(retained),
        "projects": projects,
    }


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

    command = [str(v) for v in candidate["command"]]
    prepare_command = [str(v) for v in candidate.get("prepare_command", [])]
    candidate_cwd = work_root / str(candidate.get("working_directory", "."))

    prepare = None
    if prepare_command:
        prepare = execute(prepare_command, candidate_cwd, result_dir / "prepare.log")
        if prepare["exit_code"] != 0:
            raise SystemExit(f"candidate preparation failed; see {result_dir / 'prepare.log'}")

    setup_mode = str(case.get("setup", {}).get("mode", "cold"))
    prime = None
    if setup_mode == "warm":
        prime = execute(command, candidate_cwd, result_dir / "prime.log")
        if prime["exit_code"] != 0:
            raise SystemExit(f"priming invocation failed; see {result_dir / 'prime.log'}")
    elif setup_mode != "cold":
        raise SystemExit(f"unsupported setup mode: {setup_mode}")

    artifacts_before = snapshot_glob(work_root, "*/target/*.jar", archive_payload=True)
    main_classes_before = snapshot_glob(work_root, "*/target/classes/**/*.class")
    test_classes_before = snapshot_glob(work_root, "*/target/test-classes/**/*.class")
    tests_before = snapshot_glob(work_root, "*/target/surefire-reports/TEST-*.xml")
    changed_files = apply_changes(work_root, list(case.get("changes", [])))
    fixture_input_sha256 = tree_digest(work_root)

    measured = execute(command, candidate_cwd, result_dir / "measured.log")
    artifacts_after = snapshot_glob(work_root, "*/target/*.jar", archive_payload=True)
    main_classes_after = snapshot_glob(work_root, "*/target/classes/**/*.class")
    test_classes_after = snapshot_glob(work_root, "*/target/test-classes/**/*.class")
    tests_after = snapshot_glob(work_root, "*/target/surefire-reports/TEST-*.xml")
    native_cache = capture_maven_cache_report(work_root, result_dir)

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

    artifact_changes = compare_snapshots(artifacts_before, artifacts_after)
    main_class_changes = compare_snapshots(main_classes_before, main_classes_after)
    test_class_changes = compare_snapshots(test_classes_before, test_classes_after)
    test_report_changes = compare_snapshots(tests_before, tests_after)

    measured_ms = int(measured["duration_ms"])
    prime_ms = int(prime["duration_ms"]) if prime else None
    saved_vs_prime_ms = (prime_ms - measured_ms) if prime_ms is not None else None
    speedup_vs_prime_x = round(prime_ms / measured_ms, 3) if prime_ms is not None and measured_ms > 0 else None

    workset = {
        "artifact_outputs_content_changed": changed_count(artifact_changes, "content_changed"),
        "artifact_outputs_payload_changed": changed_count(artifact_changes, "payload_changed"),
        "artifact_outputs_mtime_changed": changed_count(artifact_changes, "mtime_changed"),
        "main_classes_content_changed": changed_count(main_class_changes, "content_changed"),
        "main_classes_mtime_changed": changed_count(main_class_changes, "mtime_changed"),
        "test_classes_content_changed": changed_count(test_class_changes, "content_changed"),
        "test_classes_mtime_changed": changed_count(test_class_changes, "mtime_changed"),
        "test_reports_content_changed": changed_count(test_report_changes, "content_changed"),
        "test_reports_mtime_changed": changed_count(test_report_changes, "mtime_changed"),
        "main_classes_observed": len(main_class_changes),
        "test_classes_observed": len(test_class_changes),
        "test_reports_observed": len(test_report_changes),
    }

    passed = all(bool(item["passed"]) for item in assertions)
    candidate_maven = command_output([command[0], "--version"], candidate_cwd)

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
        "changed_files": changed_files,
        "prepare": prepare,
        "prime": prime,
        "build": measured,
        "timing": {
            "prepare_ms": int(prepare["duration_ms"]) if prepare else None,
            "prime_ms": prime_ms,
            "measured_ms": measured_ms,
            "saved_vs_prime_ms": saved_vs_prime_ms,
            "speedup_vs_prime_x": speedup_vs_prime_x,
        },
        "workset": workset,
        "native_cache": native_cache,
        "assertions": assertions,
        "observations": {
            "artifacts": artifact_changes,
            "main_classes": main_class_changes,
            "test_classes": test_class_changes,
            "test_reports": test_report_changes,
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
        f"- Candidate preparation: {int(prepare['duration_ms']) if prepare else '(none)'} ms",
        f"- Prime duration: {prime_ms if prime_ms is not None else '(none)'} ms",
        f"- Measured duration: {measured_ms} ms",
        f"- Saved versus prime: {saved_vs_prime_ms if saved_vs_prime_ms is not None else '(n/a)'} ms",
        f"- Speed-up versus prime: {speedup_vs_prime_x if speedup_vs_prime_x is not None else '(n/a)'}x",
        f"- Changed fixture files: {', '.join(changed_files) if changed_files else '(none)'}",
        f"- Surefire reports: {len(reports)}",
        f"- Fixture input SHA-256: `{fixture_input_sha256}`",
        "",
        "## Workset",
        "",
        f"- JAR archive bytes changed: {workset['artifact_outputs_content_changed']}; payload changed: {workset['artifact_outputs_payload_changed']}; filesystem timestamp changed: {workset['artifact_outputs_mtime_changed']}",
        f"- Main-class content changed: {workset['main_classes_content_changed']} / {workset['main_classes_observed']}; timestamp changed: {workset['main_classes_mtime_changed']}",
        f"- Test-class content changed: {workset['test_classes_content_changed']} / {workset['test_classes_observed']}; timestamp changed: {workset['test_classes_mtime_changed']}",
        f"- Test-report content changed: {workset['test_reports_content_changed']} / {workset['test_reports_observed']}; timestamp changed: {workset['test_reports_mtime_changed']}",
        "",
        "Filesystem timestamp changes are observations only; cache hydration can update timestamps without executing the producing lifecycle.",
        "",
        "## Native cache evidence",
        "",
    ]
    if native_cache:
        summary.append(f"- Retained report: `{native_cache['report_file']}` (`{native_cache['report_sha256']}`)")
        for project in native_cache["projects"]:
            summary.append(
                f"- `{project['artifact_id']}`: source={project['source']}, "
                f"checksum_matched={project['checksum_matched']}, "
                f"lifecycle_matched={project['lifecycle_matched']}, "
                f"plugins_matched={project['plugins_matched']}"
            )
    else:
        summary.append("- No Maven Build Cache native report was produced by this candidate.")

    summary.extend(["", "## Artifact observation", ""])
    if artifact_changes:
        for item in artifact_changes:
            summary.append(f"- `{item['path']}`: content_changed={str(item['content_changed']).lower()}, payload_changed={str(item['payload_changed']).lower()}, mtime_changed={str(item['mtime_changed']).lower()}")
    else:
        summary.append("- No module JAR outputs were observed.")

    summary.extend(["", "## Main-class observation", ""])
    if main_class_changes:
        for item in main_class_changes:
            summary.append(f"- `{item['path']}`: content_changed={str(item['content_changed']).lower()}, mtime_changed={str(item['mtime_changed']).lower()}")
    else:
        summary.append("- No main class outputs were observed before or after the measured invocation.")

    summary.extend(["", "## Test-class observation", ""])
    if test_class_changes:
        for item in test_class_changes:
            summary.append(f"- `{item['path']}`: content_changed={str(item['content_changed']).lower()}, mtime_changed={str(item['mtime_changed']).lower()}")
    else:
        summary.append("- No test class outputs were observed before or after the measured invocation.")

    summary.extend(["", "## Test-report observation", ""])
    if test_report_changes:
        for item in test_report_changes:
            summary.append(f"- `{item['path']}`: content_changed={str(item['content_changed']).lower()}, mtime_changed={str(item['mtime_changed']).lower()}")
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
