# Representative end-to-end production-value qualification

## Status

**Qualified — latency value positive; hosted-compute saving not qualified.**

Cross-workflow cache correctness is already qualified. This slice answers a different question: whether the extra shared-cache mechanism is worthwhile at the scale of a current real Java consumer.

Tracking: issue #14.

## Qualification evidence

Two independent exact-main benchmark pairs were retained.

### Run set A

- experiment main: `2d9ac9af9006725576009b5c453590800a1a7337`;
- producer workflow: `35335319664`;
- separate consumer workflow: `35335436917`;
- aggregate artifact: `java-ci-production-value-aggregate`, ID `10543361402`;
- aggregate digest: `sha256:b0929549ff82473df00f03a88210265e79249518d4d0632dd47e2bcfaec2ffa7`.

Paired later-run savings: `16 / 14 / 4 s`.
Paired two-run compute savings: `10 / 10 / -1 s`.

### Run set B

- experiment main: `d47d10ae0cb2be7828310331a8fed8121e10d0fd`;
- producer workflow: `35335827417`;
- separate consumer workflow: `35335932166`;
- aggregate artifact: `java-ci-production-value-aggregate`, ID `10542752885`;
- aggregate digest: `sha256:ad911173f29df841d3c3a41fb6552a7b5812bab638d0c14dc67405e8e70604c5`.

Paired later-run savings: `3 / 9 / 2 s`.
Paired two-run compute savings: `0 / 9 / -2 s`.

Run set B uses result/aggregate schema v2 and additionally retains cache byte counts plus exact cache save/restore step duration.

## Workload

The benchmark uses a read-only exact-source checkout of:

```text
brainboxemb/2026-010-02.java.event-timing-framework
0f9dbc2f5aa0beaec8f63465ada83f2bc2a83709
```

That revision is both current `main` and the source retained in `prod/bld`.

It contains:

- Maven parent plus `framework` and `app` modules;
- 21 Java source/test files;
- 22 tests in 6 Surefire suites;
- compiler, Surefire, shade and Git build-identity plugins;
- the same Java 8 / Maven Wrapper baseline used by current production.

The workload is declared in `workloads/event-timing-framework.toml`; product source is not copied into this repository.

## Existing production context

The same exact product source already retains production timing evidence from run `35211527836`:

- Maven reported total: 18.214 s;
- Linux canonical job: 41 s;
- protected-main path to timing capture: 67 s wall clock;
- 60 hosted-runner seconds to timing capture.

This matters because Maven time is only part of actual CI latency.

## Compared paths

Only two modes are compared:

```text
control / none
  ordinary Maven Wrapper verify

shared
  qualified Maven Build Cache adapter
  + runtime-separated cache namespace
  + cached Surefire outputs
  + GitHub cache transport
```

Moon output caching or other mechanisms are not added merely to create more benchmark candidates.

A dedicated dependency-prime job populates the normal Maven dependency cache before measured jobs. Both measured modes then start on fresh hosted runners with the same dependency-cache basis. The shared path still pays its own extension preparation and output-cache save/restore costs.

## Repeated matched design

Each exact-main benchmark pair executes three matched samples. Two independent run sets were retained, giving six matched samples for the production-value conclusion.

Producer workflow:

```text
dependency prime
     ↓
3 × control producer-equivalent
3 × shared producer + cache save
```

Later consumer workflow, triggered through `workflow_run`:

```text
3 × control consumer
3 × shared cache restore + consumer
     ↓
aggregate
```

Every measured build begins with zero module `target/` outputs. Both modes must produce the two expected product JARs and six Surefire XML reports. Shared producers must report Maven-native `BUILD`; shared consumers must report `LOCAL` for both product modules and prove an exact transport hit from the separate producer workflow.

## Measurements

Each result retains:

- exact experiment and workload revisions;
- mode, phase and sample;
- runner/workflow provenance;
- fresh-output assertion;
- wrapper-check duration;
- shared candidate preparation duration;
- measured Maven duration and Maven-reported total;
- cache file count and transport state;
- Maven native cache report for shared mode;
- output/test correctness.

The aggregate additionally uses GitHub's real job `started_at` / `completed_at` timestamps, so measured job duration includes:

- hosted-runner job setup;
- both checkouts;
- Java setup and dependency-cache restore;
- candidate preparation where applicable;
- Maven;
- output-cache restore/save where applicable;
- evidence upload.

## Decision views

### Later-run latency

Compare matched control-consumer job durations with shared-consumer durations. Across both retained run sets, all six shared consumers were faster than their paired control consumer.

This is the user/developer-facing question: does a later affected Java run finish materially sooner?

### Two-run compute

For every sample compare:

```text
control producer-equivalent + control consumer
vs
shared producer + shared consumer
```

This prevents the producer/save cost from being treated as free.

Each aggregate reports median, minimum and maximum rather than deciding from one runner sample. The qualification conclusion below combines the paired deltas from both exact-main run sets.

## Combined six-sample result

Across the two exact-main benchmark pairs:

- control consumer job: 21–32 s, six-sample median 23.5 s;
- shared consumer job: 13–21 s, six-sample median 17.0 s;
- paired later-run savings: `16, 14, 4, 3, 9, 2 s`;
- paired later-run saving median: **6.5 s**;
- paired later-run percentage saving median: **28.8%**;
- every one of the six matched later-run samples is positive.

For producer + consumer hosted-runner compute:

- paired savings: `10, 10, -1, 0, 9, -2 s`;
- paired saving median: **4.5 s**;
- paired percentage saving median: **8.8%**;
- three samples improve, one is neutral, and two are worse.

The shared Maven phase itself is consistently much smaller on consumers: control consumer Maven measured 9.547–16.306 s versus shared consumer 2.809–3.265 s. The additional shared candidate preparation is roughly 2–3 s per measured job.

Run set B shows that the Maven build-cache payload is small for this workload:

- 6 cache files;
- about 153 kB uncompressed;
- save step median 1 s;
- restore step median 1 s (0–1 s).

Transport size/time is therefore not the dominant source of variance in the current benchmark.

## Qualification conclusion

**Later-run latency value is qualified positive for the current real-consumer scale.**

The evidence is stronger than a Maven-only microbenchmark: all six complete shared consumer jobs, including hosted-runner setup, checkout, Java setup/dependency-cache restore, shared-cache restore/preparation, Maven and evidence upload, finish faster than their matched control jobs.

**Hosted-compute saving is not qualified as structural.**

Although the paired six-sample median is positive, two samples are worse and one is neutral. The evidence therefore does not support claiming that shared caching reliably reduces total producer+consumer hosted-runner consumption at this repository size.

This distinction matters for production policy:

- projects may have a real latency reason to opt into `shared`;
- the architecture must not advertise `shared` as a guaranteed runner-cost reduction;
- `none` remains a valid safe/default mode where build scale or operational simplicity matters more than feedback latency.

Correctness remains a gate. Performance cannot compensate for missing artifacts, missing Surefire evidence, wrong source provenance or an invalid cache decision.

A smaller Maven phase is not by itself a production-value result. The decision is based on complete matched job durations and the two-run compute view.

If shared caching is neutral or slower at the current real-consumer scale, that is valid evidence. The workload must not be enlarged solely to manufacture a positive result.

Existing production preflight and generated-output publication are unchanged by build-output caching. Their retained 67-second/60-runner-second baseline is context; unrelated overhead is not counted as cache savings.

No production repository is modified by this qualification and no migration is activated automatically.

The next qualification question is release/canonical-artifact policy: determine whether release qualification may hydrate source-equivalent Maven build-cache outputs or whether canonical release artifacts must always come from an explicit cache-bypassed/empty-output build.
