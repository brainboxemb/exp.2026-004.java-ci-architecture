# Cross-workflow Maven build-cache qualification

## Status

**Qualified on exact experiment main.**

Exact source:

```text
681ce7b9d56973b5540cb314c8e45e25618915a0
```

Producer workflow:

- run `35323272710`;
- workflow `Java CI shared-cache producer`;
- event `push`;
- result: success;
- evidence artifact `java-ci-cross-workflow-producer-0`;
- artifact ID `10537549340`;
- artifact digest `sha256:91f5d72fb9bbb0949d0360af3ff2e335fdd4cbf6689621fcfec410becfaeaa0e`.

Consumer workflow:

- run `35323361468`;
- workflow `Java CI shared-cache consumer`;
- event `workflow_run`;
- result: success;
- evidence artifact `java-ci-cross-workflow-consumer-0`;
- artifact ID `10537579540`;
- artifact digest `sha256:f3a2cd6354a3440ea3f9653d3845e5929f92f6770bc79bf8996cf39c8151b4e5`.

The producer and consumer are distinct GitHub Actions workflow runs and both use the same exact protected-main source revision.

## CI-15 question

CI-15 asks:

> Can a later GitHub Actions workflow run restore and reuse Maven module state produced by an earlier workflow run for the exact same source and runtime identity?

The answer for the current four-module fixture is **yes**.

## Producer evidence

The producer starts from a fresh fixture:

- zero module output files before Maven;
- Maven builds `core`, `feature-a`, `feature-b` and `app`;
- native Maven Build Cache source is `BUILD` for all four modules;
- all four required JARs are produced;
- all five Surefire XML reports are produced;
- Maven build-cache state grows from 0 to 12 files;
- measured Maven phase: 5318 ms;
- candidate preparation: 5276 ms.

GitHub Actions then saves only Maven's local build-cache directory under the exact key:

```text
java-ci-cross-workflow-681ce7b9d56973b5540cb314c8e45e25618915a0-35323272710-0
```

## Consumer evidence

The later consumer run restores that exact key on a new hosted runner.

Self-verifying result:

- transport hit = `true`;
- producer run = `35323272710`;
- consumer run = `35323361468`;
- producer and consumer run IDs are different;
- producer source = consumer source = exact `681ce7b9...`;
- 12 cache files are present before Maven;
- zero module output files exist before Maven;
- `core` = `LOCAL`;
- `feature-a` = `LOCAL`;
- `feature-b` = `LOCAL`;
- `app` = `LOCAL`;
- all four required JARs are restored;
- all five Surefire XML reports are restored;
- measured Maven phase: 2631 ms;
- candidate preparation: 4765 ms;
- all CI-15 assertions pass.

The retained Maven cache report also shows matching checksums/lifecycle for all four restored modules.

## What this proves

The `shared` Maven-cache design now proves all of these separately:

1. same-worktree/module reuse;
2. runtime/toolchain separation;
3. fresh-runner reuse across different jobs;
4. explicit transport-miss fallback;
5. persistence and reuse across **different workflow runs**.

GitHub Actions remains opaque transport/orchestration. Maven Build Cache remains responsible for module checksums, validity and restored outputs.

The qualified candidate capability can therefore be recorded as:

```text
cross_workflow_output_cache = true
```

## What this does not prove

This result does **not** yet show that shared caching is economically worthwhile for production repositories.

The tiny fixture shows:

- producer Maven phase: 5318 ms;
- consumer Maven phase: 2631 ms.

But the same evidence also records substantial preparation, runner, checkout, Java setup and cache transport overhead. The next qualification must therefore measure **end-to-end wall-clock and hosted-runner cost** on a representative workload rather than comparing Maven phase time alone.

This result also does not decide release/canonical-artifact policy.

## Next qualification

The blocking production-value question is now:

> Does shared Maven caching reduce total CI latency and/or hosted-runner consumption enough on representative Java work to justify its added transport/storage mechanism?

That measurement should retain at least:

- complete workflow wall-clock;
- hosted-runner seconds;
- checkout/setup/preparation time;
- cache restore/save time and bytes;
- Maven time;
- correctness/workset evidence;
- control path without shared cache;
- repeated samples to separate structural savings from runner variance.

No production migration is activated by CI-15 alone.
