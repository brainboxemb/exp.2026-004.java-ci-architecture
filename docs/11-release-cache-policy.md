# Release and canonical-artifact cache policy

## Status

**Qualified policy.**

Tracking: issue #20.

This policy closes the final release/canonical-artifact question for the initial Java CI architecture PoP. It combines already-qualified cache behaviour with the existing immutable release evidence from the real event-timing consumer.

No additional runtime testcase is required because the release boundary is already proven in production-shaped CI.

## Inputs to the decision

The policy rests on the following qualified evidence:

- local Maven-native module reuse and invalidation;
- build-model/dependency invalidation;
- forced cache-bypass through CI-11;
- runtime-separated cache identity;
- fresh-runner and cross-workflow shared reuse;
- representative later-run latency value;
- CI-16 product-scoped Git build-identity correctness;
- the existing exact-tag real-consumer release run.

The real release evidence is:

```text
repository  brainboxemb/2026-010-02.java.event-timing-framework
tag         v0.2.1
source      0f9dbc2f5aa0beaec8f63465ada83f2bc2a83709
workflow    35211641563
```

That release run proves the stronger operational release shape already exists:

- exact tagged source checkout on a fresh GitHub-hosted Linux runner;
- Maven dependency caching only;
- no Maven build-output-cache extension/restore;
- one canonical Linux Maven producer;
- independent native full-Windows Maven qualification;
- Windows smoke of the exact Linux-produced application JAR;
- generated release publication that downloads and publishes prepared output without another Maven build;
- final release validation of artifact version and exact embedded source revision.

## Normal canonical PR/main policy

Normal canonical execution may use one of:

```text
none
local
shared
```

The project chooses the mode. `none` remains a first-class safe/default mode.

Cached canonical output is valid only when every material output input participates in cache validity, including:

- source files;
- effective Maven build model;
- dependencies/plugins;
- runtime/toolchain identity;
- product-specific non-source inputs.

Product-owned build identity is part of this rule. If an artifact embeds repository identity, the owning module declares that input. CI-16 proves the event-timing app can add `../.git/HEAD` without forcing unrelated framework output to rebuild.

### Producer versus materialization provenance

A hydrated result keeps the evidence of the producer that actually executed Maven.

Current execution/materialization evidence is separate.

Therefore this is valid:

```text
producer source revision       A
current materialization source B
```

when Maven has established that the producer output is input-equivalent for B.

The orchestration layer must never rewrite producer evidence to pretend that Maven executed again.

## Protected-main publication

Protected-main publication consumes the prepared canonical output from the qualifying canonical run.

Publication:

- does not invoke Maven merely to publish;
- does not recalculate product artifacts;
- may add current orchestration/materialization evidence;
- does not rewrite producer execution evidence.

Build-output caching therefore changes how the canonical producer may obtain valid module output; it does not change the publication ownership boundary.

## Exact-tag release policy

The exact release tag is an independent trust boundary.

The canonical Linux release producer must:

1. check out the exact tagged source on a fresh/empty build workspace;
2. start with no module `target/` outputs;
3. consume **no Maven build-output cache**;
4. publish **no Maven build-output cache** from that release qualification;
5. execute the ordinary authoritative Maven lifecycle;
6. retain exact source/toolchain/test/build evidence;
7. produce the artifacts later used by release publication and exact-artifact smoke.

The preferred production expression is:

```text
cache mode = none
```

for the exact-tag Linux canonical producer.

The independent native Windows full qualification likewise uses fresh Maven execution rather than build-output reuse.

### Dependency cache remains allowed

Maven dependency caching remains allowed during release qualification.

This distinction is intentional:

```text
~/.m2/repository dependency/plugin downloads
    !=
Maven build-output cache
```

Reusing downloaded immutable dependencies does not substitute previously compiled/tested/package output.

### Empty workspace versus mvn clean

A literal `mvn clean` is not required when an ephemeral hosted runner checks out exact source into a workspace with no module outputs.

The requirement is **empty module output state**, not a mandatory extra Maven lifecycle phase.

A reused/self-hosted runner would need an explicit equivalent reset before the release producer starts.

## Why exact-tag release deliberately rebuilds

A release tag may identify the same source commit that already passed protected-main canonical execution.

The release still rebuilds because the tag boundary has a different trust purpose:

- exact immutable release qualification;
- independent release evidence;
- full platform qualification;
- product artifact/build-identity validation;
- release failure/archive semantics;
- immutable release publication.

This is a deliberate correctness/audit boundary, not an optimization oversight.

The representative latency qualification does not override that boundary.

## Release publication

After the fresh exact-tag Linux producer succeeds, publication reuses its prepared canonical output.

The release pipeline may:

- add orchestration/timing evidence;
- publish `rel/vX.Y.Z/bld`;
- validate artifact identity;
- create checksums/evidence bundles;
- publish GitHub Release assets.

It must not run Maven again merely to materialize those outputs.

## No CI-17

A new testcase solely to prove fresh exact-tag execution would duplicate existing evidence:

- CI-11 already proves cache reads/saves can be bypassed while retaining the same Maven lifecycle;
- real `v0.2.1` exact-tag run `35211641563` already proves the stronger operational shape on a fresh hosted runner with no build-output cache configured;
- Migration 006 and the same release prove publication consumes prepared output without rebuilding.

The design-first PoP model therefore stops here rather than manufacturing redundant qualification work.

## Production handoff consequence

The initial PoP now supports a production architecture decision:

- cache mode remains project-configurable as `none | local | shared`;
- `shared` has qualified later-run latency value, not guaranteed hosted-compute savings;
- cache runtime identity and retained Surefire outputs are mandatory shared-cache constraints;
- product modules must declare material non-source inputs such as embedded Git identity;
- exact-tag release uses `none`/fresh canonical execution;
- publication reuses prepared canonical output.

This conclusion does **not** activate a production migration automatically. Cross-project adoption remains a separate `brainboxemb.meta` decision.
