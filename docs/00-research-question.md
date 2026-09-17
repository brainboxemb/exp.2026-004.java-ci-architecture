# Problem statement and PoP questions

## Problem

The Java/software CI architecture should provide correct, reproducible and understandable incremental execution while avoiding unnecessary builds, tests and hosted-runner usage.

This repository does not answer that problem by blindly comparing every possible architecture. The target concept is designed first in [`02-target-architecture.md`](02-target-architecture.md); the PoP then checks the runtime-sensitive assumptions that need empirical evidence.

## Concerns that must remain distinct

1. **Repository affected selection** — should Java work start at all?
2. **Module/task invalidation** — which parts of a multi-module build are invalidated by a change?
3. **Build-output reuse** — can previously produced outputs be safely reused or hydrated?
4. **Qualification policy** — which boundaries deliberately require fresh/exact execution, especially releases and platform qualification?

Dependency-download caching is measured separately from build-output caching. A warm Maven repository is not evidence of an incremental build.

## Existing architectural baseline

Migration 006 already established:

- GitHub Actions owns runner/job orchestration;
- Moon/generic tooling provides repository/capability affected selection;
- Maven remains Java build/test authority;
- Windows qualification is event-sensitive rather than an unconditional matrix;
- canonical build output is prepared once and publication does not rebuild Maven.

The new concept extends this with module-level build-output reuse while preserving those boundaries.

## Target mechanism under PoP

The target mechanism to qualify first is Maven-native build caching, because module-level build/test reuse belongs naturally inside Maven's project graph and lifecycle if the mechanism proves correct, observable and portable in CI.

Moon task/output caching remains a possible alternative or complementary mechanism when a concrete PoP result shows that the target mechanism cannot satisfy a requirement. It is not implemented solely to create a comparison tournament.

## PoP questions

The first PoP must establish whether the target mechanism can:

- reuse unchanged module work without silently skipping required tests/plugins;
- invalidate affected dependents correctly after shared/core changes;
- avoid unnecessary upstream/independent work for application-only changes;
- invalidate cache state for relevant build-model/toolchain inputs;
- hydrate eligible state on a fresh GitHub-hosted runner;
- expose reliable execute/reuse/miss evidence;
- retain a cache-disabled forced-fresh path for correctness-sensitive qualification;
- deliver enough benefit to justify its complexity/overhead.

See [`03-pop-plan.md`](03-pop-plan.md) for the minimal testcase set.

## Permanent role

After initial adoption, this repository remains the reusable PoP/qualification/regression environment for the Java CI architecture. New migration or production defects should be reduced to repeatable cases here when practical, and successful fixes should leave those cases behind as regression coverage.

## Decision criteria

A production recommendation must explain:

- correctness and stale-output risks;
- affected/invalidation precision;
- local and fresh-runner cache behaviour;
- test execution semantics;
- artifact reproducibility;
- Linux/Windows boundaries;
- release behaviour;
- observable evidence for execute/reuse/skip;
- complexity and maintenance cost;
- wall time and hosted-runner cost.

A faster mechanism that cannot prove correct invalidation is not acceptable.
