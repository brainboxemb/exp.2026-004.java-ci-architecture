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
- `warm` — execute one unmeasured priming invocation, apply the declared change, then execute the measured invocation;
- `fresh-cache-reuse` — a producer job creates Maven build-cache state and a separate consumer runner restores that transported cache into an otherwise fresh fixture worktree;
- `fresh-cache-miss` — a fresh runner explicitly receives no transported build cache and must fall back to a normal build.

Fresh-runner modes are orchestrated as separate GitHub jobs. They are not simulated by deleting files inside one warm job.

## Candidate-specific measured execution

A testcase may add arguments to the **measured** invocation for one candidate without changing the priming invocation:

```toml
[execute.candidates.maven-build-cache]
measured_append = [
  "-Dmaven.build.cache.skipCache=true",
  "-Dmaven.build.cache.skipSave=true",
]
```

This is intended for qualification modes such as forced-fresh/cache-bypass. The candidate still owns the base Maven command; the testcase only declares the execution condition it needs to prove. The normalized result retains the base command, appended arguments and final measured command.

Do not use this mechanism to encode a second build lifecycle in a testcase.

A testcase may also select an actual runtime identity for prime and measured invocations using environment variables already exposed by the runner:

```toml
[execute.prime_env_from]
JAVA_HOME = "JAVA_HOME_8_X64"

[execute.measured_env_from]
JAVA_HOME = "JAVA_HOME_17_X64"
```

The harness records the resulting Maven runtime information for both invocations. This allows runtime/toolchain invalidation to be tested without mutating the Maven project model merely to imitate a JDK change.

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

Candidate-specific qualification expectations may additionally assert normalized workset fields, native cache sources and the cache-read-disabled state. They remain declarative in TOML; the generic harness evaluates them without testcase-specific probing code.

## Observations are not log greps

The harness also records before/after filesystem evidence without asserting a preferred architecture yet:

- module JAR SHA-256, size and modification time;
- Surefire XML SHA-256, size and modification time;
- whether content or modification time changed;
- measured invocation duration;
- exact Java/Maven runtime;
- exact testcase, candidate and fixture-input hashes;
- exact checked-out repository source revision plus the GitHub event SHA/run provenance.

On pull requests GitHub's event SHA may identify a synthetic merge revision. The workflow therefore resolves the intended PR-head revision explicitly, checks out that exact revision, passes it to the harness and records the event SHA separately. The harness refuses to run when the checked-out revision differs from the requested source revision.

This allows the bootstrap baseline to answer questions such as “was an artifact reproduced?” and “was a test report rewritten?” without parsing human Maven log messages.

A later phase may add explicit selectivity expectations once the observation contract is proven across multiple candidate types. Candidate-native structured reports (for example Moon CI reports) should be retained and normalized rather than replaced by custom text probing.

## Candidate contract

The generic harness invokes a candidate adapter with:

```text
candidate + isolated fixture worktree + testcase metadata + result directory
```

The candidate definition supplies its command/capabilities. The harness applies the same setup/change sequence and correctness assertions around every candidate.

The normalized result uses schema `brainboxemb.java-ci-experiment-result` version 4 and retains candidate-independent observations, candidate-native normalized evidence, execution-mode data and provenance. Native cache evidence retains the original Maven source value as `source_raw` while `source` is the normalized cross-candidate execution state.

## CI orchestration

GitHub Actions:

1. resolves the exact source revision (PR head for pull requests, event SHA otherwise);
2. discovers local and fresh-runner testcase modes from that exact source;
3. creates the normal case/candidate matrix for `cold`/`warm` cases;
4. checks out the same exact source revision in every testcase job;
5. sets up the required Java baseline and exact Maven Wrapper;
6. invokes the local generic testcase Action for local cases;
7. for `fresh-cache-reuse`, runs a producer and a dependent consumer on separate hosted runners, transporting only Maven's build-cache directory between them;
8. for `fresh-cache-miss`, proves an explicit transport miss and normal Maven fallback;
9. uploads every result directory and fails when correctness/qualification assertions fail.

The workflow is orchestration. It must not duplicate testcase semantics.
