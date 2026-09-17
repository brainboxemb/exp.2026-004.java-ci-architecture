# Local Maven Build Cache PoP

## Status

**PoP principle proven for local same-worktree module reuse. Further qualification remains required before production migration.**

Target mechanism: Apache Maven Build Cache Extension `1.3.0`.

Qualified exact PR source:

- `00eb1ee66b65c2ae2d890ed516ea4de170f3607c`
- workflow run `35250370997`
- discovery + all 14 matrix testcase jobs green
- seven plain-Maven control jobs + seven Maven Build Cache jobs

The final run is self-verifying: testcase TOML declares candidate-specific expected worksets and native cache sources, and the generic harness fails the job when those expectations are not met.

## Evidence model

The PoP does not infer rebuilds from timestamps or free-form Maven log text.

For the Maven Build Cache candidate it retains the extension's native `cache-report*.xml`, normalizes the per-module cache source, and combines that with:

- class-file content/mtime observations;
- Surefire report content/mtime observations;
- complete JAR byte hashes;
- semantic JAR payload hashes that ignore ZIP metadata;
- Maven invocation timing;
- exact testcase/candidate/source/toolchain provenance.

See [`04-workset-metrics.md`](04-workset-metrics.md).

## Qualified local behaviour

| Case | Core | Feature A | Feature B | App | Test reports regenerated | Production JAR payload changed |
| --- | --- | --- | --- | --- | ---: | ---: |
| CI-01 cold clean | BUILD | BUILD | BUILD | BUILD | 5 | 4 |
| CI-02 identical warm | LOCAL | LOCAL | LOCAL | LOCAL | 0 | 0 |
| CI-03 docs-only | LOCAL | LOCAL | LOCAL | LOCAL | 0 | 0 |
| CI-04 app code-only | LOCAL | LOCAL | LOCAL | BUILD | 2 | 1 |
| CI-05 shared core change | BUILD | BUILD | BUILD | BUILD | 5 | 1 |
| CI-06 app code + unit test | LOCAL | LOCAL | LOCAL | BUILD | 2 | 1 |
| CI-07 app unit-test-only | LOCAL | LOCAL | LOCAL | BUILD | 2 | 0 |

These are declarative assertions in the testcase definitions, not a hand-written interpretation applied after the run.

## Conclusions

### Unchanged and documentation-only work

An unchanged warm invocation and a documentation-only change reuse all four Maven modules from the local cache. No Surefire reports are regenerated, so the reactor test suite is not rerun merely because `verify` was invoked.

This is materially different from the plain-Maven control, where a warm/no-op or documentation-only `verify` reruns the reactor tests.

### Application-only production change

An application production-code change rebuilds only `app`. `core`, `feature-a` and `feature-b` are local cache hits.

Only the two app test classes rerun. Tests in the three unaffected modules are reused rather than rerun.

### Production code plus unit-test change

Changing app production code together with its unit test has the same module-level invalidation boundary: only `app` rebuilds, and both app test classes rerun.

The extension therefore gives useful **module-level** selectivity. It does not by itself provide changed-test-class impact analysis inside an invalidated module: changing one app test does not mean only that one app test runs.

### Unit-test-only change

A unit-test-only change invalidates the `app` module while the other three modules remain local hits. Both app test classes rerun.

The production JAR payload remains unchanged. The JAR archive bytes can nevertheless differ because the packaging lifecycle reruns and ZIP/JAR metadata can change. The PoP deliberately records both archive-byte identity and semantic archive-payload identity so this is not mistaken for a production-code change.

### Shared core change

Changing the shared `core` source invalidates the required dependent graph. All four modules rebuild and all five test classes rerun.

Only the core production payload changes in this fixture; the dependent JARs can be recreated bytewise differently while retaining the same payload. This correctly exposes rebuild cost separately from semantic output change.

## Timing observations

Timing is part of the incremental-build question, but a single GitHub-hosted runner sample is not a stable performance claim.

An earlier fully instrumented run (`35249617550`, source `42daedaddcc74a8fec04ccd85cf5614c15a93a42`) produced these illustrative measured Maven invocation samples:

| Case | Plain Maven | Maven Build Cache | Sample relationship |
| --- | ---: | ---: | ---: |
| CI-01 cold clean | 5009 ms | 10058 ms | cache slower cold |
| CI-02 identical warm | 3637 ms | 1664 ms | about 2.19x faster |
| CI-03 docs-only | 3450 ms | 2479 ms | about 1.39x faster |
| CI-04 app code-only | 3818 ms | 3343 ms | about 1.14x faster |
| CI-05 core change | 4013 ms | 3042 ms | about 1.32x faster in this sample |
| CI-06 app code + test | 3404 ms | 2767 ms | about 1.23x faster |
| CI-07 test-only | 3698 ms | 3819 ms | slightly slower in this sample |

Do not use those ratios as production performance guarantees. They show that reducing the workset can provide useful savings, while cache overhead can also dominate small or cold workloads. Performance qualification must repeat equivalent cases and report a distribution rather than selecting one favourable run.

## What this PoP proves

The current target concept is viable at the local Maven-reactor level:

- Maven remains lifecycle/build/test authority;
- native Maven caching can reuse complete unaffected modules;
- unchanged/docs-only builds can avoid Java test execution entirely;
- an app-local change does not require unrelated modules/tests to rerun;
- a shared dependency change invalidates the required downstream graph;
- test-only changes invalidate test execution without changing the production payload;
- native structured cache evidence is available and can be retained without log probing.

This is enough to continue qualifying the target design. It is **not** enough to start production migration yet.

## Remaining qualification

The next qualification slice should cover, in this order:

1. representative root/module POM, dependency, compiler/plugin and toolchain invalidation;
2. forced-fresh/cache-bypass execution to prove correctness does not depend on cached state;
3. fresh-runner / cross-run cache transport and hydration;
4. missing/corrupt cache fallback where practical;
5. repeated timing measurements for the important incremental cases;
6. release/canonical-build implications, including whether reproducible-JAR settings are required when byte identity matters.

Only after these principles are qualified should `brainboxemb.meta` decide whether to activate a production migration through the normal owner chain.
