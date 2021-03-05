"""
Core functionality of the Python -> Argo YAML transpiler.
"""

import ast
from pathlib import Path
from scargo.transpile.types import Transput
from typing import Any, Dict, List, Union

import astpretty

from scargo.core import WorkflowParams
from scargo.transpile.workflow_step import WorkflowStep
from scargo.errors import ScargoTranspilerError
from scargo.transpile import entrypoint, yaml_io


def transpile_workflow_parameters(script_locals: Dict[str, Any]) -> WorkflowParams:
    """
    Retrieves the global workflow parameters from the scargo Python script
    and writes them to YAML.
    """
    workflow_param_variables = [value for value in script_locals.values() if isinstance(value, WorkflowParams)]

    if not workflow_param_variables:
        raise ScargoTranspilerError("No globally defined WorkflowParams object found.")
    elif len(workflow_param_variables) > 1:
        raise ScargoTranspilerError("Multiple global WorkflowParams objects found. Please only define one.")
    else:
        return workflow_param_variables[0]


def get_script_locals(source: str) -> Dict[str, Any]:
    """
    Execute the script (without actually running the __main__ function) in
    order to get convenient access to the locals() generated by the script.
    """

    script_locals = {}
    # globals are currently discarded, since their use in @scargo functions is not yet defined
    exec(source, {}, script_locals)

    return script_locals


def build_step_template(step: WorkflowStep, all_outputs: Dict[str, str]) -> Dict[str, Any]:
    all_parameters = []

    for name, value in step.inputs.parameters.items():
        if isinstance(value, Transput):
            # TODO: step.inputs.parameters -> value should not be a whole Transput?
            prev_step_output = list(value.parameters.keys())
            assert len(prev_step_output) == 1
            prev_step_param = prev_step_output[0]
            all_parameters.append(
                {
                    "name": name,
                    "value": "{{"
                    + f"steps.{all_outputs[prev_step_param]}-compute.outputs.parameters.{prev_step_param}"
                    + "}}",
                }
            )
        else:
            all_parameters.append(
                {
                    "name": name,
                    "value": value,
                }
            )

    step_template = {
        "name": step.hyphenated_name,
        "template": step.template_name,
        "arguments": {"parameters": all_parameters},
    }
    if step.condition is not None:
        step_template["when"] = step.condition

    return step_template


def build_template(
    hyphenated_script_name: str,
    workflow_params: WorkflowParams,
    entrypoint_name: str,
    workflow_steps: List[List[WorkflowStep]],
) -> Dict[str, Any]:
    """
    Convert the script to AST, traverse the tree and transpile the Python
    statements to an Argo workflow.

    # TODO: add whitespace to make output more readable
    """
    # initialize the transpiled workflow dictionary
    # with the typical Argo header
    transpiled_workflow = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Workflow",
        "metadata": {"generateName": f"scargo-{hyphenated_script_name}-"},
        "spec": {
            "entrypoint": entrypoint_name,
            "volumes": [{"name": "workdir", "emptyDir": {}}],
        },
    }

    transpiled_workflow["spec"]["arguments"] = {"parameters": [{"name": name} for name in workflow_params]}

    # add entrypoint and define the corresponding workflow steps templates
    templates = []

    workflow_steps[0][0].inputs
    workflow_steps[0][0].outputs

    all_outputs = dict()

    entrypoint_steps = []
    for step_group in workflow_steps:
        for step in step_group:
            if step.outputs.parameters is not None:
                for output in step.outputs.parameters.keys():
                    all_outputs[output] = step.hyphenated_name

            entrypoint_steps.append(build_step_template(step, all_outputs))

    entrypoint_template = {
        "name": entrypoint_name,
        "steps": [entrypoint_steps],
    }
    templates.append(entrypoint_template)

    # add template implementations for the individual workflow steps
    for step_group in workflow_steps:
        for step in step_group:
            templates.append(step.template)

    # all templates, including the entrypoint, it's corresponding steps and step-implementation templates fall under the
    # spec -> templates fields of an Argo Workflow
    transpiled_workflow["spec"]["templates"] = templates
    return transpiled_workflow


def get_decorator_names(decorator_list: List) -> List[str]:
    decorator_names = []
    for decor in decorator_list:

        if isinstance(decor, ast.Call):
            decor_func = decor.func
            if isinstance(decor_func, ast.Name):
                decorator_names.append(decor_func.id)

        elif isinstance(decor, ast.Name):
            decorator_names.append(decor.id)

    return decorator_names


def find_entrypoint(tree) -> ast.FunctionDef:
    entrypoints = []
    for top_level_node in tree.body:
        if isinstance(top_level_node, ast.FunctionDef):
            if "entrypoint" in get_decorator_names(top_level_node.decorator_list):
                entrypoints.append(top_level_node)

    if len(entrypoints) == 0:
        raise ScargoTranspilerError("no entrypoint!")
    elif len(entrypoints) > 1:
        raise ScargoTranspilerError("too many entrypoint")
    else:
        return entrypoints[0]


def transpile(path_to_script: Union[str, Path]) -> None:
    """
    Transpiles the `source` (a Python script using the scargo library) to Argo
    YAML via conversion to the Python Abstract Syntax Tree (AST).

    Performs transpilation by:
     1. Transpiling the WorkFlow Parameters
     2. Transpiling the EntryPoint function
    """

    path_to_script = Path(path_to_script)
    hyphenated_script_name = path_to_script.stem.replace("_", "-")

    with open(path_to_script, "r") as fi:
        source = fi.read()

    tree = ast.parse(source)

    # parse the workflow parameters and transpile them to a separate YAML file
    script_locals = get_script_locals(source)
    workflow_params = transpile_workflow_parameters(script_locals)
    yaml_io.write_params_to_yaml(path_to_script, workflow_params)

    # parse the entrypoint function and it's corresponding steps into a transpilable format
    entrypoint_func = find_entrypoint(tree)
    entrypoint_transpiler = entrypoint.EntrypointTranspiler(script_locals, tree)
    entrypoint_transpiler.visit(entrypoint_func)

    # transpile the data structures from the previous steps into Argo workflow YAML
    transpiled_workflow = build_template(
        hyphenated_script_name,
        workflow_params,
        entrypoint_name=entrypoint_func.name,
        workflow_steps=entrypoint_transpiler.steps,
    )
    yaml_io.write_workflow_to_yaml(path_to_script, transpiled_workflow)

    astpretty.pprint(tree, show_offsets=False)
