# Java CI architecture Proof of Principle

Reusable, design-first Proof of Principle (PoP) and qualification repository for Java CI architecture, incremental builds, caching, affected execution and automated test cases.

This repository is the implementation/evidence owner for the active cross-project track coordinated from [`brainboxemb/brainboxemb.meta`](https://github.com/brainboxemb/brainboxemb.meta), tracking issue [`brainboxemb.meta#69`](https://github.com/brainboxemb/brainboxemb.meta/issues/69).

## Role

The architecture is **designed first**. This repository does not discover the architecture by running an open-ended tournament of tools.

The initial adoption sequence is:

```text
Concept / target architecture
        ↓
Proof of Principle
        ↓
Qualification
        ↓
Production migration
```

The repository does **not** disappear after that migration. It remains the reusable qualification/regression laboratory for the Java CI architecture:

```text
new CI problem or design change
        ↓
reproduce as declarative testcase here
        ↓
qualify the proposed correction/change
        ↓
production migration or owner fix
        ↓
retain testcase as regression coverage
```

This means a problem discovered during a later migration should preferably become a reproducible testcase here before production logic is changed, when the problem can be represented faithfully by the fixture/harness.

## Current target concept

The target responsibility split is:

- GitHub Actions: event, runner, job and artifact orchestration;
- Moon/generic repository layer: affected/capability selection and platform policy;
- Maven: Java reactor, lifecycle, build and test authority;
- Maven-native build cache: optional module-level optimisation, with intended modes `none | local | shared`;
- publication: reuse canonical prepared output, never rebuild merely to publish.

See [`docs/02-target-architecture.md`](docs/02-target-architecture.md).

## Principles

- test cases are explicit, declarative, reviewable and repeatable;
- one generic harness executes cases instead of case-specific probing scripts;
- GitHub Actions discovers and orchestrates the cases;
- every run produces machine-readable `result.json` plus a readable summary;
- correctness and invalidation behaviour are gates before performance;
- design decisions are separated from runtime assumptions that require PoP evidence;
- alternative mechanisms are added when the target design fails or leaves a material question unresolved, not merely for a benchmark tournament;
- proven failure cases are retained as regression tests;
- conclusions and production decisions are recorded back in `brainboxemb.meta` before rollout.

## Repository layout

```text
fixture/       deterministic multi-module Maven workload
tests/cases/   declarative TOML qualification/regression cases
harness/       generic discovery, execution and assertion code
candidates/    target/adaptor implementations needed by a PoP or comparison
results/       retained conclusions/evidence summaries, not ad-hoc CI logs
docs/          target architecture, PoP plan and testcase contract
.github/       generic testcase Action and CI orchestration
```

## Current phase

Issue [#1](https://github.com/brainboxemb/exp.2026-004.java-ci-architecture/issues/1) established the reusable fixture, testcase contract, harness and plain-Maven control baseline.

Issue [#2](https://github.com/brainboxemb/exp.2026-004.java-ci-architecture/issues/2) owns the target architecture and PoP/qualification work.

The **local same-worktree Maven Build Cache PoP is now qualified**: the seven declarative cases prove module-level cache reuse, app-only selectivity, shared-core invalidation, code+test behaviour and test-only behaviour against native Maven cache evidence. See [`docs/05-local-maven-build-cache-pop.md`](docs/05-local-maven-build-cache-pop.md).

The **build-model/configuration and cache-disabled qualification is now green**: root/shared model changes invalidate broadly, app-local model changes remain app-local, shared dependency changes invalidate all consuming modules, and the same Maven lifecycle remains correct with build-cache reads disabled. See [`docs/06-model-invalidation-and-cache-disabled.md`](docs/06-model-invalidation-and-cache-disabled.md).

The **runtime-identity and fresh-runner qualification is now green**: the cache is partitioned by Maven runtime JDK/OS/arch/wrapper identity, a JDK 8 → 17 switch rebuilds instead of reusing stale state, a separate hosted runner can restore Maven's transported local build cache, Surefire reports are retained as attached outputs, and an explicit transport miss falls back to a normal build. See [`docs/07-runtime-and-fresh-runner-cache.md`](docs/07-runtime-and-fresh-runner-cache.md).

The **cross-workflow persistence qualification is now green**: CI-15 proves that a dedicated producer workflow can save Maven build-cache state and a later, separate `workflow_run` consumer can restore that exact state for the same source/runtime identity, start with zero module outputs, reuse all four modules as Maven-native `LOCAL`, and recover all four JARs plus five Surefire reports. Exact main `681ce7b9d56973b5540cb314c8e45e25618915a0`, producer run `35323272710`, consumer run `35323361468`. See [`docs/08-cross-workflow-cache.md`](docs/08-cross-workflow-cache.md).

The representative **end-to-end production-value qualification is now complete** (issue #14). Two independent exact-main benchmark pairs provide six matched samples against the exact current event-timing framework workload. Shared caching makes every later consumer run faster, with paired latency savings of `16, 14, 4, 3, 9, 2 s` (median 6.5 s / 28.8%). Total producer+consumer hosted compute is not consistently lower: paired savings are `10, 10, -1, 0, 9, -2 s`. See [`docs/09-production-value.md`](docs/09-production-value.md).

The **Git build-identity invalidation qualification is now green** (issue #18). CI-16 first reproduced the real correctness defect: with an identical source tree under a different Git commit, Maven restored both product modules as `LOCAL` and the app JAR retained the stale producer revision. The qualified correction adds `../.git/HEAD` as a Maven Build Cache input only to the app module. On run `35337342442`, `framework` remains `LOCAL`, `app` becomes `BUILD`, and the app JAR embeds the exact consumer revision. See [`docs/10-git-build-identity.md`](docs/10-git-build-identity.md).

The active question is now the final **release/canonical-artifact policy**. No production rollout is activated automatically.
