# Declarative testcase model

Testcases describe CI behaviour as data. They do not contain shell snippets or candidate-specific probing logic.

## File format

Testcases are TOML files under `tests/cases/`. TOML is used because it is readable in review and Python 3.11+ can parse it using the standard library (`tomllib`) without adding a parser dependency to the harness.

A testcase has four sections:

```toml
id = "CI-04"
title = "Application-only source change"
question = "Does an application-only change avoid invalidating independent library modules?"

[setup]
mode = "warm"

[[changes]]
path = "app/src/main/java/org/brainboxemb/ci/App.java"
operation = "replace"
find = "return featureA + featureB;"
replace = "return featureA + featureB + \"!\";"

[expect]
build_required = true
required_artifacts = ["app/target/app-1.0.0-SNAPSHOT.jar"]
tests_pass = true
```

## Setup mode

`setup.mode` currently supports:

- `cold` — no priming build before the measured invocation;
- `warm` — execute one unmeasured priming invocation, apply the declared change, then execute the measured invocation.

Later cross-run/fresh-runner cases will add explicit cache transfer/setup semantics instead of overloading `warm`.

## Changes

Each `[[changes]]` entry names a path relative to `fixture/` and one controlled operation.

Bootstrap operations:

- `replace` — replace one exact text fragment; failure to find it fails the testcase;
- `append` — append literal text to an existing file.

Changes are applied by the generic harness, not the candidate.

## Expectations

Bootstrap expectations intentionally focus on candidate-independent correctness:

- whether a build invocation is required for the case;
- Maven exit status;
- required output artifacts;
- test success;
- source/output checksums and invocation timing retained in evidence.

Module execution/reuse assertions will be added only with a reliable structured observation mechanism. Free-form Maven-log greps are not accepted as the long-term execution oracle.

This is deliberate: the experiment must not claim module-level incremental execution before it can prove that state without fragile text matching.

## Candidate contract

The generic harness invokes a candidate adapter with:

```text
candidate + isolated fixture worktree + testcase metadata + result directory
```

The adapter returns structured execution information. The harness adds candidate-independent evidence and evaluates testcase assertions.

The normalized result contains at least:

```json
{
  "schema": "brainboxemb.java-ci-experiment-result",
  "schema_version": 1,
  "case": "CI-04",
  "candidate": "maven-baseline",
  "status": "pass",
  "setup_mode": "warm",
  "build": {
    "required": true,
    "executed": true,
    "exit_code": 0,
    "duration_ms": 0
  },
  "assertions": [],
  "artifacts": [],
  "toolchain": {}
}
```

Additional candidate-specific evidence may be linked from this result, but cannot replace the normalized fields.

## CI orchestration

GitHub Actions:

1. discovers `tests/cases/*.toml`;
2. creates a matrix over cases and enabled candidates;
3. checks out one exact source revision;
4. sets up the required Java baseline;
5. invokes the local generic testcase Action;
6. uploads each result directory;
7. fails the matrix cell if assertions fail.

The workflow is orchestration. It must not duplicate testcase semantics.
