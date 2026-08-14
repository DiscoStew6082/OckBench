# OckBench evaluation size: official treatment

## Bottom line

For an **officially comparable OckBench result**, the authors use the frozen
**OckBench Selected v1.0** set: **200 problems per model/effort setting**
(100 math, 60 coding, 40 science). They explicitly evaluate every setting on
that fixed set. Low and medium are separate settings, not two halves of one
run.

The benchmark is already a deliberately reduced set selected from larger
candidate pools. The authors do not publish a second, statistically validated
short form. A smaller run is reasonable for local screening or choosing an
effort level, but it should be labelled a pilot and should not be compared with
the official leaderboard/OckScore.

## What the authors explicitly say

- The [paper, Sections 3.2 and 4.1](https://arxiv.org/html/2511.05722) defines a
  non-random Differentiation Filter, retains problems with representative-model
  accuracy between 10% and 90%, ranks the survivors by output-token variance,
  and selects 100 math, 60 coding, and 40 science problems. It calls these 200
  items the fixed OckBench v1.0 split and says all evaluated model/settings run
  on all 200.
- The [official project page](https://ockbench.github.io/) labels its leaderboard
  “OckBench (Selected) — 200 problems (100 math + 60 coding + 40 science).” It
  also presents effort variants as distinct settings.
- The official repository contains the three frozen files:
  [100 math](https://github.com/OckBench/OckBench/blob/b72752a0ba5989d3c212675ec60d3eedcd838628/data/OckBench_Math_Selected.jsonl),
  [60 coding](https://github.com/OckBench/OckBench/blob/b72752a0ba5989d3c212675ec60d3eedcd838628/data/OckBench_Coding_Selected.jsonl), and
  [40 science](https://github.com/OckBench/OckBench/blob/b72752a0ba5989d3c212675ec60d3eedcd838628/data/OckBench_Science_Selected.jsonl).
- An earlier official README explicitly warned users to keep splits consistent
  and not compare a full-dataset run with a Selected-subset run
  ([permalink](https://github.com/OckBench/OckBench/blob/a2d6fb18641c2157ce248cfaf88087c04e23eaa3/README.md#L139-L147)).

## Reduced evaluation and sampling

- The repository does ship [10 coding](https://github.com/OckBench/OckBench/blob/b72752a0ba5989d3c212675ec60d3eedcd838628/data/OckBench_coding_mini.jsonl)
  and [10 science](https://github.com/OckBench/OckBench/blob/b72752a0ba5989d3c212675ec60d3eedcd838628/data/OckBench_science_mini.jsonl)
  files, but no math mini file. The author commit that added them calls them
  “small smoke-test subsets”
  ([commit](https://github.com/OckBench/OckBench/commit/a2d6fb18641c2157ce248cfaf88087c04e23eaa3)). The
  [current configuration documentation](https://github.com/OckBench/OckBench/blob/b72752a0ba5989d3c212675ec60d3eedcd838628/docs/configuration.md#L14-L25)
  merely says Selected and mini splits are available; it makes no accuracy,
  representativeness, or leaderboard-comparability claim for mini. They should
  not be repurposed as a short-form score: coding mini has no problem IDs in
  common with Coding Selected, and science mini overlaps Science Selected on
  only one of ten IDs.
- The current CLI has no `--limit`, random-sample, shuffle, or benchmark-seed
  option. It accepts a dataset path and a provenance label, then the
  [runner loads every row in that file](https://github.com/OckBench/OckBench/blob/b72752a0ba5989d3c212675ec60d3eedcd838628/src/core/runner.py#L256-L261).
- The paper reports **single-shot** evaluation and refers to accuracy as
  **Pass@1**. It does not report Pass@k or repeated seeded generations. It says
  greedy decoding (`temperature=0`) was used where possible. The newer live
  project page says decoding sampling follows each model's validated evaluation
  configuration; neither source describes random question subsampling.
- The live page notes one exceptional pooled MiniMax result made from four
  requested effort-label runs. That is reported as pooled observations, not as
  Pass@k and not as a reduced question set.

## Implication for the current Qwen experiment

The proposed 200 generations are **100 Selected science/coding problems at low
plus the same 100 at medium**. That is a sound matched domain experiment, but it
is not the official all-domain OckBench run: an official Selected run is 200
problems **per effort setting**, including math, so two full settings would be
400 generations.

It is appropriate to cut below 200 generations if the present goal is only to
choose low versus medium economically. That would be an internal pilot, not an
official score. Use the same fixed problem IDs for both efforts and report
coding and science separately. The authors provide no endorsed smaller sample
size, so any particular cut (for example 20, 40, or 60 problems per setting) is
our experimental-design choice, not official OckBench guidance.

## Reasoning and generation budgets

OckBench does not impose one universal hidden-reasoning budget across models.
Every run has a provider-visible total output cap covering reasoning plus the
final answer. Provider-specific controls are recorded separately when the API
offers them: effort labels such as low, medium, high, or xhigh for some models,
and an explicit thinking-token budget for providers such as Gemini. The public
configuration templates use total-output ceilings ranging from 64K to 128K,
but those are provider examples rather than one cross-model standard.

For local Qwen, the official configuration example only enables thinking; it
does not define an OckBench-standard low or medium reasoning-token allowance.
Therefore the local Qwen3.8 smoke comparison uses the same 32,768 total-output
cap at both efforts and changes only the provider-supported reasoning-effort
label. The 600-second wall-clock limit is an explicitly local operational
boundary, not part of the official benchmark protocol.

## Chosen local smoke scope

The official repository's ten-row coding mini and ten-row science mini files
will be run once at medium and once at low: 40 generations total. This is a
smoke comparison of model behavior, reasoning capture, timeout handling, and
evaluation plumbing. It is not a representative Selected result and must not
be reported as an OckBench leaderboard score.
