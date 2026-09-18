#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
import tomllib

from run_case import (
    SCHEMA,
    SCHEMA_VERSION,
    capture_maven_cache_report,
    command_output,
    execute,
    sha256,
    tree_digest,
)


def parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no", ""}:
        return False
    raise ValueError(f"unsupported boolean value: {value}")


def file_count(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--phase", choices=("producer", "consumer", "miss"), required=True)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--transport-hit")
    parser.add_argument("--results-dir", required=True)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    case_path = (repo / args.case).resolve()
    candidate_dir = repo / "candidates" / args.candidate
    candidate_path = candidate_dir / "candidate.toml"
    case = tomllib.loads(case_path.read_text(encoding="utf-8"))
    candidate = tomllib.loads(candidate_path.read_text(encoding="utf-8"))

    expected_candidate = str(case.get("qualification", {}).get("candidate", ""))
    if expected_candidate and expected_candidate != str(candidate["id"]):
        raise SystemExit(
            f"case {case['id']} requires candidate {expected_candidate}, got {candidate['id']}"
        )

    setup_mode = str(case.get("setup", {}).get("mode", ""))
    expected_mode = {
        "producer": "fresh-cache-reuse",
        "consumer": "fresh-cache-reuse",
        "miss": "fresh-cache-miss",
    }[args.phase]
    if setup_mode != expected_mode:
        raise SystemExit(
            f"phase {args.phase} requires setup mode {expected_mode}, got {setup_mode}"
        )

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

    work_root = repo / ".experiment-work" / str(case["id"]) / f"{candidate['id']}-{args.phase}"
    if work_root.exists():
        shutil.rmtree(work_root)
    shutil.copytree(repo / "fixture", work_root)

    cache_dir = Path(args.cache_dir).resolve()
    if args.phase == "producer":
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True)
    else:
        cache_dir.mkdir(parents=True, exist_ok=True)

    cache_files_before = file_count(cache_dir)
    module_output_files_before = sum(
        1 for path in work_root.glob("*/target/**/*") if path.is_file()
    )

    command = [str(v) for v in candidate["command"]]
    command = command + [f"-Dmaven.build.cache.location={cache_dir}"]
    prepare_command = [str(v) for v in candidate.get("prepare_command", [])]
    candidate_cwd = work_root / str(candidate.get("working_directory", "."))

    prepare = None
    if prepare_command:
        prepare = execute(prepare_command, candidate_cwd, result_dir / "prepare.log")
        if prepare["exit_code"] != 0:
            raise SystemExit(f"candidate preparation failed; see {result_dir / 'prepare.log'}")

    build = execute(command, candidate_cwd, result_dir / "measured.log")
    native_cache = capture_maven_cache_report(work_root, result_dir)
    reports = sorted(work_root.glob("*/target/surefire-reports/TEST-*.xml"))
    cache_files_after = file_count(cache_dir)

    expected = case.get("expect", {})
    assertions: list[dict[str, object]] = []

    assertions.append({
        "name": "fresh-module-output-state",
        "kind": "qualification",
        "passed": module_output_files_before == 0,
        "expected": 0,
        "actual": module_output_files_before,
    })

    expect_tests_pass = bool(expected.get("tests_pass", True))
    assertions.append({
        "name": "build-exit",
        "kind": "correctness",
        "passed": (build["exit_code"] == 0) == expect_tests_pass,
        "exit_code": build["exit_code"],
    })

    for rel in [str(v) for v in expected.get("required_artifacts", [])]:
        ok = (work_root / rel).is_file()
        assertions.append({
            "name": f"artifact:{rel}",
            "kind": "correctness",
            "passed": ok,
        })

    expected_reports = int(expected.get("expected_test_reports", 0))
    if expected_reports:
        assertions.append({
            "name": "test-report-count",
            "kind": "correctness",
            "passed": len(reports) == expected_reports,
            "expected": expected_reports,
            "actual": len(reports),
        })

    actual_sources = {
        str(project.get("artifact_id")): project.get("source")
        for project in (native_cache or {}).get("projects", [])
    }

    if args.phase == "producer":
        for artifact_id in ("core", "feature-a", "feature-b", "app"):
            actual = actual_sources.get(artifact_id)
            assertions.append({
                "name": f"producer-cache-source:{artifact_id}",
                "kind": "qualification",
                "passed": actual == "BUILD",
                "expected": "BUILD",
                "actual": actual,
            })
        assertions.append({
            "name": "producer-cache-populated",
            "kind": "qualification",
            "passed": cache_files_after > 0,
            "expected": ">0",
            "actual": cache_files_after,
        })
    else:
        expected_transport = bool(expected.get("cross_run", {}).get("transport_hit"))
        actual_transport = parse_bool(args.transport_hit)
        assertions.append({
            "name": "cache-transport-hit",
            "kind": "qualification",
            "passed": actual_transport == expected_transport,
            "expected": expected_transport,
            "actual": actual_transport,
        })

        expected_sources = expected.get("candidates", {}).get(
            str(candidate["id"]), {}
        ).get("native_cache_sources", {})
        for artifact_id, expected_source in expected_sources.items():
            actual = actual_sources.get(str(artifact_id))
            assertions.append({
                "name": f"native-cache-source:{artifact_id}",
                "kind": "qualification",
                "passed": actual == expected_source,
                "expected": expected_source,
                "actual": actual,
            })

    passed = all(bool(item["passed"]) for item in assertions)
    fixture_input_sha256 = tree_digest(work_root)

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
        "phase": args.phase,
        "build": build,
        "prepare": prepare,
        "transport": {
            "cache_dir": str(cache_dir),
            "transport_hit": parse_bool(args.transport_hit),
            "cache_files_before": cache_files_before,
            "cache_files_after": cache_files_after,
        },
        "fresh_state": {
            "module_output_files_before": module_output_files_before,
        },
        "native_cache": native_cache,
        "assertions": assertions,
        "test_reports": [str(path.relative_to(work_root)) for path in reports],
        "toolchain": {
            "measured_maven": command_output([command[0], "--version"], candidate_cwd),
        },
        "provenance": {
            "repository_source_revision": checked_out_sha,
            "requested_source_revision": requested_source_revision,
            "github_event_sha": os.environ.get("GITHUB_SHA"),
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
            "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "github_job": os.environ.get("GITHUB_JOB"),
            "runner_name": os.environ.get("RUNNER_NAME"),
            "case_definition_sha256": sha256(case_path),
            "candidate_definition_sha256": sha256(candidate_path),
            "fixture_input_sha256": fixture_input_sha256,
        },
    }
    (result_dir / "result.json").write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = [
        f"# {case['id']} — {case['title']} — {args.phase}",
        "",
        f"- Candidate: `{candidate['id']}`",
        f"- Status: **{result['status']}**",
        f"- Source revision: `{checked_out_sha}`",
        f"- Runner: `{os.environ.get('RUNNER_NAME')}`",
        f"- Fresh module output files before build: {module_output_files_before}",
        f"- Transport hit: {parse_bool(args.transport_hit)}",
        f"- Cache files before/after: {cache_files_before}/{cache_files_after}",
        f"- Measured duration: {build['duration_ms']} ms",
        "",
        "## Native cache evidence",
        "",
    ]
    if native_cache:
        for project in native_cache["projects"]:
            summary.append(
                f"- `{project['artifact_id']}`: source={project['source']}, "
                f"source_raw={project.get('source_raw')}, "
                f"checksum_matched={project['checksum_matched']}"
            )
    else:
        summary.append("- No native Maven Build Cache report was produced.")

    summary.extend(["", "## Assertions", ""])
    for assertion in assertions:
        summary.append(
            f"- {'PASS' if assertion['passed'] else 'FAIL'} — {assertion['name']}"
        )
    (result_dir / "README.md").write_text(
        "\n".join(summary) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "case": case["id"],
        "candidate": candidate["id"],
        "phase": args.phase,
        "status": result["status"],
        "result": str(result_dir / "result.json"),
    }))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
