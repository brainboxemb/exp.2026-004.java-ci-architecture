# Target Java CI architecture

This document is the **design input** for the Java CI Proof of Principle (PoP). The PoP does not choose an architecture by trial and error; it checks the runtime-sensitive assumptions in this design.

## Design goal

Extend the Java execution model established by Migration 006 with safe module-level incremental execution and build-output reuse, without moving Maven lifecycle semantics into GitHub Actions or Moon.

The desired result is:

- irrelevant repository changes stop before Java setup/build work;
- affected Java builds remain one understandable Maven lifecycle;
- unchanged Maven modules may reuse validated outputs instead of repeating work;
- changed modules and their affected dependents are invalidated correctly;
- fresh CI runners can reuse eligible outputs through an explicit shared transport;
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

## Cache adoption modes

Build-output caching is an **optional optimisation capability**, not part of Java correctness semantics. A project should not pay cache setup/maintenance cost merely because the shared framework supports it.

The intended project-level modes are:

```text
none
  ordinary Maven lifecycle; no build-output cache reuse

local
  Maven Build Cache local reuse for development or same-environment workflows

shared
  Maven Build Cache reuse across CI runs/runners through an explicitly qualified shared transport
```

`none` is the safe initial/default mode. Projects opt into `local` or `shared` when repository size, module count or test/build cost makes the optimisation worthwhile.

For the first qualified `shared` implementation, GitHub Actions transports Maven's **local build-cache directory** between hosted runners. GitHub does not decide module validity and does not become a second Java build-cache engine; Maven still owns cache keys and restore semantics. This qualification proves fresh-runner/cross-job reuse. Retention across separate workflow runs is a distinct question and is not implied by that result.

Forced-fresh execution is **orthogonal** to the configured mode. Qualification/release diagnostics must be able to disable cache reads and execute the ordinary Maven lifecycle without introducing a second build architecture. The Maven Build Cache extension provides this through `maven.build.cache.skipCache`; cache saving can be disabled separately when a qualification run must neither consume nor publish cached state.

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

Likewise, same-worktree Maven behaviour is not evidence that reuse works on a fresh hosted runner. Fresh-runner reuse requires an explicit transport/remote-cache boundary and its own testcase.

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

## Runtime identity and retained test evidence

The PoP exposed two constraints that are now part of the target design.

### Runtime-separated cache namespace

Apache Maven Build Cache 1.3.0 did not, in the fixture, automatically invalidate cached module state when the actual JDK running Maven changed from Java 8 to Java 17. Therefore the shared Java cache adapter must partition cache storage by the relevant runtime identity before Maven performs module-level lookup.

The qualified namespace fingerprint includes:

- JDK release metadata from the selected `JAVA_HOME`;
- operating system and architecture;
- exact Maven Wrapper properties identity.

This is a correctness boundary, not merely a cache-performance key. A runtime identity change selects a different Maven build-cache namespace and therefore cannot accidentally consume state produced under the previous runtime.

### Repository/build identity is a cache correctness input

The representative real consumer embeds `git.commit.id.full` and a build timestamp in its executable JAR. Source-file equality alone is therefore not sufficient evidence that this module's packaged output is reusable: a different Git commit may require different artifact bytes even when the tracked tree is identical.

CI-16 qualifies this explicitly before release policy is finalized. The target rule is narrow rather than repository-wide: modules whose output does not depend on repository identity should remain eligible for reuse, while an artifact that embeds the concrete Git revision must never retain an earlier revision.

If the baseline Maven checksum does not observe this input, the adapter/product cache contract must add the smallest correct module/plugin-specific identity input and qualify it here. Globally partitioning all module cache state by repository SHA is a fallback, not the preferred first solution, because it would unnecessarily destroy cross-commit reuse.

### Surefire reports are cache outputs

Module reuse can legitimately skip test execution. On a fresh runner, however, skipped tests leave no local Surefire XML unless those reports are restored as part of the validated module output.

The qualified Maven Build Cache configuration therefore attaches `surefire-reports` as additional cached output. Fresh-runner reuse must restore both the canonical artifacts and the test evidence expected by CI.

## Qualification boundaries

Not every event should maximize cache reuse.

The target policy is:

- normal PR/local CI: ordinary Maven by default; cache reads/writes only when the project explicitly enables a qualified cache mode;
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
8. Build-output caching is optional and project-configurable; `none` remains a valid first-class mode.

### Questions that require PoP evidence

1. Does Maven Build Cache reuse an unchanged module without re-running unnecessary tests/plugins in our fixture?
2. Does an application-only change avoid invalidating independent/upstream modules?
3. Does a shared/core change correctly invalidate all required dependents?
4. Do POM/plugin/compiler/toolchain-relevant changes invalidate cached state correctly?
5. Can eligible build outputs be restored on a fresh GitHub runner without stale or missing state?
6. Can execute/reuse/miss decisions be retained as reliable structured evidence?
7. Is the overhead worthwhile for the scale of our Java repositories?
8. If shared cache retention beyond one workflow execution is needed, does it remain reliable across separate workflow runs and retention windows?
9. When product output embeds Git/build identity, does repository identity participate in invalidation narrowly enough to keep that artifact correct without needlessly rebuilding unrelated modules?

If these principles pass, later qualification expands edge/error/platform coverage. If a principle fails, change the concept first; do not hide the failure by weakening the testcase.
