#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
import tomllib

from run_case import capture_maven_cache_report, command_output, execute, sha256


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


def byte_count(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def target_file_count(root: Path) -> int:
    return sum(1 for path in root.glob("*/target/**/*") if path.is_file())


def parse_maven_total(log_path: Path) -> str | None:
    if not log_path.is_file():
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(r"\[INFO\]\s+Total time:\s+(.+)", text)
    return matches[-1].strip() if matches else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", required=True)
    parser.add_argument("--workload-dir", required=True)
    parser.add_argument("--mode", choices=("control", "shared"), required=True)
    parser.add_argument("--phase", choices=("producer", "consumer"), required=True)
    parser.add_argument("--sample", type=int, required=True)
    parser.add_argument("--cache-dir")
    parser.add_argument("--transport-hit")
    parser.add_argument("--producer-run-id")
    parser.add_argument("--producer-source-revision")
    parser.add_argument("--results-dir", required=True)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    workload_path = (repo / args.workload).resolve()
    workload = tomllib.loads(workload_path.read_text(encoding="utf-8"))
    work = Path(args.workload_dir).resolve()

    if not work.is_dir():
        raise SystemExit(f"workload directory does not exist: {work}")

    expected_revision = str(workload["revision"])
    checked_out_sha = command_output(["git", "rev-parse", "HEAD"], work)
    if checked_out_sha != expected_revision:
        raise SystemExit(
            f"workload checkout {checked_out_sha} does not match declared revision {expected_revision}"
        )

    result_dir = (repo / args.results_dir).resolve()
    if result_dir.exists():
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True)

    before_outputs = target_file_count(work)
    cache_dir = Path(args.cache_dir).resolve() if args.cache_dir else None
    cache_files_before = file_count(cache_dir) if cache_dir else None
    cache_bytes_before = byte_count(cache_dir) if cache_dir else None

    if args.mode == "shared" and cache_dir is None:
        raise SystemExit("shared mode requires --cache-dir")
    if args.mode == "shared" and args.phase == "consumer":
        if not args.producer_run_id or not args.producer_source_revision:
            raise SystemExit("shared consumer requires producer run/source provenance")

    wrapper = execute(["./mvnw", "--version"], work, result_dir / "wrapper.log")
    if wrapper["exit_code"] != 0:
        raise SystemExit("Maven Wrapper check failed")

    prepare = None
    cache_env: dict[str, str] = {}
    if args.mode == "shared":
        assert cache_dir is not None
        if args.phase == "producer":
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
            cache_dir.mkdir(parents=True)
        else:
            cache_dir.mkdir(parents=True, exist_ok=True)

        cache_env["MAVEN_BUILD_CACHE_BASE"] = str(cache_dir)
        prepare_script = repo / "candidates" / "maven-build-cache" / "prepare.sh"
        prepare = execute(
            ["bash", str(prepare_script)],
            work,
            result_dir / "prepare.log",
            cache_env,
        )
        if prepare["exit_code"] != 0:
            raise SystemExit("Maven Build Cache preparation failed")
        command = [
            "bash",
            str(repo / "candidates" / "maven-build-cache" / "run.sh"),
            "verify",
        ]
    else:
        command = ["./mvnw", "--batch-mode", "--no-transfer-progress", "verify"]

    build = execute(command, work, result_dir / "measured.log", cache_env or None)
    native_cache = (
        capture_maven_cache_report(work, result_dir)
        if args.mode == "shared"
        else None
    )
    reports = sorted(work.glob("*/target/surefire-reports/TEST-*.xml"))
    cache_files_after = file_count(cache_dir) if cache_dir else None
    cache_bytes_after = byte_count(cache_dir) if cache_dir else None

    assertions: list[dict[str, object]] = []
    assertions.append({
        "name": "fresh-module-output-state",
        "kind": "correctness",
        "passed": before_outputs == 0,
        "expected": 0,
        "actual": before_outputs,
    })
    assertions.append({
        "name": "build-exit",
        "kind": "correctness",
        "passed": build["exit_code"] == 0,
        "exit_code": build["exit_code"],
    })

    for rel in [str(v) for v in workload.get("required_artifacts", [])]:
        assertions.append({
            "name": f"artifact:{rel}",
            "kind": "correctness",
            "passed": (work / rel).is_file(),
        })

    expected_reports = int(workload.get("expected_test_reports", 0))
    assertions.append({
        "name": "test-report-count",
        "kind": "correctness",
        "passed": len(reports) == expected_reports,
        "expected": expected_reports,
        "actual": len(reports),
    })

    if args.mode == "shared":
        actual_sources = {
            str(project.get("artifact_id")): project.get("source")
            for project in (native_cache or {}).get("projects", [])
        }
        expected_source = "BUILD" if args.phase == "producer" else "LOCAL"
        for artifact_id in ("event-timing-framework", "event-timing-app"):
            actual = actual_sources.get(artifact_id)
            assertions.append({
                "name": f"native-cache-source:{artifact_id}",
                "kind": "qualification",
                "passed": actual == expected_source,
                "expected": expected_source,
                "actual": actual,
            })

        if args.phase == "producer":
            assertions.append({
                "name": "producer-cache-populated",
                "kind": "qualification",
                "passed": bool(cache_files_after and cache_files_after > 0),
                "expected": ">0",
                "actual": cache_files_after,
            })
        else:
            actual_transport = parse_bool(args.transport_hit)
            assertions.append({
                "name": "cache-transport-hit",
                "kind": "qualification",
                "passed": actual_transport is True,
                "expected": True,
                "actual": actual_transport,
            })
            current_run_id = os.environ.get("GITHUB_RUN_ID")
            assertions.append({
                "name": "separate-workflow-run",
                "kind": "qualification",
                "passed": bool(current_run_id) and current_run_id != args.producer_run_id,
                "producer_run_id": args.producer_run_id,
                "consumer_run_id": current_run_id,
            })
            assertions.append({
                "name": "producer-consumer-source-match",
                "kind": "qualification",
                "passed": args.producer_source_revision == os.environ.get("EXPERIMENT_SOURCE_REVISION"),
                "producer_source_revision": args.producer_source_revision,
                "consumer_source_revision": os.environ.get("EXPERIMENT_SOURCE_REVISION"),
            })

    passed = all(bool(item["passed"]) for item in assertions)
    prepare_ms = int(prepare["duration_ms"]) if prepare else 0
    wrapper_ms = int(wrapper["duration_ms"])
    build_ms = int(build["duration_ms"])

    result = {
        "schema": "brainboxemb.java-ci-production-value-result",
        "schema_version": 2,
        "workload": workload["id"],
        "workload_title": workload["title"],
        "workload_repository": workload["repository"],
        "workload_revision": expected_revision,
        "mode": args.mode,
        "phase": args.phase,
        "sample": args.sample,
        "status": "pass" if passed else "fail",
        "timing": {
            "wrapper_ms": wrapper_ms,
            "candidate_prepare_ms": prepare_ms,
            "measured_maven_ms": build_ms,
            "measured_path_ms": wrapper_ms + prepare_ms + build_ms,
            "maven_reported_total": parse_maven_total(result_dir / "measured.log"),
        },
        "fresh_state": {
            "module_output_files_before": before_outputs,
        },
        "transport": {
            "cache_dir": str(cache_dir) if cache_dir else None,
            "transport_hit": parse_bool(args.transport_hit),
            "cache_files_before": cache_files_before,
            "cache_files_after": cache_files_after,
            "cache_bytes_before": cache_bytes_before,
            "cache_bytes_after": cache_bytes_after,
            "producer_workflow_run_id": args.producer_run_id,
            "consumer_workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
        "native_cache": native_cache,
        "assertions": assertions,
        "test_reports": [str(path.relative_to(work)) for path in reports],
        "production_baseline": workload.get("production_baseline", {}),
        "provenance": {
            "experiment_source_revision": os.environ.get("EXPERIMENT_SOURCE_REVISION"),
            "workload_source_revision": checked_out_sha,
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "github_job": os.environ.get("GITHUB_JOB"),
            "runner_name": os.environ.get("RUNNER_NAME"),
            "runner_os": os.environ.get("RUNNER_OS"),
            "workload_definition_sha256": sha256(workload_path),
        },
    }
    (result_dir / "result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )

    summary = [
        f"# Production value — {workload['title']}",
        "",
        f"- Mode/phase/sample: `{args.mode}` / `{args.phase}` / `{args.sample}`",
        f"- Status: **{result['status']}**",
        f"- Workload source: `{checked_out_sha}`",
        f"- Wrapper check: {wrapper_ms} ms",
        f"- Candidate preparation: {prepare_ms} ms",
        f"- Measured Maven: {build_ms} ms",
        f"- Measured path: {wrapper_ms + prepare_ms + build_ms} ms",
        f"- Maven reported total: {result['timing']['maven_reported_total']}",
        f"- Fresh module output files before build: {before_outputs}",
        f"- Cache files before/after: {cache_files_before}/{cache_files_after}",
        f"- Cache bytes before/after: {cache_bytes_before}/{cache_bytes_after}",
        "",
        "## Assertions",
        "",
    ]
    for assertion in assertions:
        summary.append(
            f"- {'PASS' if assertion['passed'] else 'FAIL'} — {assertion['name']}"
        )
    (result_dir / "README.md").write_text(
        "\n".join(summary) + "\n", encoding="utf-8"
    )

    print(json.dumps({
        "workload": workload["id"],
        "mode": args.mode,
        "phase": args.phase,
        "sample": args.sample,
        "status": result["status"],
        "result": str(result_dir / "result.json"),
    }))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
