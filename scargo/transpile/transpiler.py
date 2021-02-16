"""
Core functionality of the Python -> Argo YAML transpiler.
"""

import ast
from pathlib import Path
from typing import Dict, Union
import yaml

import astpretty

from scargo.core import WorkflowParams
from scargo.errors import ScargoTranspilerError
from scargo.transpile.utils import ArgoYamlDumper
from scargo.transpile.workflow_step import WorkflowStep


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
                "volumes": [{"name": "workdir", "emptyDir": {}}],
            },
        }

    @staticmethod
    def _get_script_locals(path_to_script: Path) -> Dict:
        """
        Execute the script (without actually running the __main__ function) in
        order to get convenient access to the locals() generated by the script.
        """

        script_locals = {}
        with open(path_to_script, "r") as script:
            exec(script.read(), {}, script_locals)  # no need to keep the globals, everything we need is in the locals

        return script_locals

    def transpile_parameters(self, path_to_script: Path) -> None:
        """
        Retrieves the global workflow parameters from the scargo Python script
        and writes them to YAML.
        """
        script_locals = self._get_script_locals(path_to_script)
        workflow_param_variables = [value for value in script_locals.values() if isinstance(value, WorkflowParams)]

        if not workflow_param_variables:
            raise ScargoTranspilerError("No globally defined WorkflowParams object found.")
        elif len(workflow_param_variables) > 1:
            raise ScargoTranspilerError("Multiple global WorkflowParams objects found. Please only define one.")

        self._write_params_to_yaml(path_to_script, workflow_param_variables[0])
        return workflow_param_variables[0]

    def transpile(self, path_to_script: Path) -> None:
        """
        Convert the script to AST, traverse the tree and transpile the Python
        statements to an Argo workflow.
        """
        self.script_locals = self._get_script_locals(path_to_script)
        workflow_params = self.transpile_parameters(path_to_script)

        # set the Argo workflow name based on the script name
        hyphenated_script_name = path_to_script.stem.replace("_", "-")
        self.transpiled_workflow["metadata"]["generateName"] = f"scargo-{hyphenated_script_name}-"

        # transpile the parameters and write them to a separate YAML
        # as well as include their names in the main YAML workflow file
        self.transpiled_workflow["spec"]["arguments"] = {"parameters": [{"name": name} for name in workflow_params]}

        # parse the AST tree
        with open(path_to_script, "r") as source:
            self.tree = ast.parse(source.read())
        self.visit(self.tree)  # traverse the tree

        # add entrypoint
        self.transpiled_workflow["spec"]["entrypoint"] = self.entrypoint

        # add entrypoint template
        templates = []
        entrypoint_template = {
            "name": self.entrypoint,
            "steps": [
                [
                    {
                        "name": step.hyphenated_name,
                        "template": step.template_name,
                        "arguments": {
                            "parameters": [
                                {
                                    "name": name,
                                    "value": value,
                                }
                                for name, value in step.inputs.parameters.items()
                            ]
                        },
                    }
                    for step in self.steps
                ]
            ],
        }
        templates.append(entrypoint_template)

        # add templates for the individual workflow steps
        for step in self.steps:
            templates.append(step.template)

        # update the transpiled workflow and write to YAML
        self.transpiled_workflow["spec"]["templates"] = templates
        self._write_workflow_to_yaml(path_to_script, self.transpiled_workflow)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """
        Visits all FunctionDef nodes and retrieves:
            - the name of the function with the @entrypoint decorator
            - a list of all workflow steps (one for every expression in the
              @entrypoint-decorated function)

        TODO: only iterate over the top-level nodes
        """

        if isinstance(node.decorator_list[0], ast.Name):
            if node.decorator_list[0].id == "entrypoint":
                self.entrypoint = node.name

                self.steps = []
                for expression in node.body:
                    if isinstance(expression.value, ast.Call):
                        self.steps.append(
                            WorkflowStep(call_node=expression.value, locals_context=self.script_locals, tree=self.tree)
                        )
                        pass

    @staticmethod
    def _write_workflow_to_yaml(path_to_script: Path, transpiled_workflow: Dict) -> None:
        """
        Writes the `transpiled_workflow` to a YAML file in the same directory as the
        original Python input script.
        """

        def repr_str(dumper, data):
            """
            Custom string representation to ensure a leading "|" followed by a
            line break in the source section of the Argo YAML workflow file.
            """
            if "\n" in data:
                return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
            return dumper.org_represent_str(data)

        # back up the default string representer and register the custom one
        ArgoYamlDumper.org_represent_str = ArgoYamlDumper.represent_str
        yaml.add_representer(str, repr_str, Dumper=ArgoYamlDumper)

        filename = f"{path_to_script.stem.replace('_', '-')}.yaml"
        with open(path_to_script.parent / filename, "w+") as yaml_out:
            yaml.dump(transpiled_workflow, yaml_out, Dumper=ArgoYamlDumper, sort_keys=False)

    @staticmethod
    def _write_params_to_yaml(path_to_script: Path, parameters: Dict) -> None:
        """
        Writes the `parameters` to a YAML file in the same directory as the
        original Python input script.
        """

        filename = f"{path_to_script.stem.replace('_', '-')}-parameters.yaml"
        with open(path_to_script.parent / filename, "w+") as yaml_out:
            yaml.dump(dict(parameters), yaml_out)


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
