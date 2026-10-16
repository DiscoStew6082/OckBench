"""Content-bound cache admission; all providers and datasets are local fakes."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from src.core.cache import CacheIdentityMismatch, RunCache, aggregate_cache_file
from src.core.config import load_config
from src.core.identity import build_run_inputs, compute_run_identity, identity_hash
from src.core.runner import BenchmarkRunner
from src.core.schemas import BenchmarkConfig, Problem
from src.loaders.base import get_loader
from tests.test_cache_identity import _register_fixed_provider


def fixture_config(tmp_path, **kwargs):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(json.dumps({"id": "one", "problem": "Which?", "answer": "A", "metadata": {}}) + "\n")
    return BenchmarkConfig(dataset_path=str(dataset), provider="gemini", model="mutable-label",
                           evaluator_type="science", max_output_tokens=100, **kwargs)


def test_same_path_changed_bytes_refuses_resume_and_preserves_cache(tmp_path):
    config = fixture_config(tmp_path)
    cache_path = tmp_path / "cache.jsonl"
    RunCache.open(str(cache_path), config)
    before = cache_path.read_bytes()
    dataset = Path(config.dataset_path)
    dataset.write_text(dataset.read_text().replace('"A"', '"B"'))
    with pytest.raises(CacheIdentityMismatch, match="run_inputs"):
        RunCache.open(str(cache_path), config)
    assert cache_path.read_bytes() == before


def test_row_selection_order_answer_and_metadata_are_bound(tmp_path):
    config = fixture_config(tmp_path)
    rows = [Problem(id="one", problem="Question", answer="A"), Problem(id="two", problem="Q2", answer="B")]
    initial = build_run_inputs(config, problems=rows)
    for changed in [rows[:1], rows[::-1], [rows[0].model_copy(update={"answer": "C"}), rows[1]],
                    [rows[0].model_copy(update={"metadata": {"test_list": ["changed"]}}), rows[1]]]:
        manifest = build_run_inputs(config, problems=changed)
        assert manifest.dataset_sha256 == initial.dataset_sha256
        assert manifest.selected_rows_sha256 != initial.selected_rows_sha256
    assert initial == build_run_inputs(config, problems=rows)


def test_duplicate_cache_keys_fail_before_admission(tmp_path):
    config = fixture_config(tmp_path)
    rows = [Problem(id="one", problem="Question", answer="A")] * 2
    with pytest.raises(ValueError, match="Duplicate selected problem id"):
        build_run_inputs(config, problems=rows)


def test_old_unbound_cache_readable_but_never_resumed_or_rewritten(tmp_path):
    config = fixture_config(tmp_path)
    identity = compute_run_identity(config)
    identity.pop("run_inputs")
    cache_path = tmp_path / "old.jsonl"
    cache_path.write_text(json.dumps({"__ockbench_cache__": True, "identity": identity,
                                    "identity_hash": identity_hash(identity)}) + "\n")
    before = cache_path.read_bytes()
    with pytest.raises(CacheIdentityMismatch, match="predates content-bound RunInputs"):
        RunCache.open(str(cache_path), config)
    assert aggregate_cache_file(str(cache_path))[0] == []
    assert cache_path.read_bytes() == before


def test_revision_change_refuses_resume_without_recording_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("OCKBENCH_SOURCE_REVISION", "benchmark-123")
    monkeypatch.setenv("UNRELATED_SECRET", "do-not-record")
    config = fixture_config(tmp_path, model_revision="checkpoint-abc", runtime_revision="omlx-xyz", api_key="secret-key")
    manifest = build_run_inputs(config)
    cache_path = str(tmp_path / "cache.jsonl")
    RunCache.open(cache_path, config, manifest)
    header = Path(cache_path).read_text()
    assert "secret-key" not in header and "do-not-record" not in header
    assert manifest.benchmark_revision == "benchmark-123"
    for field in ["model_revision", "runtime_revision", "benchmark_revision"]:
        with pytest.raises(CacheIdentityMismatch, match="run_inputs"):
            RunCache.open(cache_path, config, replace(manifest, **{field: "different"}))


def test_loader_and_manifest_share_exact_snapshot_despite_path_replacement(tmp_path):
    config = fixture_config(tmp_path)
    snapshot = Path(config.dataset_path).read_bytes()
    loader = get_loader(config.dataset_path)
    Path(config.dataset_path).write_text('{"id":"one","problem":"Different","answer":"B"}\n')
    rows = loader.load(content=snapshot)
    assert rows[0].answer == "A"
    original = build_run_inputs(config, dataset_bytes=snapshot, problems=rows)
    assert original.dataset_sha256 != build_run_inputs(config).dataset_sha256


def test_runner_refuses_changed_dataset_before_provider_generation(tmp_path):
    calls = []
    provider = _register_fixed_provider("fake-content-bound", calls=calls)
    config = fixture_config(tmp_path).model_copy(update={"provider": provider})
    cache_path = str(tmp_path / "cache.jsonl")
    first = BenchmarkRunner(config, cache_path).run()
    assert len(calls) == 1 and first.run_inputs["schema_version"] == "run_inputs_v1"
    second = BenchmarkRunner(config, cache_path).run()
    assert len(calls) == 1 and second.run_inputs == first.run_inputs
    Path(config.dataset_path).write_text('{"id":"one","problem":"Which?","answer":"B"}\n')
    with pytest.raises(CacheIdentityMismatch, match="run_inputs"):
        BenchmarkRunner(config, cache_path).run()
    assert len(calls) == 1


def test_revision_env_handoff_and_explicit_config_precedence(tmp_path, monkeypatch):
    config = fixture_config(tmp_path)
    monkeypatch.setenv("OCKBENCH_MODEL_REVISION", "env-model")
    monkeypatch.setenv("OCKBENCH_RUNTIME_REVISION", "env-runtime")
    loaded = load_config(**config.model_dump())
    assert loaded.model_revision == "env-model"
    assert loaded.runtime_revision == "env-runtime"
    loaded = load_config(**{**config.model_dump(), "model_revision": "explicit"})
    assert loaded.model_revision == "explicit"
