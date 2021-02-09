"""
Core functionality of the Python -> Argo YAML transpiler.
"""

import ast
from pathlib import Path
from typing import Dict, Union
import yaml

import astpretty

from scargo.errors import ScargoTranspilerError


class ParameterTranspiler(ast.NodeVisitor):
    """
    Extracts and transpiles the workflow parameters from the scargo Python
    script.
    """

    def transpile(self, path_to_script: Path) -> None:
        """
        Convert the script to AST, traverse the tree, find the instantiation of
        WorkflowParams() to postprocess, write them to a Argo parameter YAML
        file & return the workflow parameters as a Python dictionary.
        """

        with open(path_to_script, "r") as source:
            tree = ast.parse(source.read())

        # traverse only the top-level nodes to find the definition of the WorkflowParams object
        occurences = 0
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign) and node.value.func.id == "WorkflowParams":
                workflow_params_args = node.value.args
                if len(workflow_params_args) != 1:
                    raise ScargoTranspilerError("WorkflowParams should only take one argument!")

                occurences += 1
                param_keys = [k.value for k in workflow_params_args[0].keys]
                param_values = [v.value for v in workflow_params_args[0].values]
                workflow_params = dict(zip(param_keys, param_values))

        if occurences == 0:
            raise ScargoTranspilerError("WorkflowParams object could not be found at the global level.")
        elif occurences > 1:
            raise ScargoTranspilerError("Multiple WorkflowParams objects found. Please only define one.")

        # postprocess the workflow parameters by converting them back to a Python dictionary
        self._write_to_yaml(path_to_script, workflow_params)

        return workflow_params

    @staticmethod
    def _write_to_yaml(path_to_script: Path, parameters: Dict) -> None:
        """
        Writes the `parameters` to a YAML file in the same directory as the
        original Python input script.
        """

        filename = f"{path_to_script.stem.replace('_', '-')}-parameters.yaml"
        with open(path_to_script.parent / filename, "w+") as yaml_out:
            yaml.dump(parameters, yaml_out)


class ScargoTranspiler(ast.NodeVisitor):
    """
    Extracts and transpiles the scargo Python script to an Argo YAML workflow
    file.
    """

    def __init__(self):
        """
        Configures the Argo headers.
        """

        # initialize the transpiled workflow dictionary
        # with the typical Argo header
        self.transpiled_workflow = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Workflow",
            "metadata": {"generateName": None},  # will be defined in self.transpile()
            "spec": {
                "volumes": {"name": "workdir", "emptyDir": {}},
            },
        }

    def transpile(self, path_to_script: Path) -> None:
        """
        Convert the script to AST, traverse the tree and transpile the Python
        statements to an Argo workflow.
        """

        # set the Argo workflow name based on the script name
        hyphenated_script_name = path_to_script.stem.replace("_", "-")
        self.transpiled_workflow["metadata"]["generateName"] = f"scargo-{hyphenated_script_name}-"

        # transpile the parameters and write them to a separate YAML
        # as well as include their names in the main YAML workflow file
        workflow_params = ParameterTranspiler().transpile(path_to_script)
        self.transpiled_workflow["arguments"] = {"parameters": [{"name": name} for name in workflow_params.keys()]}

        # TODO: add entrypoint

        # TODO add step templates

        # TODO: add templates

        # write the workflow to YAML
        self._write_to_yaml(path_to_script, self.transpiled_workflow)

    @staticmethod
    def _write_to_yaml(path_to_script: Path, transpiled_workflow: Dict) -> None:
        """
        Writes the `transpiled_workflow` to a YAML file in the same directory as the
        original Python input script.
        """

        filename = f"{path_to_script.stem.replace('_', '-')}.yaml"
        with open(path_to_script.parent / filename, "w+") as yaml_out:
            yaml.dump(transpiled_workflow, yaml_out, sort_keys=False)


def transpile(path_to_script: Union[str, Path]) -> None:
    """
    Transpiles the `source` (a Python script using the scargo library) to Argo
    YAML via conversion to the Python Abstract Syntax Tree (AST).
    """

    # make sure that the Path is a pathlib object
    path_to_script = Path(path_to_script)

    # transpile the workflow parameters from Python to YAML
    ScargoTranspiler().transpile(path_to_script)

    with open(path_to_script, "r") as source:
        tree = ast.parse(source.read())

    astpretty.pprint(tree, show_offsets=False)
