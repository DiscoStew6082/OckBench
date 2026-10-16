# Local benchmark runner

This directory contains the custom, disposable runner used for local OckBench
experiments. It is not part of the official OckBench evaluation protocol.

## Qwen3.8 official-mini smoke sequence

`run-qwen38-mini-smoke.sh` runs the official ten-row science mini and ten-row
coding mini datasets at medium reasoning, performs a clean oMLX restart, and
then runs the same datasets at low reasoning. The 40 generations use:

- exact oMLX-advertised model ID `Qwen3.8-27B-oQ8-mtp`;
- Lightning MTP enabled;
- one request at a time;
- a 32,768 total-output-token ceiling;
- one attempt with a 600-second hard wall-clock limit;
- identical Qwen thinking-mode sampling and seed at both efforts;
- separate persisted reasoning text when the endpoint exposes it; and
- disposable, read-only Docker isolation for generated coding solutions.

The command refuses to take over port 8000, starts a fresh oMLX state directory
for each effort, retains resumable OckBench caches, and stops its owned service
between efforts. Generated state, logs, caches, and results live under the
Git-ignored `artifacts/` directory.

From the repository root:

```bash
local-runner/run-qwen38-mini-smoke.sh
```

Docker Desktop must already be running. The defaults expect:

- oMLX at `/Volumes/Envoy/projects/omlx-inference-lab/.venv/bin/omlx`;
- the model under
  `/Volumes/Envoy/models/omlx/Qwen/Qwen3.8-27B-oQ8-mtp`; and
- the model-discovery root `/Volumes/Envoy/models/omlx`.

Override those locations with `OMLX_BIN`, `QWEN38_MODEL_ROOT`, or
`OCKBENCH_ARTIFACT_ROOT` when necessary. Reusing the default run ID resumes
completed rows from the per-lane caches after an interruption.

The absolute model-call ceiling is 40 requests times 600 seconds, or 6 hours
40 minutes, plus model loading, image-build, and coding-test overhead. This is
a smoke comparison only, not an official Selected or leaderboard score.


### Resume identity and revision evidence

The Docker image passes its `OCKBENCH_SOURCE_REVISION` build argument into the
benchmark's RunInputs manifest. The mini-smoke launcher also passes the local
oMLX version output, or an explicit `OCKBENCH_RUNTIME_REVISION`, plus
`OCKBENCH_MODEL_REVISION` when supplied. Set the latter to a known checkpoint
revision or content digest; the model's advertised ID is only a label. A version
string alone is not an immutable runtime build fingerprint; use the exact
runtime commit/build digest when available.

Dataset bytes and ordered loaded rows are always content-bound. Existing
unbound caches require fresh paths; retain them for historical aggregation.
No model/server requests are made by the offline identity tests.
