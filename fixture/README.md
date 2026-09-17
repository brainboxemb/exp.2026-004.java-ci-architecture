# Fixture

Deterministic multi-module Maven fixture used by every candidate.

Dependency graph:

```text
        core
       /    \
feature-a  feature-b
       \    /
         app
```

This file is intentionally inside the fixture so documentation-only changes can be applied without touching Java/Maven inputs.
