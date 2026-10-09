"""`swebench report` re-grades the run it is pointed at.

It used to re-grade the gold patches whatever the run had evaluated. For a model's
run that found no test output under `gold/`, re-graded nothing, and rewrote the
run's results.json with every instance as an error.
"""

import json

import pytest
from typer.testing import CliRunner

from swebench.cli.cli import app
from swebench.harness import run_evaluation

IID = "x__x-1"
F2P = "tests/test_a.py::test_fix"
P2P = "tests/test_a.py::test_keep"


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """A CWD holding a one-instance dataset; logs/ resolve under it."""
    monkeypatch.chdir(tmp_path)
    # re-grading reads logs only; neither needs a Docker daemon or a lower fd limit
    monkeypatch.setattr(run_evaluation, "_docker_client", lambda: None)
    monkeypatch.setattr("resource.setrlimit", lambda *a, **k: None)
    instance = {
        "instance_id": IID,
        "image": "img",
        "repo": "x/x",
        "version": "1",
        "FAIL_TO_PASS": [F2P],
        "PASS_TO_PASS": [P2P],
        "log_parser": "parse_log_pytest",
        "eval_type": "pass_and_fail",
        "eval_script": "echo",
        "patch": "GOLD PATCH",
    }
    (tmp_path / "ds.json").write_text(json.dumps([instance]))
    return tmp_path


def _write_run(root, run_id, model, resolved=True):
    run = root / "logs" / "evaluation" / run_id
    inst = run / model / IID
    inst.mkdir(parents=True)
    (inst / "patch.diff").write_text("MODEL PATCH")
    status = "PASSED" if resolved else "FAILED"
    (inst / "test_output.txt").write_text(
        ">>>>> Start Test Output\n"
        f"{status} {F2P}\n"
        f"PASSED {P2P}\n"
        ">>>>> End Test Output\n"
        f">>>>> Test Exit Code: {0 if resolved else 1}\n"
    )
    (run / "run.json").write_text(
        json.dumps(
            {"dataset": str(root / "ds.json"), "split": "test", "task_repo": None}
        )
    )
    return run


def _results(run):
    return json.loads((run / "results.json").read_text())


def test_a_model_run_is_regraded_as_that_model(workdir):
    run = _write_run(workdir, "my-run", "gpt5")
    result = CliRunner().invoke(app, ["report", "my-run"])
    assert result.exit_code == 0, result.output
    results = _results(run)
    assert results["resolved_ids"] == [IID]
    assert results["error_ids"] == []
    report = json.loads((run / "gpt5" / IID / "report.json").read_text())
    assert report[IID]["resolved"] is True
    assert not (run / "gold").exists()


def test_a_regrade_follows_the_log_not_the_previous_verdict(workdir):
    run = _write_run(workdir, "my-run", "gpt5", resolved=False)
    (run / "gpt5" / IID / "report.json").write_text(
        json.dumps({IID: {"resolved": True}})
    )
    result = CliRunner().invoke(app, ["report", "my-run"])
    assert result.exit_code == 0, result.output
    assert _results(run)["unresolved_ids"] == [IID]


def test_a_run_holding_several_models_asks_which(workdir):
    run = _write_run(workdir, "my-run", "a")
    _write_run(workdir, "my-run", "b", resolved=False)
    result = CliRunner().invoke(app, ["report", "my-run"])
    assert result.exit_code == 1
    assert "--model" in result.output
    assert not (run / "results.json").exists()

    result = CliRunner().invoke(app, ["report", "my-run", "-m", "b"])
    assert result.exit_code == 0, result.output
    assert _results(run)["unresolved_ids"] == [IID]


def test_a_missing_run_is_an_error_not_an_empty_report(workdir):
    result = CliRunner().invoke(app, ["report", "no-such-run", "-d", "ds.json"])
    assert result.exit_code == 1
    assert "no such run directory" in result.output
    assert not (workdir / "logs" / "evaluation" / "no-such-run").exists()
