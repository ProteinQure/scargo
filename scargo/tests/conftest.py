"""
Pytest fixtures used across the test suite.
"""

from pathlib import Path
import tempfile
from textwrap import dedent

import pytest
import yaml


@pytest.fixture
def scargo_workflow_params_file():
    """
    Fixture which creates a temporary scargo Python script for subsequent tests
    of the scargo transpiler.  This fixture is `yield`ing since this allows for
    cleanup/teardown after the tests have run.
    """

    source = bytes(
        dedent(
            """
            from scargo.core import WorkflowParams

            workflow_parameters = WorkflowParams(
                {
                    "s3-bucket": "pq-dataxfer-tmp",
                    "input-val": "1",
                    "output-path": "testing/scargo-examples/output",
                }
            )
            """
        ),
        "utf-8",
    )

    with tempfile.NamedTemporaryFile() as tmp:
        tmp.write(source)
        tmp.seek(0)  # go to beginning of file
        yield tmp.name

@pytest.fixture
def check_transpiled_params_file():
    """

    """

    def closure(path_to_scargo_params_file):
        """
        """

        # ensure that the transpilation resulted in a YAML file in the same directory as the Python script
        path_to_scargo_params_file = Path(path_to_scargo_params_file)
        files_in_tmp = list(path_to_scargo_params_file.parent.iterdir())
        new_yaml_params_file = (
            path_to_scargo_params_file.parent / f"{path_to_scargo_params_file.stem.replace('_', '-')}-parameters.yaml"
        )
        assert new_yaml_params_file in files_in_tmp

        # parse the new YAML parameter file and make sure that the content is correct
        with open(new_yaml_params_file, "r") as yaml_in:
            yaml_content = yaml.load(yaml_in)
        expected_workflow_params = {
            "s3-bucket": "pq-dataxfer-tmp",
            "input-val": "1",
            "output-path": "testing/scargo-examples/output",
        }
        assert yaml_content == expected_workflow_params

    return closure