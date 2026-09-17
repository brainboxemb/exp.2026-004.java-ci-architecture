# Agent guidance

This repository is experimental evidence, not production Java tooling.

## Start here

Read, in order:

1. `README.md`;
2. `docs/00-research-question.md`;
3. `docs/01-test-model.md`;
4. `tests/README.md`;
5. the active GitHub issue/PR.

For cross-project status and final architecture decisions, `brainboxemb/brainboxemb.meta` remains the coordination authority.

## Preserve the experiment boundary

Keep fixtures, testcase definitions, candidate implementations, harness code and experiment results here. Do not change `tool.java-project`, templates or product repositories to make an experiment pass.

A candidate may model existing production behaviour, but the experiment must not silently become the production owner.

## Testcase rules

- Testcases are declarative TOML under `tests/cases/`.
- One testcase answers one concrete CI/invalidation question.
- Candidate-specific shell/probing logic must not be copied into individual testcases.
- Assertions belong in the generic harness or the candidate adapter when they are genuinely candidate-specific.
- Prefer standard tool output, filesystem artifacts and structured reports over brittle free-form log greps.
- Retain enough evidence to distinguish execution, reuse/hydration, skip and failure.

## Candidate rules

Candidates must implement the same harness contract. Do not weaken expected behaviour for one candidate simply because its implementation cannot currently expose evidence.

Correctness is a gate. Performance comparisons are meaningful only after a candidate passes the relevant correctness cases.

## CI

GitHub Actions owns runner/job/matrix orchestration. The local composite Action executes one testcase/candidate pair through the generic harness.

A test that depends on real GitHub event semantics may use a dedicated end-to-end workflow later, but it must still have a declared expected result and automated assertions.
