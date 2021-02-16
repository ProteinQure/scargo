"""
Pytest fixtures used across the test suite.
"""

import tempfile
from textwrap import dedent

import pytest


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
