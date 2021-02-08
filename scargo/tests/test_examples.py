import sys

import pytest

from scargo.paths import EXAMPLES_DIR


@pytest.mark.script_launch_mode("subprocess")
@pytest.mark.parametrize(
    "script_path",
    [
        EXAMPLES_DIR / "python_step" / "python_step.py",
        EXAMPLES_DIR / "multi_step" / "multi_step.py",
        EXAMPLES_DIR / "multi_step_with_condition" / "multi_step_with_cond.py",
        EXAMPLES_DIR / "full_artifacts" / "full_artifacts.py",
        EXAMPLES_DIR / "csv_iter" / "csv_iter.py",
        EXAMPLES_DIR / "csv_iter_with_condition" / "csv_iter_with_cond.py",
    ],
)
def test_run_examples(script_runner, script_path):
    """
    Test scargo Python examples.

    Does not (yet) check expected outputs. Only checks runs complete without errors.
    """
    # using sys.executable instead of `python` because of virtualenvs
    result = script_runner.run(sys.executable, script_path, env={"SCARGO_LOCAL_MOUNT": EXAMPLES_DIR / "data"})
    assert result.success
    assert result.stderr == ""
