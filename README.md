# Java CI architecture experiment

Controlled experiment for reproducible Java CI architecture, incremental builds, caching, affected execution and automated qualification test cases.

This repository is the implementation owner for the active experiment coordinated from [`brainboxemb/brainboxemb.meta`](https://github.com/brainboxemb/brainboxemb.meta), tracking issue [`brainboxemb.meta#69`](https://github.com/brainboxemb/brainboxemb.meta/issues/69).

## Goal

Determine which generic Java/software CI architecture gives correct, reproducible and understandable incremental execution while avoiding unnecessary builds and runner usage.

The experiment compares candidate implementations against the same deterministic multi-module Java fixture and the same declarative test cases. Production tooling is not changed from this repository.

## Principles

- test cases are explicit, declarative and reviewable;
- one generic harness executes cases instead of case-specific probing scripts;
- GitHub Actions discovers test cases and orchestrates the matrix;
- every run produces machine-readable `result.json` plus a readable summary;
- correctness and invalidation behaviour are evaluated before performance;
- candidates are compared against the same workload and assertions;
- conclusions are recorded back in `brainboxemb.meta` before production rollout.

## Repository layout

```text
fixture/       deterministic multi-module Maven workload
tests/cases/   declarative TOML test cases
harness/       generic discovery, execution and assertion code
candidates/    candidate CI/build-cache architectures
results/       retained experiment conclusions, not ad-hoc CI logs
docs/          research question, testcase contract and evaluation rules
.github/       generic testcase Action and CI orchestration
```

## Current phase

Issue [#1](https://github.com/brainboxemb/exp.2026-004.java-ci-architecture/issues/1) bootstraps the testcase contract, fixture and current Maven baseline. Maven Build Cache, Moon output caching and hybrid candidates are deliberately later steps so the test oracle exists before candidate-specific implementation begins.
