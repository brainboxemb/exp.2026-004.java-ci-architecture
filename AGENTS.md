# Agent guidance

This repository is reusable Java CI Proof-of-Principle (PoP), qualification and regression evidence, not production Java tooling.

## Start here

Read, in order:

1. `README.md`;
2. `docs/02-target-architecture.md`;
3. `docs/03-pop-plan.md`;
4. `docs/01-test-model.md`;
5. the active GitHub issue/PR.

Use `docs/00-research-question.md` for the broader problem context. For cross-project status and final architecture/rollout decisions, `brainboxemb/brainboxemb.meta` remains the coordination authority.

## Design-first rule

Do not use this repository to discover architecture by blindly implementing every possible tool combination.

The normal sequence is:

```text
concept -> PoP -> qualification -> production migration
```

Start from the target architecture. Use PoP cases for assumptions that require runtime evidence. Add an alternative implementation only when the target design fails, a material uncertainty remains, or comparison is required to resolve a concrete design decision.

A PoP failure is valid evidence. Correct the concept or implementation; do not weaken a testcase merely to make a candidate pass.

## The PoP is permanent

Do not treat the repository as disposable after initial production adoption.

When a later migration or owner repository exposes a Java CI problem that can be faithfully reproduced here:

1. reduce it to a declarative testcase/fixture change here;
2. prove the failure;
3. qualify the proposed correction here;
4. change the production owner through its normal issue/PR/migration path;
5. retain the testcase as regression coverage.

Historical baseline and regression cases therefore remain useful after the original PoP has completed.

## Preserve the ownership boundary

Keep fixtures, testcase definitions, PoP adapters, harness code and qualification results here. Do not change `tool.java-project`, templates or product repositories to make a PoP pass.

This repository can model production behaviour but must not silently become the production implementation owner.

## Testcase rules

- Testcases are declarative TOML under `tests/cases/`.
- One testcase answers one concrete CI/invalidation question.
- Candidate/adapter-specific shell/probing logic must not be copied into individual testcases.
- Assertions belong in the generic harness or adapter only when genuinely implementation-specific.
- Prefer standard tool output, filesystem artifacts and structured reports over brittle free-form log greps.
- Retain enough evidence to distinguish execution, reuse/hydration, skip, invalidation and failure.
- A newly discovered production defect should preferably become a failing testcase before the production fix when it can be reproduced accurately here.

## Adapter rules

Adapters must implement the same harness contract. Do not weaken expected behaviour because one implementation cannot expose sufficient evidence.

Correctness is a gate. Performance comparisons are meaningful only after the relevant correctness cases pass.

## CI

GitHub Actions owns runner/job/matrix orchestration. The local composite Action executes one testcase/adapter pair through the generic harness.

A test that depends on real GitHub event semantics may use a dedicated end-to-end workflow, but it must still have a declared expected result and automated assertions.
