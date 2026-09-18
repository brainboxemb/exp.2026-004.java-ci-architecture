#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
import tomllib
import xml.etree.ElementTree as ET

from run_case import capture_maven_cache_report, command_output, execute, sha256


SCHEMA = "brainboxemb.java-ci-git-identity-result"
SCHEMA_VERSION = 1


def parse_properties(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        result[key.strip()] = value.strip()
    return result


def jar_properties(jar: Path, resource: str) -> dict[str, str]:
    if not jar.is_file():
        raise RuntimeError(f"identity artifact does not exist: {jar}")
    with zipfile.ZipFile(jar) as archive:
        try:
            raw = archive.read(resource).decode("utf-8")
        except KeyError as exc:
            raise RuntimeError(
                f"identity resource {resource} is missing from {jar}"
            ) from exc
    return parse_properties(raw)


def file_count(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file())


def module_output_count(root: Path) -> int:
    return sum(
        1
        for path in root.glob("*/target/**/*")
        if path.is_file()
    )


def remove_outputs(root: Path) -> None:
    root_target = root / "target"
    if root_target.exists():
        shutil.rmtree(root_target)
    for target in root.glob("*/target"):
        if target.exists():
            shutil.rmtree(target)


def cache_sources(native_cache: dict[str, object] | None) -> dict[str, str | None]:
    return {
        str(project.get("artifact_id")): project.get("source")
        for project in (native_cache or {}).get("projects", [])
    }


def git(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *command],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(command)} failed ({completed.returncode}):\n{completed.stdout}"
        )
    return completed.stdout.strip()


def apply_project_cache_input(
    work: Path,
    module_pom: str,
    property_name: str,
    input_path: str,
) -> dict[str, str]:
    pom = work / module_pom
    if not pom.is_file():
        raise RuntimeError(f"cache-input module POM does not exist: {pom}")

    namespace = "http://maven.apache.org/POM/4.0.0"
    ET.register_namespace("", namespace)
    tree = ET.parse(pom)
    root = tree.getroot()
    ns = {"m": namespace}

    properties = root.find("m:properties", ns)
    if properties is None:
        properties = ET.Element(f"{{{namespace}}}properties")
        artifact_id = root.find("m:artifactId", ns)
        insert_at = list(root).index(artifact_id) + 1 if artifact_id is not None else 1
        root.insert(insert_at, properties)

    existing = properties.find(f"m:{property_name}", ns)
    if existing is None:
        existing = ET.SubElement(properties, f"{{{namespace}}}{property_name}")
    existing.text = input_path

    tree.write(pom, encoding="utf-8", xml_declaration=True)
    return {
        "module_pom": module_pom,
        "property": property_name,
        "path": input_path,
        "pom_sha256": sha256(pom),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--workload-dir", required=True)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--results-dir", required=True)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    case_path = (repo / args.case).resolve()
    case = tomllib.loads(case_path.read_text(encoding="utf-8"))
    if str(case.get("setup", {}).get("mode")) != "git-identity-change":
        raise SystemExit("identity harness requires setup mode git-identity-change")

    candidate_dir = repo / "candidates" / args.candidate
    candidate = tomllib.loads(
        (candidate_dir / "candidate.toml").read_text(encoding="utf-8")
    )
    if str(candidate.get("id")) != "maven-build-cache":
        raise SystemExit("CI-16 currently qualifies the Maven Build Cache target")

    workload_ref = str(case["workload"]["definition"])
    workload_path = (repo / workload_ref).resolve()
    workload = tomllib.loads(workload_path.read_text(encoding="utf-8"))
    work = Path(args.workload_dir).resolve()
    cache_base = Path(args.cache_dir).resolve()
    result_dir = (repo / args.results_dir).resolve()

    if result_dir.exists():
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True)
    producer_dir = result_dir / "producer"
    consumer_dir = result_dir / "consumer"
    producer_dir.mkdir()
    consumer_dir.mkdir()

    expected_workload_revision = str(workload["revision"])
    producer_revision = git(["rev-parse", "HEAD"], work)
    producer_tree = git(["rev-parse", "HEAD^{tree}"], work)
    if producer_revision != expected_workload_revision:
        raise SystemExit(
            f"workload source {producer_revision} does not match declared "
            f"{expected_workload_revision}"
        )

    correction_cfg = case.get("correction", {})
    correction = apply_project_cache_input(
        work,
        str(correction_cfg["module_pom"]),
        str(correction_cfg["cache_input_property"]),
        str(correction_cfg["cache_input_path"]),
    )

    # Prepare the target adapter once. The generated .mvn cache configuration is
    # deliberately left uncommitted. The app-specific Maven cache-input
    # declaration is likewise a PoP correction applied only in this isolated
    # workload checkout; no production repository is modified.
    prepare = execute(
        ["bash", str(candidate_dir / "prepare.sh")],
        work,
        result_dir / "prepare.log",
    )
    if prepare["exit_code"] != 0:
        raise SystemExit("candidate preparation failed")

    if cache_base.exists():
        shutil.rmtree(cache_base)
    cache_base.mkdir(parents=True)
    cache_env = {"MAVEN_BUILD_CACHE_BASE": str(cache_base)}

    producer = execute(
        ["bash", str(candidate_dir / "run.sh"), "verify"],
        work,
        producer_dir / "measured.log",
        cache_env,
    )
    producer_cache = capture_maven_cache_report(work, producer_dir)
    producer_sources = cache_sources(producer_cache)

    identity_artifact_rel = str(case["workload"]["identity_artifact"])
    identity_resource = str(case["workload"]["identity_resource"])
    revision_property = str(case["workload"]["revision_property"])
    timestamp_property = str(case["workload"]["timestamp_property"])
    identity_artifact = work / identity_artifact_rel
    producer_identity = jar_properties(identity_artifact, identity_resource)
    producer_artifact_sha256 = sha256(identity_artifact)
    producer_cache_files = file_count(cache_base)
    corrected_worktree_diff = command_output(["git", "diff", "--", correction["module_pom"]], work)

    # Change repository identity only: a child commit with the same tree.
    git(["config", "user.name", "Java CI PoP"], work)
    git(["config", "user.email", "java-ci-pop@invalid.example"], work)
    commit_env = os.environ.copy()
    commit_env.update({
        "GIT_AUTHOR_DATE": "2026-01-02T03:04:05Z",
        "GIT_COMMITTER_DATE": "2026-01-02T03:04:05Z",
    })
    completed = subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "PoP identical tree, new Git identity"],
        cwd=work,
        env=commit_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"unable to create identity-only commit:\n{completed.stdout}")

    consumer_revision = git(["rev-parse", "HEAD"], work)
    consumer_tree = git(["rev-parse", "HEAD^{tree}"], work)

    # Model a fresh canonical workspace while retaining only the qualified Maven
    # build-output cache. No module output may survive locally.
    remove_outputs(work)
    consumer_outputs_before = module_output_count(work)

    # Ensure the build-time property has a chance to differ even on coarse clocks.
    time.sleep(1)

    consumer = execute(
        ["bash", str(candidate_dir / "run.sh"), "verify"],
        work,
        consumer_dir / "measured.log",
        cache_env,
    )
    consumer_cache = capture_maven_cache_report(work, consumer_dir)
    consumer_sources = cache_sources(consumer_cache)
    consumer_identity = jar_properties(identity_artifact, identity_resource)
    consumer_artifact_sha256 = sha256(identity_artifact)
    consumer_cache_files = file_count(cache_base)

    reports = sorted(work.glob("*/target/surefire-reports/TEST-*.xml"))
    required_artifacts = [str(v) for v in workload.get("required_artifacts", [])]
    expected_reports = int(workload.get("expected_test_reports", 0))

    assertions: list[dict[str, object]] = [
        {
            "name": "producer-build-exit",
            "kind": "correctness",
            "passed": producer["exit_code"] == 0,
            "exit_code": producer["exit_code"],
        },
        {
            "name": "git-revision-changed",
            "kind": "qualification",
            "passed": producer_revision != consumer_revision,
            "producer": producer_revision,
            "consumer": consumer_revision,
        },
        {
            "name": "git-tree-identical",
            "kind": "qualification",
            "passed": producer_tree == consumer_tree,
            "producer": producer_tree,
            "consumer": consumer_tree,
        },
        {
            "name": "fresh-consumer-module-output-state",
            "kind": "correctness",
            "passed": consumer_outputs_before == 0,
            "expected": 0,
            "actual": consumer_outputs_before,
        },
        {
            "name": "consumer-build-exit",
            "kind": "correctness",
            "passed": consumer["exit_code"] == 0,
            "exit_code": consumer["exit_code"],
        },
        {
            "name": "producer-embedded-revision",
            "kind": "correctness",
            "passed": producer_identity.get(revision_property) == producer_revision,
            "expected": producer_revision,
            "actual": producer_identity.get(revision_property),
        },
        {
            "name": "consumer-embedded-revision",
            "kind": "correctness",
            "passed": consumer_identity.get(revision_property) == consumer_revision,
            "expected": consumer_revision,
            "actual": consumer_identity.get(revision_property),
        },
        {
            "name": "no-stale-producer-revision",
            "kind": "correctness",
            "passed": consumer_identity.get(revision_property) != producer_revision,
            "stale_revision": producer_revision,
            "actual": consumer_identity.get(revision_property),
        },
        {
            "name": "test-report-count",
            "kind": "correctness",
            "passed": len(reports) == expected_reports,
            "expected": expected_reports,
            "actual": len(reports),
        },
    ]

    for rel in required_artifacts:
        assertions.append({
            "name": f"artifact:{rel}",
            "kind": "correctness",
            "passed": (work / rel).is_file(),
        })

    passed = all(bool(item["passed"]) for item in assertions)
    result = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "case": case["id"],
        "title": case["title"],
        "question": case["question"],
        "status": "pass" if passed else "fail",
        "candidate": candidate["id"],
        "correction": {
            **correction,
            "worktree_diff": corrected_worktree_diff,
        },
        "workload": {
            "repository": workload["repository"],
            "declared_revision": expected_workload_revision,
            "producer_revision": producer_revision,
            "consumer_revision": consumer_revision,
            "producer_tree": producer_tree,
            "consumer_tree": consumer_tree,
        },
        "identity": {
            "artifact": identity_artifact_rel,
            "resource": identity_resource,
            "revision_property": revision_property,
            "timestamp_property": timestamp_property,
            "producer": producer_identity,
            "consumer": consumer_identity,
            "producer_artifact_sha256": producer_artifact_sha256,
            "consumer_artifact_sha256": consumer_artifact_sha256,
        },
        "producer": {
            "execution": producer,
            "native_cache": producer_cache,
            "native_cache_sources": producer_sources,
            "cache_files_after": producer_cache_files,
        },
        "consumer": {
            "execution": consumer,
            "module_output_files_before": consumer_outputs_before,
            "native_cache": consumer_cache,
            "native_cache_sources": consumer_sources,
            "cache_files_after": consumer_cache_files,
            "test_reports": [str(p.relative_to(work)) for p in reports],
        },
        "assertions": assertions,
        "provenance": {
            "experiment_source_revision": os.environ.get("EXPERIMENT_SOURCE_REVISION"),
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
            "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "case_definition_sha256": sha256(case_path),
            "workload_definition_sha256": sha256(workload_path),
            "candidate_definition_sha256": sha256(candidate_dir / "candidate.toml"),
        },
    }
    (result_dir / "result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        f"# {case['id']} — {case['title']}",
        "",
        f"- Status: **{result['status']}**",
        f"- Producer revision: `{producer_revision}`",
        f"- Consumer revision: `{consumer_revision}`",
        f"- Git tree identical: `{str(producer_tree == consumer_tree).lower()}`",
        f"- Correction: `{correction['module_pom']}` adds `{correction['property']}={correction['path']}`",
        f"- Consumer output files before Maven: `{consumer_outputs_before}`",
        f"- Producer embedded revision: `{producer_identity.get(revision_property)}`",
        f"- Consumer embedded revision: `{consumer_identity.get(revision_property)}`",
        f"- Producer embedded timestamp: `{producer_identity.get(timestamp_property)}`",
        f"- Consumer embedded timestamp: `{consumer_identity.get(timestamp_property)}`",
        f"- Producer cache sources: `{producer_sources}`",
        f"- Consumer cache sources: `{consumer_sources}`",
        "",
        "## Assertions",
        "",
    ]
    for assertion in assertions:
        lines.append(
            f"- {'PASS' if assertion['passed'] else 'FAIL'} — {assertion['name']}"
        )
    (result_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "case": case["id"],
        "status": result["status"],
        "producer_revision": producer_revision,
        "consumer_revision": consumer_revision,
        "consumer_embedded_revision": consumer_identity.get(revision_property),
        "consumer_cache_sources": consumer_sources,
    }))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
