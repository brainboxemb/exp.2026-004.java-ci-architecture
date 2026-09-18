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

## What “incremental” must mean here

Do not equate an unchanged JAR with an incremental build. The PoP evaluates three independent dimensions:

1. **compile/package workset** — which modules, production classes, test classes and packaged outputs were actually rewritten;
2. **test workset** — which test classes/modules actually executed rather than being reused/skipped;
3. **cost** — measured Maven duration and later hosted-runner/wall-clock cost.

A mechanism is only useful when it preserves correctness and reduces real work. A smaller workset with no meaningful time benefit is still evidence, but not automatically a worthwhile production optimisation.

For warm same-runner cases, the harness records the priming duration and measured duration so speed-up can be compared directly. Fresh-runner/cross-run performance gets a separate PoP case because same-worktree reuse does not prove CI cache portability.

## Control baseline

The original plain-Maven baseline is retained as historical control:

- exact main: `1f2dde6629e2acc6f6b86c482939c7752939c2f6`;
- workflow run: `35233519246`;
- fixture: `core -> feature-a/feature-b -> app`;
- cases: CI-01 through CI-05.

Observed control behaviour:

- warm/no-op: module JARs are not rewritten, while all Surefire reports are rewritten;
- docs-only: module JARs are not rewritten, while all Surefire reports are rewritten;
- app-only source change: only the app JAR is reproduced, while all Surefire reports are rewritten;
- core source change: all four module JARs and all Surefire reports are rewritten.

The current PoP fixture adds a second independent app test class and class-level output observation so compilation and test execution can be measured more precisely. Historical evidence remains reproducible by checking out its exact revision.

## Qualified local PoP

The local same-worktree Maven Build Cache principle is qualified on:

- exact main `bc5d1b16da3820b72430611b65969ec7fb0588d0`;
- exact-main run `35250860673`;
- CI-01 through CI-07 against both plain Maven control and Maven Build Cache.

This proves unchanged/docs-only reuse, app-local selectivity, shared-core dependent invalidation, code+test behaviour and test-only behaviour at module level.

The build-model/configuration and cache-disabled slice is qualified by CI-08 through CI-11 on exact PR source `bbef150becf2d60c60d48a9f2f4ea86a90db77c7`, run `35317148073` (discovery + all 22 testcase jobs green).

It proves root/shared versus module-local model invalidation, shared dependency-version invalidation, and correct execution without build-cache reuse. See [`06-model-invalidation-and-cache-disabled.md`](06-model-invalidation-and-cache-disabled.md).

Caching itself remains optional (`none | local | shared`).

The runtime/fresh-runner slice is qualified on exact PR source `03620b5ade2d561361b3a9085ab284ecdba92b44`, run `35319465746` (all 28 jobs green). CI-12 proves runtime JDK namespace separation, CI-13 proves fresh-runner/cross-job reuse with restored artifacts and Surefire evidence, and CI-14 proves explicit transport-miss fallback. See [`07-runtime-and-fresh-runner-cache.md`](07-runtime-and-fresh-runner-cache.md).

The first attempt is also retained as useful failure evidence: default Maven Build Cache reused JDK-8 state under JDK 17, and fresh-runner reuse initially omitted Surefire XML. The corrected design adds a runtime-specific cache namespace and attached Surefire outputs rather than weakening those cases.

## Minimal PoP implementation

Add one target implementation adapter for Maven-native build caching. Do not implement Moon-output-cache and hybrid alternatives merely to create a benchmark tournament.

An alternative implementation is added only when the target mechanism fails a principle or leaves a material design question unresolved.

## PoP questions and cases

### PoP-01 — unchanged warm module state

**Question:** Can Maven-native build caching reuse unchanged module work, including avoiding unnecessary lifecycle/test work, while preserving correct outputs?

Use the identical warm case and retain cache-native evidence plus generic artifact/class/test observations and measured duration.

### PoP-02 — application source change

**Question:** Does an app-only source change rebuild only what Maven semantics require while safely reusing unaffected module state?

Keep the existing code-only case as a technical control.

### PoP-03 — application code + unit-test change

**Question:** For the normal developer case where production code and its unit test change together, which production classes, test classes, test reports and JARs are rebuilt, and how much faster is the measured build than the clean priming build?

This is CI-06. An independent unchanged test class in the same app module makes it possible to see whether Maven executes only the changed test class or the complete module test set.

### PoP-04 — unit-test-only change

**Question:** If one unit test changes and production sources do not, does production compilation/package state remain reusable, which test classes are recompiled, which tests actually execute, and what time is saved?

This is CI-07. It is a first-class PoP case rather than a later edge case because test-only changes are normal Java development work.

### PoP-05 — shared/core change

**Question:** Does changing shared core state invalidate every dependent module that must be rebuilt/tested?

Expected principle: correctness dominates hit rate; no dependent may reuse stale state.

### PoP-06 — build-model/toolchain invalidation

**Question:** Does a relevant POM, plugin/compiler configuration or equivalent build-input change invalidate cached state correctly?

Start with one representative build-model change; broaden only during qualification if the principle works.

### PoP-07 — fresh-runner reuse

**Question:** Can a new GitHub-hosted runner restore valid build state produced by another hosted runner?

This requires explicit cache transport or Maven remote-cache semantics. The testcase records producer/consumer source, runtime, transport and runner evidence.

A same-job warm build does not satisfy this case. CI-13 qualifies producer → separate consumer reuse across hosted jobs, and CI-15 now extends that proof across separate GitHub Actions workflow runs using an exact producer-run/source cache key. See [`08-cross-workflow-cache.md`](08-cross-workflow-cache.md).

### PoP-08 — forced-fresh equivalence

**Question:** Can the same source be built successfully with cache reads disabled so release qualification never depends on cached build state?

The fresh path must execute the required tests and produce the expected canonical artifacts.

## Evidence required per measured case

Retain at least:

- changed fixture inputs;
- production `.class` before/after state;
- test `.class` before/after state;
- module JAR before/after state;
- per-test-class Surefire report before/after state;
- cache-native hit/miss/execute evidence where available;
- priming and measured Maven duration;
- exact source/toolchain/candidate configuration.

Class/report modification time is useful to observe repeated work, while content hashes show whether output content actually changed. Cache-native evidence is required to distinguish true execution from output hydration when restored files receive new timestamps.

## PoP acceptance

The target principle is supported only when:

- correctness assertions pass;
- invalidation matches dependency/build-model semantics;
- structured evidence distinguishes hit/miss/execute/reuse;
- compile and test worksets are no broader than the mechanism requires;
- a fresh runner can reuse eligible state;
- eligible state can survive between separate workflow runs;
- forced-fresh execution remains available;
- measured overhead does not erase the benefit for realistic repository sizes.

No single timing result decides the architecture. Performance is evaluated after correctness and observability, but an incremental-build claim must ultimately show actual work and time reduction rather than only unchanged final artifacts.

## Qualification after PoP

Only after the PoP supports the core principles should the suite expand to cases such as:

- module versus root POM changes;
- dependency version and plugin changes;
- cache corruption/missing-entry fallback;
- Linux/Windows native-cache boundaries;
- longer retention/eviction behaviour if production adoption depends on it;
- release/tag behaviour;
- larger fixture/real consumer canaries.

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
