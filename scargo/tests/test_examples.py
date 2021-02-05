import pytest

from scargo.paths import EXAMPLES_DIR, PKG_ROOT_DIR


@pytest.mark.script_launch_mode("subprocess")
@pytest.mark.parametrize(
    "script_path",
    [
        EXAMPLES_DIR / "python_step" / "python_step.py",
        EXAMPLES_DIR / "multi_step" / "multi_step.py",
        EXAMPLES_DIR / "multi_step_with_condition" / "multi_step_with_cond.py",
    ],
)
def test_run_examples(script_runner, script_path):
    """
    Test scargo Python examples.

    Does not (yet) check expected outputs. Only checks runs complete without errors.
    """
    result = script_runner.run("python", script_path, env={"SCARGO_LOCAL_MOUNT": PKG_ROOT_DIR})
    assert result.success
    assert result.stderr == ""
