# Test cases

Each `cases/*.toml` file is a declarative experiment case. Cases describe setup, controlled source changes and candidate-independent correctness expectations. They do not embed shell commands.

The generic harness copies `fixture/` into an isolated work directory, optionally primes it, applies the declared change, invokes the selected candidate and writes structured evidence.

The first five cases bootstrap the harness:

- `CI-01` — cold clean build;
- `CI-02` — identical warm rebuild;
- `CI-03` — unrelated documentation change after a warm build;
- `CI-04` — application-only source change;
- `CI-05` — shared core source change.

These first cases deliberately **observe** module/output reuse rather than asserting a preferred incremental strategy. Once the observation contract is proven reliable, later cases add explicit selectivity/cache expectations shared by all candidates.
