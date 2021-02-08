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

    def _check_for_workflow_params(self) -> None:
        """
        Check if this class has a 'ast_workflow_params' attribute which should
        be present after traversing the AST if the scargo script defines a
        WorkflowParams object.
        """

        if not getattr(self, "ast_workflow_params", False):
            raise ScargoTranspilerError("Please create a global WorkflowParams instance in your scargo script.")

    def transpile(self, path_to_script: Path) -> None:
        """
        Convert the script to AST, traverse the tree, find the instantiation of WorkflowParams() to
        postprocess & return the workflow parameters as a Python dictionary.
        """

        with open(path_to_script, "r") as source:
            tree = ast.parse(source.read())

        # recursively traverse the tree to find the definition of the WorkflowParams object
        self.visit(tree)
        self._check_for_workflow_params()

        # postprocess the workflow parameters by converting them back to a Python dictionary
        param_keys = [k.value for k in self.ast_workflow_params[0].keys]
        param_values = [v.value for v in self.ast_workflow_params[0].values]
        self._write_to_yaml(path_to_script, dict(zip(param_keys, param_values)))

    def visit_Call(self, node: ast.Call) -> None:
        """
        Visits every Call `node` in the tree and tries to find where in the
        script the user defined the WorkflowParams. Returning the `node.args`
        doesn't makes sense since there might be other Call nodes left to visit
        after this one. Therefore, we assign it to a class attribute that we
        can postprocess later.
        """

        if type(node.func) == ast.Name and node.func.id == "WorkflowParams":
            print(f"WorkflowParams are instantiated on line {node.lineno}")
            self.ast_workflow_params = node.args

    @staticmethod
    def _write_to_yaml(path_to_script: Path, parameters: Dict) -> None:
        """
        Writes the `parameters` to a YAML file in the same directory as the
        original Python input script.
        """

        filename = f"{path_to_script.stem.replace('_', '-')}-parameters.yaml"
        with open(path_to_script.parent / filename, "w+") as yaml_out:
            yaml.dump(parameters, yaml_out)


def transpile(path_to_script: Union[str, Path]) -> None:
    """
    Converts the `source` (usually a Python script) to a Python Abstract Syntax
    Tree (AST).
    """

    # make sure that the Path is a pathlib object
    path_to_script = Path(path_to_script)

    # transpile the workflow parameters from Python to YAML
    ParameterTranspiler().transpile(path_to_script)

    with open(path_to_script, "r") as source:
        tree = ast.parse(source.read())

    astpretty.pprint(tree, show_offsets=False)
