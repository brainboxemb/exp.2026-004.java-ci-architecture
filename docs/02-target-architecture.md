# Target Java CI architecture

This document is the **design input** for the Java CI Proof of Principle (PoP). The PoP does not choose an architecture by trial and error; it checks the runtime-sensitive assumptions in this design.

## Design goal

Extend the Java execution model established by Migration 006 with safe module-level incremental execution and build-output reuse, without moving Maven lifecycle semantics into GitHub Actions or Moon.

The desired result is:

- irrelevant repository changes stop before Java setup/build work;
- affected Java builds remain one understandable Maven lifecycle;
- unchanged Maven modules may reuse validated outputs instead of repeating work;
- changed modules and their affected dependents are invalidated correctly;
- fresh CI runners can reuse eligible outputs across runs;
- release/platform qualification can deliberately force fresh execution where required;
- execute/reuse/skip decisions are retained as evidence.

## Responsibility model

```text
GitHub event / exact source
          |
          v
GitHub Actions
  runner, job and artifact orchestration
          |
          v
Moon / generic repository affected layer
  should this Java capability run at all?
  which platform-qualification policy applies?
          |
          v
Maven
  project graph, lifecycle, build and test semantics
          |
          v
Maven-native build cache (target PoP mechanism)
  module input fingerprinting
  module output reuse / restore
  local and cross-run cache semantics
          |
          v
canonical artifacts + tests + structured evidence
```

### GitHub Actions

GitHub Actions owns infrastructure orchestration only:

- event handling and exact-source checkout;
- Linux/Windows runner allocation;
- dependency/cache transport where required;
- job dependencies and artifact transfer;
- publication of testcase/evidence artifacts.

It should not contain hand-maintained Java module dependency logic or decide which Maven module output is valid for reuse.

### Moon / repository affected layer

Moon remains the repository/capability affected layer established by Migration 006. Its primary Java question is whether Java work should start at all and whether a change requires ordinary smoke or full platform qualification.

Moon may expose structured affected/task evidence, but the target design does **not** make Moon the Java module build-output authority merely because Moon also supports task caching.

### Maven

Maven remains Java build/test semantic authority:

- reactor/project graph;
- lifecycle execution;
- plugin execution;
- tests;
- artifact construction.

The canonical build continues to be expressed as Maven lifecycle execution, normally `verify`, rather than a generated set of per-module GitHub jobs.

### Maven-native build cache

The target PoP mechanism for module-level incremental/cache behaviour is Apache Maven Build Cache Extension. It operates inside Maven's project/lifecycle model and can calculate module input keys, reuse/restore outputs and support local or remote caches.

This is a **target design choice subject to PoP qualification**, not yet a production decision. If the PoP finds correctness, observability or CI portability problems that cannot be resolved cleanly, the architecture must be reconsidered before production rollout.

## Cache layers are separate

The architecture distinguishes these caches explicitly:

```text
Maven dependency cache
  downloaded dependencies/plugins
  !=
Maven build-output cache
  compiled/generated/test/package outputs and build state
```

A warm `~/.m2/repository` alone is not evidence of an incremental build.

Likewise, same-worktree Maven behaviour is not evidence that reuse works on a fresh hosted runner. Cross-run reuse requires an explicit transport/remote-cache boundary and its own testcase.

## Normal CI flow

```text
exact base -> exact head
        |
        v
affected preflight
        |
        +-- unrelated ----------------------> stop
        |
        v
canonical Linux Maven verify
  dependency cache may be warm
  build cache may reuse valid module state
        |
        +--> canonical artifacts/evidence
        |
        +--> selected Windows policy
                smoke: exact Linux artifact
                full : native Windows Maven + exact-artifact smoke
        |
        v
publication reuses canonical prepared output
```

The Windows event policy from Migration 006 remains unchanged by this PoP. Incremental Java execution must not accidentally make ordinary protected-main publication allocate Windows runners again.

## Qualification boundaries

Not every event should maximize cache reuse.

The target policy is:

- normal PR/local CI: eligible safe cache reads/writes;
- fresh-runner testcase: explicitly prove cross-run hydration;
- cache diagnostics: allow read-only, write-only or disabled modes where useful;
- exact release qualification: correctness takes precedence over cache speed; the release path must support forcing a fresh Maven execution rather than depending on a prior cached result.

The exact production release setting is a later qualification decision. The PoP must prove that a cache-disabled/fresh path remains available and produces the expected artifacts/tests.

## Evidence contract

CI should make these states distinguishable without relying on ad-hoc human log reading:

- Java capability skipped before Maven;
- Maven module executed;
- Maven module restored/reused from cache;
- cache miss and normal fallback build;
- invalidation caused by source/model/toolchain input changes;
- test execution or test-result reuse;
- exact source, toolchain and cache configuration used.

Prefer native structured Maven/cache records plus the existing generic filesystem/test observations. Free-form log parsing is diagnostic fallback, not the primary oracle.

## Design decisions versus PoP questions

### Design decisions

These are not open candidate competitions:

1. GitHub Actions owns runner/job/event orchestration.
2. Moon owns repository/capability affected selection, not the Maven lifecycle.
3. Maven remains Java build/test authority.
4. Module-level reuse should stay inside Maven semantics if Maven-native caching proves fit for purpose.
5. Dependency caching and build-output caching are separate concerns.
6. Publication reuses canonical build output and never rebuilds merely to publish.
7. Release qualification must retain a forced-fresh path.

### Questions that require PoP evidence

1. Does Maven Build Cache reuse an unchanged module without re-running unnecessary tests/plugins in our fixture?
2. Does an application-only change avoid invalidating independent/upstream modules?
3. Does a shared/core change correctly invalidate all required dependents?
4. Do POM/plugin/compiler/toolchain-relevant changes invalidate cached state correctly?
5. Can eligible build outputs be restored on a fresh GitHub runner without stale or missing state?
6. Can execute/reuse/miss decisions be retained as reliable structured evidence?
7. Is the overhead worthwhile for the scale of our Java repositories?

If these principles pass, later qualification expands edge/error/platform coverage. If a principle fails, change the concept first; do not hide the failure by weakening the testcase.
