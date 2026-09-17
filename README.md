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
- Maven-native build cache: target PoP mechanism for module-level incremental/cache semantics;
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

Issue [#2](https://github.com/brainboxemb/exp.2026-004.java-ci-architecture/issues/2) now defines the target architecture and minimal PoP. The next implementation work should qualify the target Maven-native build-cache mechanism against the existing control before broadening the suite.
