# Git build-identity cache invalidation

## Status

**Qualified on the current real-consumer workload.**

Tracking: issue #18.

## Correctness risk

The event-timing application embeds build provenance into its executable JAR:

```text
application.version = Maven project version
build.revision       = git.commit.id.full
build.timestamp      = git.build.time
```

A Maven module can therefore have different correct packaged output for two Git commits even when the tracked source tree is byte-identical.

Source-tree equality by itself is not a sufficient cache-validity boundary for that module.

## Baseline failure

CI-16 first ran without an additional repository-identity cache input.

Evidence:

- experiment source: `e1393ffa3af7542f3bdfdcece8b32d7974a712cd`;
- workflow run: `35336851477`;
- identity job: `105573578952`;
- retained artifact: `java-ci-git-identity-0`, ID `10542413423`;
- artifact digest: `sha256:53aa9015524470a4de67029b12bce220f77e1affc1231148a7ffaedf73e9ba2e`;
- producer revision: `0f9dbc2f5aa0beaec8f63465ada83f2bc2a83709`;
- consumer revision: `fc7454b29d2a2a223004406adc35b20c7cc73b60`;
- producer/consumer Git trees: identical;
- consumer module outputs before Maven: zero;
- consumer native cache sources: `framework=LOCAL`, `app=LOCAL`;
- consumer app JAR embedded revision: **producer** revision `0f9dbc2f...`.

This is a correctness failure: the exact consumer revision produced an artifact claiming a different Git revision.

A generic plugin `dirScan` attempt against `.git/HEAD` was also insufficient and was removed rather than retained as dead configuration.

## Qualified correction

The narrow correction is product/module-owned.

Only the application module, whose packaged output depends on Git identity, declares:

```xml
<properties>
  <maven.build.cache.input.1>../.git/HEAD</maven.build.cache.input.1>
</properties>
```

CI-16 applies this declaration to the isolated real-consumer checkout and repeats the same identity-only commit change.

Qualified evidence:

- experiment source: `907353e70f552339f578df63ab6f2dbf80d0f20f`;
- workflow run: `35337342442` — all 30 jobs green;
- CI-16 job: `105575259391`;
- retained artifact: `java-ci-git-identity-0`, ID `10543484550`;
- artifact digest: `sha256:c480e68fd982ea4abb81bfd766aea6e3940d37d1b0370c823df82190ac972d97`;
- producer revision: `0f9dbc2f5aa0beaec8f63465ada83f2bc2a83709`;
- consumer revision: `fc7454b29d2a2a223004406adc35b20c7cc73b60`;
- producer/consumer Git trees: identical;
- consumer module outputs before Maven: zero;
- consumer native cache sources:
  - `event-timing-framework = LOCAL`;
  - `event-timing-app = BUILD`;
- consumer app JAR embedded revision: `fc7454b29d2a2a223004406adc35b20c7cc73b60`.

The result proves the intended boundary: repository identity invalidates only the module whose output embeds that identity; unrelated reusable module output remains eligible for Maven-native reuse.

## Architecture rule

Repository/build identity is a **product input**, not a reason to partition the complete shared cache by repository SHA.

A Java module must declare every non-source input that materially changes its packaged output. For the current event-timing app, `.git/HEAD` is one such input because the build writes the exact Git revision into the JAR.

Generic Java tooling may provide/document the mechanism, but the consumer owns declaring product-specific build-identity inputs.

## Release implication

This correction makes ordinary cached canonical output source-identity-correct. It does not change the separate release trust boundary.

Exact-tag release qualification remains free to require an ordinary cache-independent Maven producer on a fresh runner. Publication consumes that canonical producer output and never rebuilds merely to publish.

No production repository is modified by this qualification.
