# Proof of Principle plan

The PoP exists to prove the essential runtime principles of the target architecture in [`02-target-architecture.md`](02-target-architecture.md). It is intentionally smaller than the eventual production qualification suite.

## Phase model

```text
Concept / target architecture
        ↓
Proof of Principle
        ↓
Qualification
        ↓
Production migration
```

A PoP failure is useful evidence. It means the concept or assumption needs correction; it is not a reason to weaken the testcase.

The sequence above describes **initial adoption**, not the lifetime of this repository. The PoP environment remains available afterward as a repeatable qualification and regression facility.

## Control baseline

The existing plain-Maven baseline is retained as the control:

- exact main: `1f2dde6629e2acc6f6b86c482939c7752939c2f6`;
- workflow run: `35233519246`;
- fixture: `core -> feature-a/feature-b -> app`;
- original cases: CI-01 through CI-05.

Observed control behaviour:

- warm/no-op: module JARs are not rewritten, while all Surefire reports are rewritten;
- docs-only: module JARs are not rewritten, while all Surefire reports are rewritten;
- app-only source change: only the app JAR is reproduced, while all Surefire reports are rewritten;
- core source change: all four module JARs and all Surefire reports are rewritten.

These observations define the control, not the desired architecture.

## What “incremental” must prove

A useful incremental build is not merely correct; it must perform less work and that reduction must be measurable.

For every relevant PoP case, record three dimensions separately:

1. **Invalidation** — which module/test inputs became invalid?
2. **Execution** — which module lifecycle work and unit tests actually executed versus reused/skipped?
3. **Performance** — total measured invocation duration and, where native structured evidence supports it, module/cache timing and build metadata.

A cache that produces correct outputs but still executes nearly all lifecycle/test work is not a useful incremental result.

Total timing alone is also insufficient. A small fixture can be dominated by Maven/JVM/cache startup overhead, so timing is interpreted together with native cache evidence and artifact/test observations. A later qualification phase may add a larger controlled workload when the basic principle works.

## Minimal PoP implementation

Add one target implementation adapter for Maven-native build caching. Do not implement Moon-output-cache and hybrid alternatives merely to create a benchmark tournament.

An alternative implementation is added only when the target mechanism fails a principle or leaves a material design question unresolved.

## PoP questions and cases

### PoP-01 — unchanged warm module state

**Question:** Can Maven-native build caching reuse unchanged module work, including avoiding unnecessary lifecycle/test work, while preserving correct outputs?

Use the identical warm case and retain cache-native evidence plus generic artifact/test observations and measured duration.

### PoP-02 — application-only production change

**Question:** Does an app-only source change rebuild only what Maven semantics require while safely reusing unaffected module state?

Expected principle: no unnecessary rebuild/retest of independent upstream modules. The measured work/time should reflect only the invalidated graph rather than a near-full reactor build.

### PoP-03 — production code plus its unit test

**Question:** When production code in one module and its corresponding unit test change together, is the changed JAR rebuilt, is the changed test actually executed against it, and are unaffected modules reused?

This protects against a cache hit that restores either stale production output or a stale test result.

### PoP-04 — unit-test-only change and test granularity

**Question:** When one unit test changes and production code does not, what is the actual execution granularity?

The affected module contains multiple test classes so the PoP can distinguish:

- only the changed test executes;
- all tests in that module execute;
- or test execution is incorrectly restored/skipped from stale cache state.

Maven Surefire supports explicit test selection, but the PoP does not assume automatic changed-test detection. First measure Maven + Build Cache + Surefire behaviour. A separate changed-test-selection mechanism is considered only if this measured behaviour leaves meaningful avoidable cost.

Expected correctness principle: the changed test must execute. Production JAR content need not change merely because a test changes.

### PoP-05 — shared/core change

**Question:** Does changing shared core state invalidate every dependent module that must be rebuilt/tested?

Expected principle: correctness dominates hit rate; no dependent may reuse stale state.

### PoP-06 — build-model/toolchain invalidation

**Question:** Does a relevant POM, plugin/compiler configuration or equivalent build-input change invalidate cached state correctly?

Start with one representative compiler/build-model property change; broaden only during qualification if the principle works.

### PoP-07 — fresh-runner reuse

**Question:** Can a new GitHub-hosted runner restore valid build state produced by an earlier run?

This requires explicit cross-run cache transport or Maven remote-cache semantics. The testcase must record producer source/config/cache identity and consumer source/config/cache identity.

A same-job warm build does not satisfy this case.

### PoP-08 — forced-fresh equivalence

**Question:** Can the same source be built successfully with cache reads/writes bypassed so release qualification never depends on cached build state?

The fresh path must execute the required tests and produce the expected canonical artifacts.

## Evidence sources

Prefer native structured Maven Build Cache records over log scraping. The extension provides cache/build XML metadata such as `build-cache-report.xml`, `buildinfo.xml`/`lookupinfo.xml`, checksums, lifecycle/plugin match state, completed executions and build metadata. The harness may normalize these records but should preserve the originals.

Generic observations remain useful for independent verification:

- JAR content/mtime before and after;
- Surefire report content/mtime before and after;
- exact testcase/candidate/source/toolchain hashes;
- total measured wall time.

## PoP acceptance

The target principle is supported only when:

- correctness assertions pass;
- invalidation matches dependency/build-model/test-input semantics;
- structured evidence distinguishes hit/miss/execute/reuse;
- changed unit tests demonstrably execute;
- test execution granularity is understood rather than assumed;
- fresh-runner reuse works for eligible state;
- forced-fresh execution remains available;
- measured work and timing show a useful reduction compared with the control for incremental cases;
- cache/orchestration overhead does not erase the benefit for realistic repository sizes.

No single timing result decides the architecture. Performance is evaluated after correctness and observability, but performance is part of the architecture decision.

## Qualification after PoP

Only after the PoP supports the core principles should the suite expand to cases such as:

- broader module/root POM changes;
- dependency version and plugin changes;
- integration-test/Failsafe behaviour;
- cache corruption/missing-entry fallback;
- Linux/Windows native-cache boundaries;
- multi-run retention/eviction;
- release/tag behaviour;
- larger fixture/real consumer canaries;
- changed-test selection if module-level test reruns are proven to be a material cost.

Those are qualification concerns, not prerequisites for proving the basic principle.

## Production handoff

This repository never becomes production Java tooling. When concept + PoP + required qualification support a decision, `brainboxemb.meta` records the architecture decision and may open a separate production migration with the normal owner chain:

```text
tool.git-project -> tool.java-project -> template.java-project -> real consumers
```

## Reuse after production adoption

After the first migration, this repository stays active as a reusable lab:

```text
migration/production issue
        ↓
minimal reproducible testcase here
        ↓
prove failure on current architecture
        ↓
qualify proposed correction here
        ↓
apply owner fix / migration
        ↓
retain testcase as regression coverage
```

A testcase should only be added here when the fixture/harness can represent the real problem faithfully. Product-specific behaviour that cannot be reduced without losing the failure belongs in the product owner instead.

Historical cases and control baselines should remain runnable. When toolchain or architecture baselines change, add/version the required configuration rather than silently rewriting old evidence semantics.
