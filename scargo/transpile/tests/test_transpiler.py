"""
Testing the Transpiler classes.
"""

import ast
from pathlib import Path

import pytest

from scargo.core import MountPoint, MountPoints, WorkflowParams
from scargo.transpile import transpiler


def test_transpile_parameters(scargo_workflow_params_file):
    """
    Test the standalone transpile() function with a small script that contains
    a definition of workflow parameters only.
    """

    # try to transpile the Python scargo script with the workflow parameters only
    with Path(scargo_workflow_params_file).open("r") as fi:
        source = fi.read()

    script_locals = transpiler.get_script_locals(source)
    workflow_params = transpiler.transpile_workflow_parameters(script_locals)

    expected_workflow_params = {
        "s3-bucket": "pq-dataxfer-tmp",
        "input-val": "1",
        "output-path": "testing/scargo-examples/output",
    }

    assert dict(workflow_params) == expected_workflow_params


@pytest.mark.parametrize(
    "script_locals, expected",
    [
        (
            {
                "workflow_parameters": WorkflowParams(
                    {"s3-bucket": "pq-dataxfer-tmp", "input-val": "1", "output-path": "testing/scargo-examples/output"}
                ),
                "mount_points": MountPoints(
                    {"root": MountPoint(local=Path("/home/sean/git/scargo/examples/data"), remote="pq-dataxfer-tmp")}
                ),
            },
            {"root": "pq-dataxfer-tmp"},
        )
    ],
)
def test_mount_points_from_locals(script_locals, expected):
    assert transpiler.mount_points_from_locals(script_locals) == expected


@pytest.mark.parametrize(
    "decorators, expected",
    [
        (
            [
                ast.Call(
                    func=ast.Name(id="scargo", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="image", value=ast.Constant(value="python:alpine"))],
                )
            ],
            ["scargo"],
        ),
        ([ast.Name(id="entrypoint", ctx=ast.Load())], ["entrypoint"]),
    ],
)
def test_get_decorator_names(decorators, expected):
    assert transpiler.get_decorator_names(decorators) == expected
