# Incremental workset metrics

The PoP distinguishes correctness, cache reuse, repeated work and elapsed time. A single filesystem timestamp or archive byte hash is not enough to decide whether work executed.

For each measured invocation retain:

- module JAR archive state and archive-payload digest;
- production `.class` output state;
- test `.class` output state;
- per-test-class Surefire report state;
- native Maven Build Cache report when the candidate provides one;
- priming and measured Maven duration;
- changed fixture inputs and exact source/toolchain provenance.

## Evidence layers

Interpret evidence in this order:

```text
correctness / semantic content
  did the required outputs and tests remain correct?

native execution/cache decision
  which Maven modules were rebuilt versus restored/reused?

filesystem/archive observation
  which output bytes, archive payloads or modification times changed?

test workset
  which Surefire test-class reports were actually regenerated?

cost
  how long did the measured Maven invocation take?
```

For JARs the harness records two hashes:

- the SHA-256 of the complete JAR bytes;
- a deterministic payload digest over sorted archive entry names and uncompressed entry contents, ignoring ZIP metadata such as entry timestamps.

This distinction matters when a lifecycle rebuild recreates a semantically equal JAR with different archive metadata. It lets the PoP distinguish "artifact bytes changed" from "production payload changed" without hiding that packaging work actually ran.

Content hashes describe other output bytes. Modification-time changes are retained only as filesystem observations. A Maven Build Cache hit can hydrate an output and therefore give it a new modification time even though compilation, testing or packaging did not execute.

For the Maven Build Cache candidate the harness retains the extension's own `cache-report*.xml` from `target/maven-incremental/` and normalizes its per-project fields into `result.json`. The native report is the primary oracle for module cache/rebuild decisions; free-form Maven log text is not the primary assertion source.

## Workset dimensions

The normalized result separates:

- JAR archive-byte changes, JAR payload changes and JAR timestamp changes;
- production-class content changes from timestamp changes;
- test-class content changes from timestamp changes;
- Surefire-report content changes from timestamp changes;
- native module cache/rebuild evidence;
- measured time versus the priming invocation.

This means a cache-restored JAR is not automatically labelled as "rebuilt" merely because its filesystem timestamp changed, while a rebuilt-but-semantically-equal JAR still remains observable as packaging work.

## Test-change coverage

The PoP contains separate cases for:

- code-only change;
- code plus its unit-test change;
- unit-test-only change;
- shared/core change.

The app fixture contains two independent test classes so a one-test change can show whether only the changed test class or the complete affected-module test set executes again. The PoP does not assume changed-test impact analysis exists; it records actual Surefire behaviour.

## Performance interpretation

Incremental execution is useful only when correctness remains intact and the actual workset is reduced. Timing is therefore evaluated after correctness/selectivity.

Single hosted-runner timings are evidence samples, not stable performance claims. Where a decision depends materially on speed, repeat the same case enough times to separate candidate behaviour from runner noise and report the distribution rather than choosing one favourable run.
