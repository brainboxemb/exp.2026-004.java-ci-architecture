# Incremental workset metrics

The PoP distinguishes final-output correctness from actual repeated work.

For each measured invocation retain:

- module JAR output state;
- production `.class` output state;
- test `.class` output state;
- per-test-class Surefire report state;
- priming and measured Maven duration;
- changed fixture inputs and exact source/toolchain provenance.

Modification-time changes are used to observe rewritten outputs; content hashes distinguish rewritten-but-identical output from changed output content.

The workset is interpreted at three levels:

```text
compile/package workset
  which production classes, test classes and JARs were rewritten

test workset
  which Surefire test-class reports were rewritten/executed

cost
  measured Maven duration versus the clean priming invocation
```

A later cache-enabled candidate must also retain native hit/miss/execute/reuse evidence, because hydrated cache outputs may receive new filesystem timestamps even when their producing lifecycle did not execute.

The PoP specifically contains separate cases for:

- code-only change;
- code plus its unit-test change;
- unit-test-only change;
- shared/core change.

The app fixture contains two independent test classes so a one-test change can show whether one test class or the complete module test set executed again.
