"""
Core functionality of the Python -> Argo YAML transpiler.
"""

import ast
from pathlib import Path
from typing import Any, Dict, List, Union

from scargo.core import MountPoints, WorkflowParams
from scargo.errors import ScargoTranspilerError
from scargo.transpile import entrypoint, yaml_io
from scargo.transpile.workflow_step import generate_template, WorkflowStep
from scargo.transpile.types import FilePut


def mount_points_from_locals(script_locals: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract remote mount points from the MountPoints defined in Scargo.
    """
    raw_mount_points = [
        {"var": var, "value": value} for var, value in script_locals.items() if isinstance(value, MountPoints)
    ]
    if len(raw_mount_points) == 0:
        raise ScargoTranspilerError("No mount points found.")
    elif len(raw_mount_points) > 1:
        raise ScargoTranspilerError("More than one MountPoints instance found.")
    else:
        return {var: value.remote for var, value in raw_mount_points[0]["value"].items()}


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


def build_step_template(step: WorkflowStep) -> Dict[str, Any]:
    """
    Transpile a WorkflowStep into it's corresponding Argo YAML.

    This involves declaring input parameters and artifacts, as well as optionally defining what condition is required
    for the step to run.
    """
    all_parameters = []

    if step.inputs.parameters is not None:
        for name, param in step.inputs.parameters.items():
            if param.origin is not None:
                all_parameters.append(
                    {
                        "name": name,
                        "value": "{{" + f"steps.exec-{param.origin.step}.outputs.parameters.{param.origin.name}" + "}}",
                    }
                )
            else:
                all_parameters.append(
                    {
                        "name": name,
                        "value": param.value,
                    }
                )

    all_artifacts = []

    if step.inputs.artifacts is not None:
        for name, artifact in step.inputs.artifacts.items():
            if isinstance(artifact, FilePut):
                # TODO: it would be nice if the root was kept as a Workflow Parameter
                all_artifacts.append(
                    {
                        "name": name,
                        "s3": {"endpoint": "s3.amazonaws.com", "bucket": artifact.root, "key": artifact.path},
                    }
                )
            else:
                all_artifacts.append(
                    {
                        "name": name,
                        "from": "{{" + f"steps.{artifact.origin.step}.outputs.artifacts.{artifact.origin.name}" + "}}",
                    }
                )

    all_args = dict()
    if len(all_parameters) > 0:
        all_args["parameters"] = all_parameters

    if len(all_artifacts) > 0:
        all_args["artifacts"] = all_artifacts

    if len(all_parameters) == 0 and len(all_artifacts) == 0:
        raise ScargoTranspilerError(f"No arguments found for step {step}.")

    step_template = {
        "name": step.hyphenated_name,
        "template": step.template_name,
        "arguments": all_args,
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

    entrypoint_groups = []
    for step_group in workflow_steps:
        built_steps = []
        for step in step_group:
            built_steps.append(build_step_template(step))
        entrypoint_groups.append(built_steps)

    entrypoint_template = {
        "name": entrypoint_name,
        "steps": entrypoint_groups,
    }
    templates.append(entrypoint_template)

    # add template implementations for the individual workflow steps
    for step_group in workflow_steps:
        for step in step_group:
            templates.append(generate_template(step))

    # all templates, including the entrypoint, it's corresponding steps and step-implementation templates fall under the
    # spec -> templates fields of an Argo Workflow
    transpiled_workflow["spec"]["templates"] = templates
    return transpiled_workflow


def get_decorator_names(decorator_list: List[ast.expr]) -> List[str]:
    """
    Get names from a function's list of decorators accessed via the `decorator_list` method.

    Parameters
    ----------
    decorator_list : list
        List of all decorators applied to a given function.
    """
    decorator_names = []
    for decor in decorator_list:

        if isinstance(decor, ast.Call):
            decor_func = decor.func
            if isinstance(decor_func, ast.Name):
                decorator_names.append(decor_func.id)

        elif isinstance(decor, ast.Name):
            decorator_names.append(decor.id)

    return decorator_names


def find_entrypoint(tree: ast.Module) -> ast.FunctionDef:
    """
    Search AST of Scargo script for functions marked with @entrypoint.

    There can only be one function marked with entrypoint in valid Scargo script.
    """
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
    mount_points = mount_points_from_locals(script_locals)
    entrypoint_transpiler = entrypoint.EntrypointTranspiler(script_locals, workflow_params, mount_points, tree)
    entrypoint_transpiler.visit(entrypoint_func)

    # transpile the data structures from the previous steps into Argo workflow YAML
    transpiled_workflow = build_template(
        hyphenated_script_name,
        workflow_params,
        entrypoint_name=entrypoint_func.name,
        workflow_steps=entrypoint_transpiler.steps,
    )
    yaml_io.write_workflow_to_yaml(path_to_script, transpiled_workflow)

    print(ast.dump(tree, indent=3))
