# Declarative testcase model

Testcases describe CI behaviour as data. They do not contain shell snippets or candidate-specific probing logic.

## File format

Testcases are TOML files under `tests/cases/`. TOML is used because it is readable in review and Python 3.11+ can parse it using the standard library (`tomllib`) without adding a parser dependency to the harness.

A testcase has four sections:

```toml
id = "CI-04"
title = "Application-only source change"
question = "Which outputs are reproduced after an application-only source change?"

[setup]
mode = "warm"

[[changes]]
path = "app/src/main/java/org/brainboxemb/ci/App.java"
operation = "replace"
find = "return featureA + featureB;"
replace = "return new String(featureA + featureB);"

[expect]
tests_pass = true
required_artifacts = ["app/target/app-1.0.0-SNAPSHOT.jar"]
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

## Correctness expectations

Bootstrap assertions are candidate-independent:

- Maven/candidate exit status;
- required output artifacts;
- expected Surefire report count.

Correctness assertions determine testcase pass/fail.

## Observations are not log greps

The harness also records before/after filesystem evidence without asserting a preferred architecture yet:

- module JAR SHA-256, size and modification time;
- Surefire XML SHA-256, size and modification time;
- whether content or modification time changed;
- measured invocation duration;
- exact Java/Maven runtime;
- exact testcase, candidate and fixture-input hashes;
- GitHub source revision/run provenance when executed in Actions.

This allows the bootstrap baseline to answer questions such as “was an artifact reproduced?” and “was a test report rewritten?” without parsing human Maven log messages.

A later phase may add explicit selectivity expectations once the observation contract is proven across multiple candidate types. Candidate-native structured reports (for example Moon CI reports) should be retained and normalized rather than replaced by custom text probing.

## Candidate contract

The generic harness invokes a candidate adapter with:

```text
candidate + isolated fixture worktree + testcase metadata + result directory
```

The candidate definition supplies its command/capabilities. The harness applies the same setup/change sequence and correctness assertions around every candidate.

The normalized result uses schema `brainboxemb.java-ci-experiment-result` version 1 and retains candidate-independent observations plus provenance.

## CI orchestration

GitHub Actions:

1. discovers `tests/cases/*.toml` and `candidates/*/candidate.toml`;
2. creates a matrix over cases and candidates;
3. checks out one exact source revision;
4. sets up the required Java baseline;
5. prepares an exact Maven Wrapper when required by the fixture;
6. invokes the local generic testcase Action;
7. uploads each result directory;
8. fails a matrix cell when correctness assertions fail.

The workflow is orchestration. It must not duplicate testcase semantics.
