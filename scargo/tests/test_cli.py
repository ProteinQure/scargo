"""
Integration tests for the `scargo` CLI. The `script_runner` fixture is provided
by the `pytest-console-scripts` package in the `dev-dependencies`.
"""
import os

import pytest

from scargo.paths import EXAMPLES_DIR, EXAMPLES_DATA


@pytest.mark.script_launch_mode("subprocess")
@pytest.mark.parametrize(
    "local_mount, script_path",
    [
        ("/tmp", EXAMPLES_DIR / "python_step" / "python_step.py"),
        (str(EXAMPLES_DATA), EXAMPLES_DIR / "multi_step" / "multi_step.py"),
        (str(EXAMPLES_DATA), EXAMPLES_DIR / "multi_step_with_condition" / "multi_step_with_cond.py"),
        (str(EXAMPLES_DATA), EXAMPLES_DIR / "full_artifacts" / "full_artifacts.py"),
    ],
)
def test_scargo_transpile(local_mount, script_path, script_runner):
    """
    Test the `transpile` subcommand of the `scargo` CLI.
    """
    env = os.environ.copy()
    env.update({"SCARGO_LOCAL_MOUNT": local_mount})
    result = script_runner.run("scargo", "transpile", script_path, env=env)
    assert result.success
    assert result.stderr == ""


@pytest.mark.script_launch_mode("subprocess")
def test_scargo_submit(script_runner):
    """
    Test the `submit` subcommand of the `scargo` CLI.
    """

    result = script_runner.run("scargo", "submit", "test_files/scargo_script.py")
    assert result.success
    assert result.stderr == ""


@pytest.mark.script_launch_mode("subprocess")
def test_scargo_submit_watch(script_runner):
    """
    Test the `submit` subcommand of the `scargo` CLI with the `--watch` flag.
    """

    result = script_runner.run("scargo", "submit", "test_files/scargo_script.py", "--watch")
    assert result.success
    assert result.stderr == ""
