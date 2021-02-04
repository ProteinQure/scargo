"""
Testing the Transpiler classes.
"""

from pathlib import Path

import pytest

from scargo.transpile.transpiler import ParameterTranspiler, transpile


def test_transpile_parameters_only(scargo_workflow_params_file, check_transpiled_params_file):
    """
    Test the standalone transpile() function with a small script that contains
    a definition of workflow parameters only.
    """

    # try to transpile the Python scargo script with the workflow parameters only
    scargo_workflow_params_file = Path(scargo_workflow_params_file)
    transpile(scargo_workflow_params_file)

    check_transpiled_params_file(scargo_workflow_params_file)


class TestParameterTranspiler:
    """
    Testing the transpilation of the workflow parameters.
    """

    @pytest.fixture
    def parameter_transpiler(self):
        """
        Fixture that provides an instance of ParameterTranspiler.
        """

        return ParameterTranspiler()

    def test_transpile(self, parameter_transpiler, scargo_workflow_params_file, check_transpiled_params_file):
        """
        Testing the transpile() method of the ParameterTranspiler with a small
        Python script that only defines workflow parameters.
        """

        # try to transpile the Python scargo script with the workflow parameters only
        scargo_workflow_params_file = Path(scargo_workflow_params_file)
        parameter_transpiler.transpile(scargo_workflow_params_file)

        check_transpiled_params_file(scargo_workflow_params_file)
