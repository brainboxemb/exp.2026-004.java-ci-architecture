# Runtime identity and fresh-runner cache qualification

## Status

**Qualified on the four-module fixture after two deliberate design corrections exposed by the PoP.**

Corrected implementation evidence:

- exact PR source `03620b5ade2d561361b3a9085ab284ecdba92b44`;
- workflow run `35319465746` — all 28 jobs green;
- CI-01 through CI-11 retained as regression coverage;
- CI-12 qualifies actual Maven runtime JDK identity change;
- CI-13 qualifies fresh-runner/cross-job Maven build-cache reuse;
- CI-14 qualifies explicit transport-miss fallback.

This slice does **not** claim cache retention across separate workflow runs. It proves transport from one hosted runner/job to another fresh hosted runner/job inside one exact-source workflow execution.

## Initial failures were design evidence

The first implementation run was `35319110444` on exact source `c08e393783626fe78a12143f60d78fc644492733`. Two assumptions failed and were retained as PoP findings rather than hidden by weaker assertions.

### JDK runtime identity was not automatically part of the cache boundary

CI-12 primed the same source under Temurin Java 8 and executed the measured Maven lifecycle under Temurin/Adoptium Java 17.

Without an explicit runtime namespace, Maven Build Cache 1.3.0 reported `LOCAL` for all four modules and reran no tests. The build itself succeeded, but it reused state produced under the previous Maven runtime JDK.

That means the tested default cache key was insufficient as a correctness boundary for this runtime change.

### Fresh-runner module reuse initially lost Surefire evidence

The first CI-13 consumer already proved most of the shared-cache path:

- the GitHub cache transport was an exact hit;
- producer and consumer were different hosted runners;
- the consumer started with zero module `target/` output files;
- Maven restored all four module artifacts and reported `LOCAL` for all four modules.

However, the fresh consumer had zero Surefire XML reports because those reports were not part of Maven Build Cache's default restored output set.

The test therefore failed correctly: skipping test execution through a valid cache hit is only useful to CI if the required test evidence remains available.

## Design correction 1 — runtime-separated Maven cache namespace

The candidate adapter now derives the Maven build-cache location from a runtime fingerprint before invoking the ordinary Maven Wrapper lifecycle.

The fingerprint includes:

- the selected `JAVA_HOME/release` metadata;
- operating system;
- machine architecture;
- SHA-256 identity of `.mvn/wrapper/maven-wrapper.properties`.

The configured cache base remains transportable, but Maven reads and writes underneath a runtime-specific directory:

```text
<cache-base>/runtime-<runtime-fingerprint>/...
```

This leaves Maven responsible for module fingerprints and restores while preventing module lookup from crossing a runtime boundary that the tested Maven Build Cache version did not distinguish itself.

CI-12 remains strict: JDK 8 → JDK 17 must result in `BUILD` for all four modules.

## Design correction 2 — Surefire reports are attached cached outputs

The Maven Build Cache configuration now includes `surefire-reports` as an attached output directory.

That makes test evidence part of the validated module output restored on a fresh cache hit. Tests do not need to execute again merely to recreate reports for CI when Maven has already validated and restored the module result.

## CI-12 — actual Maven runtime JDK change

The corrected run records the real Maven runtimes:

- prime: Maven 3.9.16 under Java `1.8.0_504`;
- measured: Maven 3.9.16 under Java `17.0.20.1`.

The project source and Maven model are unchanged between prime and measured invocations.

Result:

- `core`: BUILD;
- `feature-a`: BUILD;
- `feature-b`: BUILD;
- `app`: BUILD;
- five Surefire reports regenerated;
- measured build successful.

This proves the runtime namespace prevents reuse of module state from the previous JDK runtime.

## CI-13 — fresh hosted-runner reuse

The producer and consumer ran on different GitHub-hosted runners:

- producer runner: `GitHub Actions 1000009415`;
- consumer runner: `GitHub Actions 1000009442`.

Producer evidence:

- zero module output files before build;
- Maven builds all four modules;
- five Surefire reports produced;
- build-cache directory grows from 0 to 12 files;
- measured Maven phase: 5317 ms.

GitHub Actions then transports only that Maven build-cache directory using an exact source/run/case cache key.

Consumer evidence:

- exact transport hit = `true`;
- 12 cache files present before Maven;
- zero module output files present in the fresh fixture before Maven;
- `core`, `feature-a`, `feature-b`, `app`: all `LOCAL` with matched checksums/lifecycle;
- all four required JARs restored;
- all five Surefire XML reports restored;
- measured Maven phase: 2056 ms;
- build successful.

This is real fresh-runner reuse, not same-worktree Maven incrementality.

The approximately 2.6× reduction in the Maven phase is only an observation for this tiny fixture. Candidate preparation and transport costs still exist, so this single result is not yet a production performance conclusion.

## CI-14 — explicit shared-cache miss

The miss case asks GitHub Actions for a deliberately nonexistent transport key.

Result:

- transport hit = `false`;
- zero cache files and zero module output files before Maven;
- all four modules = BUILD;
- all four required JARs produced;
- five Surefire reports produced;
- build successful.

The cache path is therefore an optimization layer: absence of transported state falls back to the ordinary Maven lifecycle rather than becoming a correctness dependency.

## Shared-cache ownership

The qualified split is:

```text
GitHub Actions
  selects hosted runners
  transports an opaque Maven build-cache directory
        ↓
Maven Build Cache adapter
  partitions transport by runtime identity
        ↓
Maven Build Cache
  owns module input checksums
  decides BUILD vs LOCAL
  restores validated module outputs
        ↓
Maven lifecycle
  remains Java build/test authority
```

GitHub Actions does not maintain a Java module graph and does not decide whether a module cache entry is valid.

## Conclusion

The target architecture survives this qualification, but with two now-mandatory constraints:

1. Maven build-output cache storage must be partitioned by relevant runtime identity before module lookup.
2. Required CI evidence such as Surefire XML must be included in the cached/restored output contract when test execution can be skipped.

The `shared` mode is now technically credible for fresh hosted runners using GitHub cache transport of Maven's local cache. It remains optional; `none` stays a first-class safe mode.

## Remaining qualification

Before a production rollout decision, the useful remaining work is narrower:

1. repeated performance measurements on representative workloads/repository sizes;
2. decide whether shared cache must survive and be relied upon across separate workflow runs/retention windows, and qualify that only if needed;
3. release/canonical-artifact policy, including whether release qualification requires a separate empty-output `clean` build;
4. failure behaviour beyond a simple miss, such as unavailable/corrupt transported state, when practical;
5. one real-consumer canary before broad rollout if meta decides caching is worth adopting.

No production migration is activated by this qualification.
