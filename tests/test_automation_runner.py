from pathlib import Path

import pytest

from automation.runner import RunnerConfig, atomic_json, read_state, run_once, single_writer


def _config(tmp_path):
    path = tmp_path / "config" / "universe.json"
    atomic_json(path, {"assets": {"TEST3": {"local_file": "../prices.csv"}}})
    (tmp_path / "prices.csv").write_text("date,close\n2020-01-01,10\n", encoding="utf-8")
    return RunnerConfig(manifest_path=path, output_root=tmp_path / "output")


def test_unchanged_input_skips_and_changed_bytes_recompute(tmp_path):
    config = _config(tmp_path)
    calls = []
    def research(*args, **kwargs):
        calls.append(args)
        return {"status": "completed"}
    first = run_once(config, research=research)
    assert run_once(config, research=research)["unchanged"] is True
    (tmp_path / "prices.csv").write_text("date,close\n2020-01-01,11\n", encoding="utf-8")
    second = run_once(config, research=research)
    assert len(calls) == 2
    assert first["run_id"] != second["run_id"]
    assert Path(first["output_dir"]).is_dir()


def test_blocked_is_not_promoted_or_hidden_on_repeat(tmp_path):
    config = _config(tmp_path)
    result = run_once(config, research=lambda *a, **k: {"status": "blocked", "missing": ["TEST3"]})
    assert result["last_success"] is None
    assert not result["promotion_allowed"]
    assert run_once(config, research=lambda *a, **k: pytest.fail("should skip"))["status"] == "blocked"


def test_failure_retains_prior_success_and_redacts_exception(tmp_path):
    config = _config(tmp_path)
    success = run_once(config, research=lambda *a, **k: {"status": "completed"})
    def fail(*args, **kwargs):
        raise ValueError("sensitive-value-never-log")
    failure = run_once(config, force=True, research=fail)
    assert failure["status"] == "failed"
    assert failure["last_success"]["run_id"] == success["run_id"]
    assert "sensitive-value" not in (config.output_root / "state.json").read_text(encoding="utf-8")
    assert read_state(config.output_root)["error_type"] == "ValueError"


def test_lock_prevents_two_writers_and_releases_after_exception(tmp_path):
    lock = tmp_path / "runner.lock"
    with single_writer(lock):
        with pytest.raises(RuntimeError, match="holds the lock"):
            with single_writer(lock):
                pytest.fail("second writer entered")
    with single_writer(lock):
        pass


def test_input_mutation_during_run_cannot_be_marked_success(tmp_path):
    config = _config(tmp_path)
    def mutation(*args, **kwargs):
        (tmp_path / "prices.csv").write_text("changed", encoding="utf-8")
        return {"status": "completed"}
    result = run_once(config, research=mutation)
    assert result["status"] == "failed"
    assert result["error_type"] == "InputsChangedDuringRun"
    assert result["last_success"] is None


def test_live_config_rejected():
    with pytest.raises(ValueError):
        RunnerConfig(mode="live")
