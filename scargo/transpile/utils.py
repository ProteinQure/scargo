"""
Utility functions used in the transpilation process.

TODO: instead of accessing slices with `node.slice.value.value` create a utility function to exec them
"""
import ast
import functools
from typing import Any, Dict, List

import astpretty

from scargo.core import MountPoints, WorkflowParams
from scargo.errors import ScargoTranspilerError
from scargo.transpile.types import Context, FileAny, Transput, FilePut, FileTmp


# used when debugging
astpp = functools.partial(astpretty.pprint, show_offsets=False)


def hyphenate(text: str) -> str:
    """
    Converts underscores to hyphens.

    Python functions use underscores while Argo uses hyphens for Argo template names by convention.
    """
    return text.replace("_", "-")


def is_workflow_param(object_name: str, locals_context: Dict[str, Any]) -> bool:
    """
    Checks if the `object_name` is a global WorkflowParams object.

    TODO: this should take an ast.Subscript instead of a str
    """
    return object_name in locals_context and isinstance(locals_context[object_name], WorkflowParams)


def is_mount_points(object_name: str, locals_context: Dict[str, Any]) -> bool:
    """
    Checks if the `object_name` is a global MountPoints object.
    """
    return object_name in locals_context and isinstance(locals_context[object_name], MountPoints)


def get_variables_from_args_and_kwargs(node: ast.Call, locals_context: Dict[str, ast.expr]) -> Dict[str, ast.expr]:
    # TODO: call exec on this node and log whatever errors happen instead of trying to manually determine errors

    all_vars = dict()
    klass = locals_context[node.func.id]
    # proceeding assuming the parameters are assigned correctly
    # TODO: actually assign args later, lol

    for keyword in node.keywords:
        all_vars[keyword.arg] = keyword.value

    return all_vars


def get_variables_from_call(node: ast.Call, expected_args: List[str] = None) -> Dict[str, ast.expr]:
    all_vars = dict()

    for a_i, arg in enumerate(node.args):
        all_vars[expected_args[a_i]] = arg

    for keyword in node.keywords:
        all_vars[keyword.arg] = keyword.value

    return all_vars


def get_variable_from_args_or_kwargs(node: ast.Call, variable_name: str, arg_index: int) -> ast.expr:
    """
    We don't know if the user has passed a positional or a keyworded
    argument to `node` which result in different ASTs. Since this is a
    common occurence, this method figures it out for you and returns the
    node representing the variable.
    """
    if node.args and len(node.args) > arg_index:
        return node.args[arg_index]
    elif node.keywords:
        filtered_keywords = list(filter(lambda k: k.arg == variable_name, node.keywords))
        if filtered_keywords:
            return filtered_keywords[0].value

    raise ScargoTranspilerError(f"Can't parse {variable_name} from {node.func.id}.")


def resolve_workflow_param(node: ast.Subscript, locals_context: Dict[str, Any]) -> str:
    """
    Given a Subscript or Constant node use the
    locals_context of the scargo script and the AST to transpile this node
    either into the actual parameter value or into a reference to the
    global Argo workflow parameters.
    """

    value = None
    if isinstance(node, ast.Subscript):
        # could be a list, tuple or dict
        subscripted_object = node.value.id
        if subscripted_object in locals_context:
            if isinstance(locals_context[subscripted_object], WorkflowParams):
                value = "{{" + f"workflow.parameters.{node.slice.value.value}" + "}}"

    if value is None:
        raise ScargoTranspilerError(f"Cannot resolve parameter value from node type {type(node)}")

    return value


def resolve_mount_points(node: ast.Subscript, context: Context) -> str:
    """
    Resolves a `node` if the object it refers to is a `MountPoints`
    instance.
    """
    subscript = node.slice.value.value
    return context.mount_points[subscript]


def resolve_subscript(node: ast.Subscript, context: Context) -> str:
    """
    General method that is used to resolve Subscript nodes which typically
    tend to involve the global workflow parameters or mount points.
    """
    assert isinstance(node, ast.Subscript)
    subscripted_object_name = node.value.id
    subscript = node.slice.value.value

    if is_workflow_param(subscripted_object_name, context.locals):
        return resolve_workflow_param(node, context.locals)
    elif is_mount_points(subscripted_object_name, context.locals):
        return resolve_mount_points(node, context)
    else:
        # TODO: should this error only be triggered if it also isn't resolvable via the locals of the function?
        raise ScargoTranspilerError(f"Cannot resolve {subscripted_object_name}[{subscript}].")


def resolve_artifact(artifact_node: ast.Call, context: Context) -> FileAny:
    if artifact_node.func.id == "TmpTransput":
        path = get_variable_from_args_or_kwargs(artifact_node, "name", 0)
        return FileTmp(path=path.value)

    root_node = get_variable_from_args_or_kwargs(artifact_node, "root", 0)
    if isinstance(root_node, ast.Subscript):
        root = resolve_subscript(root_node, context)
    else:
        raise ScargoTranspilerError("Can only resolve subscripts.")

    path_node = get_variable_from_args_or_kwargs(artifact_node, "path", 1)
    if isinstance(path_node, ast.Subscript):
        path = resolve_subscript(path_node, context)
    else:
        raise ScargoTranspilerError("Can only resolve subscripts.")

    return FilePut(root=root, path=path)


def resolve_transput_parameters(raw_parameters: ast.Dict, context: Context) -> Dict[str, str]:
    parameters = {}
    for name, value in zip(raw_parameters.keys, raw_parameters.values):
        if not isinstance(name, ast.Constant):
            raise ScargoTranspilerError("Scargo can only transpile constant string dictionary keys.")

        if isinstance(value, ast.Constant):
            parameters[name.value] = value.value
        elif isinstance(value, ast.Subscript):
            subscript = value.value
            if isinstance(subscript, ast.Attribute):
                assert subscript.attr == "parameters"
                attr_name = subscript.value.id
                if attr_name in context.inputs:
                    parameters[name.value] = context.inputs[attr_name]
                elif attr_name in context.outputs:
                    parameters[name.value] = context.outputs[attr_name]
                else:
                    raise ScargoTranspilerError("Only ScargoInput and ScargoOutput work.")
            else:
                parameters[name.value] = resolve_subscript(value, context)
        else:
            raise ScargoTranspilerError("Should be a subscript or a constant?")

    return parameters


def resolve_transput_artifacts(raw_artifacts: ast.Dict, context: Context) -> Dict[str, FileAny]:
    artifacts = {}
    for name, value in zip(raw_artifacts.keys, raw_artifacts.values):
        if not isinstance(name, ast.Constant):
            raise ScargoTranspilerError("Scargo can only handle constant dictionary keys.")

        if isinstance(value, ast.Constant):
            artifacts[name.value] = value.value
        elif isinstance(value, ast.Call):
            artifacts[name.value] = resolve_artifact(value, context)
        elif isinstance(value, ast.Subscript):
            attribute = value.value
            assert isinstance(attribute, ast.Attribute)
            assert attribute.attr == "artifacts"
            root = attribute.value.id

            # TODO: find more generic way to resolve slices. Probably evaluating them?
            artifact_name = value.slice.value.value
            if root in context.inputs:
                artifacts[name.value] = context.inputs[root].artifacts[artifact_name]
            elif root in context.outputs:
                artifacts[name.value] = context.outputs[root].artifacts[artifact_name]
            else:
                raise ScargoTranspilerError(
                    "Transput (probably TmpTransput) not found in previous input or output artifacts."
                )
        else:
            raise ScargoTranspilerError("Unrecognized assignment for artifact.")

    return artifacts


def resolve_transput(transput_node: ast.Call, context: Context) -> Transput:
    # TODO: use exec to resolve transput as an initial sanity check
    parameters = None
    artifacts = None
    node_args = get_variables_from_args_and_kwargs(transput_node, context.locals)

    if "parameters" in node_args:
        raw_parameters = node_args["parameters"]

        if not isinstance(raw_parameters, ast.Dict):
            raise ScargoTranspilerError("Transputs parameters should be assigned dictionaries.")

        parameters = resolve_transput_parameters(raw_parameters, context)

        if len(parameters) == 0:
            parameters = None

    if "artifacts" in node_args:
        raw_artifacts = node_args["artifacts"]

        if not isinstance(raw_artifacts, ast.Dict):
            raise ScargoTranspilerError("Transputs parameters should be assigned dictionaries.")

        artifacts = resolve_transput_artifacts(raw_artifacts, context)

        if len(artifacts) == 0:
            artifacts = None

    if artifacts is None and parameters is None:
        raise ScargoTranspilerError("Empty transput")

    return Transput(parameters=parameters, artifacts=artifacts)
