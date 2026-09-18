# Build-model invalidation and cache-disabled qualification

## Status

**Qualified on the four-module fixture.**

Target mechanism: Apache Maven Build Cache Extension `1.3.0`.

Qualified exact PR source:

- `bbef150becf2d60c60d48a9f2f4ea86a90db77c7`
- workflow run `35317148073`
- discovery + all 22 testcase matrix jobs green
- CI-01 through CI-07 retained as regression coverage
- CI-08 through CI-11 qualify build-model/configuration invalidation and cache-disabled execution

This qualification builds on the local same-worktree PoP in [`05-local-maven-build-cache-pop.md`](05-local-maven-build-cache-pop.md).

## Cache adoption model

Build-output caching remains an optional optimisation rather than a Java correctness dependency:

```text
none
  ordinary Maven lifecycle without build-output cache reuse

local
  local Maven Build Cache reuse

shared
  cross-run/shared reuse after that transport has been qualified
```

`none` remains the safe initial/default mode. Cache-disabled qualification is orthogonal to these project modes and uses the same Maven lifecycle rather than a second build implementation.

## Qualified cases

| Case | Change / execution mode | Core | Feature A | Feature B | App | Tests regenerated |
| --- | --- | --- | --- | --- | --- | ---: |
| CI-08 | root POM / shared Surefire configuration | BUILD | BUILD | BUILD | BUILD | 5 |
| CI-09 | app-local POM / Surefire configuration | LOCAL | LOCAL | LOCAL | BUILD | 2 |
| CI-10 | shared managed JUnit version | BUILD | BUILD | BUILD | BUILD | 5 |
| CI-11 | unchanged warm source, cache reads/saves disabled for measured invocation | BUILD | BUILD | BUILD | BUILD | 5 |

The Maven Build Cache expectations are declarative in the testcase definitions and are checked against normalized native cache-report evidence.

## Root build-model invalidation

CI-08 changes Surefire configuration in the root POM. That configuration contributes to the effective build model for every module.

All four modules are therefore invalidated and all five test-class reports are regenerated.

This is the conservative/correct boundary for shared build configuration: a root build-model change must not allow a child module to reuse state calculated from the previous effective model.

## Module-local build-model invalidation

CI-09 makes the equivalent Surefire configuration change only in the `app` POM.

The native cache evidence shows:

- `core`: LOCAL;
- `feature-a`: LOCAL;
- `feature-b`: LOCAL;
- `app`: BUILD.

Only the two app test classes rerun.

This demonstrates that build-model invalidation is not automatically repository-wide: a module-local effective-model change can stay within that module when Maven dependency/build semantics do not require upstream invalidation.

## Shared dependency invalidation

CI-10 changes the managed JUnit version used by all four modules.

All modules rebuild and all five test classes rerun. This proves that a dependency input shared through the root model contributes to module cache identity and prevents reuse of outputs/test state produced with the previous dependency version.

This testcase covers dependency-version invalidation, not every possible repository/plugin-resolution edge case. Later production onboarding still needs to validate project-specific plugins and inputs.

## Cache-disabled execution

CI-11 primes a normal warm Maven Build Cache build, then invokes the same Maven `verify` lifecycle with cache reads and cache saves disabled for the measured invocation.

The measured invocation:

- completes successfully;
- produces all required artifacts;
- regenerates all five Surefire reports;
- uses no LOCAL or REMOTE build-cache result;
- preserves the expected production payload because source inputs did not change.

Maven Build Cache 1.3.0 represents the native no-cache source state as the literal report value `null`. The harness retains that value as `source_raw` and normalizes it to `BUILD` for the cross-candidate workset contract. This keeps the raw Maven evidence while giving testcases one stable semantic value for executed module work.

### Cache-disabled is not the same as `mvn clean`

This result also establishes an important distinction.

Disabling Maven Build Cache reads forces the build to proceed without build-cache reuse, but it does **not** remove the existing `target/` tree. Maven and its plugins may still apply their normal same-worktree up-to-date/incremental behaviour. In CI-11 the tests rerun, while unchanged compile/package outputs do not necessarily receive new bytes or timestamps.

Therefore:

- **cache-disabled/fresh with respect to Maven Build Cache** means no build-cache result is consumed;
- **clean from empty build outputs** is a stronger and separate execution condition.

If release qualification later requires proof from an empty `target/` tree, add and qualify that as a separate policy rather than silently treating cache-disabled and `clean` as synonyms.

## Conclusion

The second correctness slice supports the target architecture:

- root/shared build-model changes invalidate broadly when their effective inputs change;
- module-local build-model changes can remain module-local;
- shared dependency-version changes invalidate every module that resolves the changed dependency;
- correctness does not depend on Maven Build Cache reuse;
- one Maven lifecycle remains authoritative in cached and cache-disabled modes;
- caching can remain optional and project-configurable.

No production migration is activated by this result.

## Remaining qualification

The next slice should move beyond the same runner/worktree:

1. actual toolchain/input invalidation where the cache can observe the changed toolchain identity;
2. fresh-runner / cross-run cache transport and hydration;
3. missing/unavailable shared-cache fallback;
4. repeated performance measurements on representative workloads;
5. release/canonical-artifact implications, including whether an empty-output clean qualification is required for releases.

Only after those questions are answered should meta decide whether a production rollout is worthwhile and for which project/cache modes.
