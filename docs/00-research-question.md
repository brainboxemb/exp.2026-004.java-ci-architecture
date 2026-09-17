# Research question

## Primary question

What generic Java/software CI architecture gives correct, reproducible and understandable incremental execution while avoiding unnecessary builds, tests and hosted-runner usage?

## Boundaries

The experiment separates four concerns that are often conflated:

1. **Repository affected selection** — should Java work start at all?
2. **Module/task invalidation** — which parts of a multi-module build are invalidated by a change?
3. **Build-output reuse** — can previously produced outputs be safely reused or hydrated?
4. **Qualification policy** — which boundaries deliberately require fresh/exact execution, especially releases and platform qualification?

Dependency-download caching is measured separately from build-output caching. A warm Maven repository is not evidence of an incremental build.

## Baseline

The production model established before this experiment already performs repository-level affected selection and selective Windows qualification, while Maven remains Java build/test authority. When Java is selected, canonical execution still runs Maven `verify`; Moon tasks in consumers are impact declarations rather than cached Java build tasks.

The experiment does not assume this division remains optimal at module level.

## Candidate families

The experiment will compare at least:

- current/plain Maven build behaviour as a control;
- Apache Maven Build Cache Extension;
- Moon task/output caching;
- a hybrid where Moon owns repository/task orchestration and Maven owns module-level build/cache semantics.

Candidates may be refined as evidence develops. The testcase contract must remain independent of the preferred candidate.

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

A faster candidate that cannot prove correct invalidation is not a valid winner.
