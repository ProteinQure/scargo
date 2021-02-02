"""
Integration tests for the `scargo` CLI. The `script_runner` fixture is provided
by the `pytest-console-scripts` package in the `dev-dependencies`.
"""

import pytest


@pytest.mark.script_launch_mode("subprocess")
def test_scargo_transpile(script_runner):
    """
    Test the `transpile` subcommand of the `scargo` CLI.
    """

    result = script_runner.run("scargo", "transpile", "test_files/scargo_script.py")
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
