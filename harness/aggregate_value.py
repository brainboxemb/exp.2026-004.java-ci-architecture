#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import statistics
import sys


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def job_seconds(job: dict[str, object]) -> float:
    started = job.get("started_at")
    completed = job.get("completed_at")
    if not isinstance(started, str) or not isinstance(completed, str):
        raise ValueError(f"job is not complete: {job.get('name')}")
    return (parse_time(completed) - parse_time(started)).total_seconds()


def step_seconds(job: dict[str, object], step_name: str) -> float:
    for step in job.get("steps", []):
        if step.get("name") != step_name:
            continue
        started = step.get("started_at")
        completed = step.get("completed_at")
        if not isinstance(started, str) or not isinstance(completed, str):
            raise ValueError(f"step is not complete: {step_name}")
        return (parse_time(completed) - parse_time(started)).total_seconds()
    raise KeyError(f"missing step {step_name} in {job.get('name')}")


def stats(values: list[float]) -> dict[str, float]:
    return {
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def load_results(root: Path) -> dict[tuple[str, str, int], dict[str, object]]:
    found: dict[tuple[str, str, int], dict[str, object]] = {}
    for path in root.rglob("result.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != "brainboxemb.java-ci-production-value-result":
            continue
        key = (str(data["mode"]), str(data["phase"]), int(data["sample"]))
        if key in found:
            raise ValueError(f"duplicate result for {key}: {path}")
        data["_path"] = str(path)
        found[key] = data
    return found


def jobs_by_name(path: Path) -> dict[str, dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(job["name"]): job for job in payload.get("jobs", [])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--producer-jobs", required=True)
    parser.add_argument("--consumer-jobs", required=True)
    parser.add_argument("--producer-run-id", required=True)
    parser.add_argument("--consumer-run-id", required=True)
    parser.add_argument("--results-dir", required=True)
    args = parser.parse_args()

    root = Path(args.input_root).resolve()
    results = load_results(root)
    producer_jobs = jobs_by_name(Path(args.producer_jobs))
    consumer_jobs = jobs_by_name(Path(args.consumer_jobs))

    expected = {
        (mode, phase, sample)
        for mode in ("control", "shared")
        for phase in ("producer", "consumer")
        for sample in range(3)
    }
    missing = sorted(expected - set(results))
    if missing:
        raise SystemExit(f"missing production-value results: {missing}")

    failed = [
        key for key, value in results.items()
        if key in expected and value.get("status") != "pass"
    ]
    if failed:
        raise SystemExit(f"failed production-value results: {failed}")

    samples: list[dict[str, object]] = []
    for sample in range(3):
        cp = results[("control", "producer", sample)]
        sp = results[("shared", "producer", sample)]
        cc = results[("control", "consumer", sample)]
        sc = results[("shared", "consumer", sample)]

        cp_job = job_seconds(producer_jobs[f"Control producer sample {sample}"])
        sp_job = job_seconds(producer_jobs[f"Shared producer sample {sample}"])
        cc_job = job_seconds(consumer_jobs[f"Control consumer sample {sample}"])
        sc_job = job_seconds(consumer_jobs[f"Shared consumer sample {sample}"])
        sp_save = step_seconds(
            producer_jobs[f"Shared producer sample {sample}"],
            "Save exact shared build cache",
        )
        sc_restore = step_seconds(
            consumer_jobs[f"Shared consumer sample {sample}"],
            "Restore exact producer build cache",
        )

        later_saved = cc_job - sc_job
        later_pct = (later_saved / cc_job * 100.0) if cc_job else 0.0
        control_pair = cp_job + cc_job
        shared_pair = sp_job + sc_job
        pair_saved = control_pair - shared_pair
        pair_pct = (pair_saved / control_pair * 100.0) if control_pair else 0.0

        samples.append({
            "sample": sample,
            "job_seconds": {
                "control_producer": cp_job,
                "shared_producer": sp_job,
                "control_consumer": cc_job,
                "shared_consumer": sc_job,
            },
            "later_run": {
                "saved_seconds": later_saved,
                "saved_percent": later_pct,
            },
            "two_run_compute": {
                "control_seconds": control_pair,
                "shared_seconds": shared_pair,
                "saved_seconds": pair_saved,
                "saved_percent": pair_pct,
            },
            "maven_ms": {
                "control_producer": cp["timing"]["measured_maven_ms"],
                "shared_producer": sp["timing"]["measured_maven_ms"],
                "control_consumer": cc["timing"]["measured_maven_ms"],
                "shared_consumer": sc["timing"]["measured_maven_ms"],
            },
            "shared_prepare_ms": {
                "producer": sp["timing"]["candidate_prepare_ms"],
                "consumer": sc["timing"]["candidate_prepare_ms"],
            },
            "shared_cache_transport": {
                "save_step_seconds": sp_save,
                "restore_step_seconds": sc_restore,
                "producer_files_after": sp["transport"]["cache_files_after"],
                "consumer_files_before": sc["transport"]["cache_files_before"],
                "producer_bytes_after": sp["transport"]["cache_bytes_after"],
                "consumer_bytes_before": sc["transport"]["cache_bytes_before"],
            },
        })

    later_control = [float(s["job_seconds"]["control_consumer"]) for s in samples]
    later_shared = [float(s["job_seconds"]["shared_consumer"]) for s in samples]
    later_saved = [float(s["later_run"]["saved_seconds"]) for s in samples]
    pair_control = [float(s["two_run_compute"]["control_seconds"]) for s in samples]
    pair_shared = [float(s["two_run_compute"]["shared_seconds"]) for s in samples]
    pair_saved = [float(s["two_run_compute"]["saved_seconds"]) for s in samples]
    later_pct = [float(s["later_run"]["saved_percent"]) for s in samples]
    pair_pct = [float(s["two_run_compute"]["saved_percent"]) for s in samples]
    save_steps = [float(s["shared_cache_transport"]["save_step_seconds"]) for s in samples]
    restore_steps = [float(s["shared_cache_transport"]["restore_step_seconds"]) for s in samples]
    cache_bytes = [float(s["shared_cache_transport"]["producer_bytes_after"]) for s in samples]

    first = results[("control", "producer", 0)]
    aggregate = {
        "schema": "brainboxemb.java-ci-production-value-aggregate",
        "schema_version": 2,
        "status": "pass",
        "producer_workflow_run_id": args.producer_run_id,
        "consumer_workflow_run_id": args.consumer_run_id,
        "workload": first["workload"],
        "workload_repository": first["workload_repository"],
        "workload_revision": first["workload_revision"],
        "sample_count": 3,
        "samples": samples,
        "aggregate": {
            "later_run_control_job_seconds": stats(later_control),
            "later_run_shared_job_seconds": stats(later_shared),
            "later_run_saved_seconds": stats(later_saved),
            "two_run_control_job_seconds": stats(pair_control),
            "two_run_shared_job_seconds": stats(pair_shared),
            "two_run_saved_seconds": stats(pair_saved),
            "later_run_saved_percent": stats(later_pct),
            "two_run_saved_percent": stats(pair_pct),
            "shared_cache_save_step_seconds": stats(save_steps),
            "shared_cache_restore_step_seconds": stats(restore_steps),
            "shared_cache_uncompressed_bytes": stats(cache_bytes),
        },
        "production_context": first.get("production_baseline", {}),
        "interpretation_boundary": (
            "Job-duration deltas include runner job setup, checkout, Java setup, "
            "candidate preparation, Maven and cache transport inside the measured jobs. "
            "Existing production preflight/publication work is unchanged and is context, "
            "not claimed cache savings."
        ),
    }

    out = Path(args.results_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(
        json.dumps(aggregate, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# Representative shared-cache production value",
        "",
        f"- Status: **{aggregate['status']}**",
        f"- Workload: `{aggregate['workload_repository']}@{aggregate['workload_revision']}`",
        f"- Samples: {aggregate['sample_count']}",
        f"- Producer workflow: `{args.producer_run_id}`",
        f"- Consumer workflow: `{args.consumer_run_id}`",
        "",
        "## Later-run latency",
        "",
        "| Metric | Median | Min | Max |",
        "| --- | ---: | ---: | ---: |",
        f"| Control consumer job | {stats(later_control)['median']:.1f} s | {min(later_control):.1f} s | {max(later_control):.1f} s |",
        f"| Shared consumer job | {stats(later_shared)['median']:.1f} s | {min(later_shared):.1f} s | {max(later_shared):.1f} s |",
        f"| Saved by shared | {stats(later_saved)['median']:.1f} s | {min(later_saved):.1f} s | {max(later_saved):.1f} s |",
        "",
        "## Two-run hosted-runner compute",
        "",
        "| Metric | Median | Min | Max |",
        "| --- | ---: | ---: | ---: |",
        f"| Control producer + consumer | {stats(pair_control)['median']:.1f} s | {min(pair_control):.1f} s | {max(pair_control):.1f} s |",
        f"| Shared producer + consumer | {stats(pair_shared)['median']:.1f} s | {min(pair_shared):.1f} s | {max(pair_shared):.1f} s |",
        f"| Saved by shared | {stats(pair_saved)['median']:.1f} s | {min(pair_saved):.1f} s | {max(pair_saved):.1f} s |",
        "",
        "## Shared-cache transport",
        "",
        f"- Save step: median {stats(save_steps)['median']:.1f} s (min {min(save_steps):.1f}, max {max(save_steps):.1f})",
        f"- Restore step: median {stats(restore_steps)['median']:.1f} s (min {min(restore_steps):.1f}, max {max(restore_steps):.1f})",
        f"- Uncompressed Maven build-cache bytes: median {stats(cache_bytes)['median']:.0f} B",
        "",
        "## Samples",
        "",
        "| Sample | control producer | shared producer | control consumer | shared consumer | later saved | two-run saved |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for sample in samples:
        jobs = sample["job_seconds"]
        lines.append(
            f"| {sample['sample']} | {jobs['control_producer']:.1f} s | "
            f"{jobs['shared_producer']:.1f} s | {jobs['control_consumer']:.1f} s | "
            f"{jobs['shared_consumer']:.1f} s | {sample['later_run']['saved_seconds']:.1f} s | "
            f"{sample['two_run_compute']['saved_seconds']:.1f} s |"
        )

    baseline = aggregate["production_context"]
    lines.extend([
        "",
        "## Existing production context",
        "",
        f"- Production baseline workflow: `{baseline.get('workflow_run_id')}`",
        f"- Maven reported: {baseline.get('maven_reported_seconds')} s",
        f"- Linux canonical job: {baseline.get('linux_canonical_job_seconds')} s",
        f"- Whole protected-main path to timing capture: {baseline.get('wall_clock_seconds_to_capture')} s",
        f"- Hosted-runner time to capture: {baseline.get('hosted_runner_seconds_to_capture')} s",
        "",
        "The existing production preflight/publication path is unchanged by this benchmark. "
        "Only matched measured-job deltas are cache savings; do not subtract unrelated "
        "production overhead merely to make the cache result look larger.",
        "",
    ])
    (out / "README.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "status": "pass",
        "samples": 3,
        "later_run_saved_seconds_median": stats(later_saved)["median"],
        "two_run_saved_seconds_median": stats(pair_saved)["median"],
        "later_run_saved_percent_median": stats(later_pct)["median"],
        "two_run_saved_percent_median": stats(pair_pct)["median"],
        "cache_save_step_seconds_median": stats(save_steps)["median"],
        "cache_restore_step_seconds_median": stats(restore_steps)["median"],
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
