"""A run that timed out is not graded as finished.

When the eval script outlives its timeout, run_instance appends a timeout line to the
test output and counts the instance as an error. Grading checked for the
TESTS_TIMEOUT marker, which nothing writes, so `swebench report`, `submit package` and
`submit verify` -- which re-grade from that same test output -- scored an instance
whose log had already reached the end marker as resolved.
"""

from swebench.harness.constants import END_TEST_OUTPUT, START_TEST_OUTPUT
from swebench.harness.grading import get_eval_report, get_logs_eval
from swebench.types import TestSpec

IID = "x__x-1"
F2P = "tests/test_a.py::test_fix"
P2P = "tests/test_a.py::test_keep"


def _spec():
    return TestSpec(
        instance_id=IID,
        image="x:latest",
        eval_script_list=[],
        repo="x/x",
        version="1.0",
        FAIL_TO_PASS=[F2P],
        PASS_TO_PASS=[P2P],
        log_parser="parse_log_pytest",
        eval_type="pass_and_fail",
    )


def _log(tmp_path, tail=""):
    log = tmp_path / "test_output.txt"
    log.write_text(
        f"{START_TEST_OUTPUT}\nPASSED {F2P}\nPASSED {P2P}\n{END_TEST_OUTPUT}\n"
        f">>>>> Test Exit Code: 0\n{tail}"
    )
    return log


def _resolved(log):
    pred = {"instance_id": IID, "model_patch": "diff", "model_name_or_path": "m"}
    report = get_eval_report(_spec(), pred, str(log), include_tests_status=False)
    return report[IID]["resolved"]


def test_a_timed_out_run_is_not_resolved(tmp_path):
    # exactly what run_instance appends on a timeout
    log = _log(tmp_path, "\n\nTimeout error: 1800 seconds exceeded.")
    assert get_logs_eval(_spec(), str(log)) == ({}, False)
    assert _resolved(log) is False


def test_the_same_log_without_the_timeout_still_resolves(tmp_path):
    assert _resolved(_log(tmp_path)) is True


def test_a_test_printing_the_phrase_is_not_a_timeout(tmp_path):
    """Only the line the harness ends the file with marks a timeout."""
    log = tmp_path / "test_output.txt"
    log.write_text(
        f"{START_TEST_OUTPUT}\nTimeout error: 5 seconds exceeded.\nPASSED {F2P}\n"
        f"PASSED {P2P}\n{END_TEST_OUTPUT}\n>>>>> Test Exit Code: 0\n"
    )
    assert _resolved(log) is True
