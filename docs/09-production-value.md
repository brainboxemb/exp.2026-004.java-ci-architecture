# Representative end-to-end production-value qualification

## Status

**Active qualification.**

Cross-workflow cache correctness is already qualified. This slice answers a different question: whether the extra shared-cache mechanism is worthwhile at the scale of a current real Java consumer.

Tracking: issue #14.

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

Three samples are executed.

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

Compare the three matched control-consumer job durations with the three shared-consumer durations.

This is the user/developer-facing question: does a later affected Java run finish materially sooner?

### Two-run compute

For every sample compare:

```text
control producer-equivalent + control consumer
vs
shared producer + shared consumer
```

This prevents the producer/save cost from being treated as free.

The aggregate reports median, minimum and maximum rather than deciding from one runner sample.

## Interpretation

Correctness remains a gate. Performance cannot compensate for missing artifacts, missing Surefire evidence, wrong source provenance or an invalid cache decision.

A smaller Maven phase is not by itself a production-value result. The decision is based on complete matched job durations and the two-run compute view.

If shared caching is neutral or slower at the current real-consumer scale, that is valid evidence. The workload must not be enlarged solely to manufacture a positive result.

Existing production preflight and generated-output publication are unchanged by build-output caching. Their retained 67-second/60-runner-second baseline is context; unrelated overhead is not counted as cache savings.

No production repository is modified by this qualification and no migration is activated automatically.
