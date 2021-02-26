"""
Testing the Transpiler classes.
"""

from pathlib import Path

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
