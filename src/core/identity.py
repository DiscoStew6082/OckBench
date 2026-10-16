"""Run identity: the tuple that makes a cache safe to resume into.

A cache is only safe to resume if the run that produced it is the *same* run in
every way that could change a problem's outcome: same provider/model, same
dataset+split, same prompt/template, same resolved request shape, same
generation settings and output budget, same evaluator/judge identity, and same
scoring/schema version. This module computes that tuple (with secrets excluded)
and a stable hash of it, so resume can compare identities and refuse a silent
merge across different runs.
"""
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict

from ..utils.prompt_formatter import template_identity
from ..utils.request_overrides import redact_override_set, redact_url
from .schemas import SCHEMA_VERSION, BenchmarkConfig, Problem


@dataclass(frozen=True)
class RunInputs:
    """Content-bound inputs captured before cache admission or inference.

    Hash the loaded rows too: loader transformations, selection, ordering, answer
    and metadata changes are material even when the dataset path is unchanged.
    Only explicit revision fields enter provenance; arbitrary env/config data and
    credentials must never be copied into this manifest.
    """

    dataset_sha256: str
    selected_rows_sha256: str
    selected_row_count: int
    model_revision: str | None
    runtime_revision: str | None
    benchmark_revision: str | None
    schema_version: str = "run_inputs_v1"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_run_inputs(
    config: BenchmarkConfig,
    *,
    dataset_bytes: bytes | None = None,
    problems: list[Problem] | None = None,
) -> RunInputs:
    """Bind a dataset snapshot and the ordered selected problems to a run."""
    if dataset_bytes is None:
        dataset_bytes = Path(config.dataset_path).read_bytes()
    if problems is None:
        from ..loaders.base import get_loader
        problems = get_loader(filepath=config.dataset_path).load(content=dataset_bytes)
    seen = set()
    for problem in problems:
        try:
            if problem.id in seen:
                raise ValueError(f"Duplicate selected problem id: {problem.id!r}")
            seen.add(problem.id)
        except TypeError as exc:
            raise ValueError("Selected problem ids must be hashable cache keys") from exc
    return RunInputs(
        dataset_sha256=hashlib.sha256(dataset_bytes).hexdigest(),
        selected_rows_sha256=identity_hash([p.model_dump(mode="json") for p in problems]),
        selected_row_count=len(problems),
        model_revision=config.model_revision,
        runtime_revision=config.runtime_revision,
        benchmark_revision=os.environ.get("OCKBENCH_SOURCE_REVISION") or None,
    )


def compute_run_identity(config: BenchmarkConfig, run_inputs: RunInputs | None = None) -> Dict[str, Any]:
    """Return the ordered identity components for ``config`` (no secrets).

    Credentials are intentionally excluded — they do not change a problem's
    outcome and must never be written to a cache header. The endpoint host *is*
    part of identity (the same model at two endpoints is a different run), but
    any credentials embedded in a ``base_url`` are masked first.
    """
    run_inputs = run_inputs or build_run_inputs(config)
    overrides = config.request_overrides
    judge_identity = None
    if config.judge is not None:
        from ..evaluators.judge import runtime_identity as judge_runtime_identity

        # Judge identity = model + endpoint (never the key); judge request shape
        # affects verdicts, so include it.
        judge_identity = {
            "model": config.judge.model,
            "base_url": redact_url(config.judge.base_url),
            # Judge generation settings change verdicts (e.g. max_tokens truncation,
            # timeout-driven failures), so they are part of the run identity.
            "max_tokens": config.judge.max_tokens,
            "timeout": config.judge.timeout,
            "request_overrides": {
                # Mask secret-keyed override values — this identity is written to
                # the cache header on disk; non-secret structure is kept (it
                # affects the request shape and thus the run identity).
                "set": redact_override_set(config.judge.request_overrides.set),
                "unset": list(config.judge.request_overrides.unset),
            },
            "runtime": judge_runtime_identity(),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "run_inputs": run_inputs.to_dict(),
        "provider": config.provider,
        "model": config.model,
        "base_url": redact_url(config.base_url),
        "dataset": {
            "name": config.dataset_name,
            "split": config.dataset_split,
            "path": config.dataset_path,
        },
        "evaluator_type": config.evaluator_type,
        # Evaluator scoring settings that can change a problem's verdict (e.g. the
        # code subprocess timeout: a timeout-sensitive solution may score
        # differently at 5s vs 30s), so a change refuses resume into an old cache.
        "evaluator_settings": {
            "execution_timeout": config.execution_timeout,
            "include_challenge_tests": config.include_challenge_tests,
        },
        "prompt_template": template_identity(config.evaluator_type),
        "request_overrides": {
            # Mask secret-keyed override values before they reach the on-disk
            # cache header; keep non-secret structure (it shapes the request).
            "set": redact_override_set(overrides.set),
            "unset": list(overrides.unset),
        },
        "generation": {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_output_tokens": config.max_output_tokens,
            "max_context_window": config.max_context_window,
            **(
                {"wall_clock_timeout": config.wall_clock_timeout}
                if config.wall_clock_timeout is not None else {}
            ),
        },
        "judge": judge_identity,
    }


def identity_hash(identity: Any) -> str:
    """Stable SHA-256 over the canonicalized identity components."""
    canonical = json.dumps(identity, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def diff_identity(expected: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Any]:
    """Return the top-level identity keys whose values differ, for messaging."""
    changed: Dict[str, Any] = {}
    for key in sorted(set(expected) | set(actual)):
        if expected.get(key) != actual.get(key):
            changed[key] = {"cache": expected.get(key), "run": actual.get(key)}
    return changed

