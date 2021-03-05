"""
Utility functions used in the transpilation process.
"""
import ast
from typing import Any, Dict

from scargo.core import MountPoints, WorkflowParams
from scargo.errors import ScargoTranspilerError
from scargo.transpile.types import Transput, FilePut


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


def resolve_mount_points(node: ast.Subscript, locals_context: Dict[str, Any], tree: ast.Module) -> str:
    """
    Resolves a `node` if the object it refers to is a `MountPoints`
    instance. This requires a few extra steps since `MountPoints` tend to
    be nested objects containing one or several `MountPoint` (singular!)
    objects which in turn can be made up of references to the global
    workflow parameter object.

    # TODO: reduce work by evaluating this structure and working with an actual MountPoints instance,
    # similar to how resolve_workflow_parameter works
    """
    subscripted_object_name = node.value.id
    subscript = node.slice.value.value

    # use the AST to check if this was defined as a string
    for toplevel_node in ast.iter_child_nodes(tree):
        if isinstance(toplevel_node, ast.Assign):
            relevant_target = list(filter(lambda t: t.id == subscripted_object_name, toplevel_node.targets))
            if relevant_target and relevant_target[0].id == subscripted_object_name:

                subscripted_object = get_variable_from_args_or_kwargs(toplevel_node.value, "__dict", 0)
                resolved_node = list(
                    filter(
                        lambda tuple_: tuple_[0].value == subscript,
                        zip(subscripted_object.keys, subscripted_object.values),
                    )
                )[0][1]

                remote_subscript_object = get_variable_from_args_or_kwargs(resolved_node, "remote", 1)
                if is_workflow_param(remote_subscript_object.value.id, locals_context):
                    return resolve_workflow_param(remote_subscript_object, locals_context)


def resolve_subscript(node: ast.Subscript, locals_context: Dict[str, Any], tree: ast.Module) -> str:
    """
    General method that is used to resolve Subscript nodes which typically
    tend to involve the global workflow parameters or mount points.
    """
    subscripted_object_name = node.value.id
    subscript = node.slice.value.value

    if is_workflow_param(subscripted_object_name, locals_context):
        return resolve_workflow_param(node, locals_context)
    elif is_mount_points(subscripted_object_name, locals_context):
        return resolve_mount_points(node, locals_context, tree)
    else:
        # TODO: should this error only be triggered if it also isn't resolvable via the locals of the function?
        raise ScargoTranspilerError(f"Cannot resolve {subscripted_object_name}[{subscript}].")


def resolve_artifact(artifact_node: ast.Call, locals_context: Dict[str, Any], tree: ast.Module) -> FilePut:
    return FilePut(
        root=resolve_subscript(get_variable_from_args_or_kwargs(artifact_node, "root", 0), locals_context, tree),
        path=resolve_subscript(get_variable_from_args_or_kwargs(artifact_node, "path", 1), locals_context, tree),
    )


def resolve_transput(transput_node: ast.Call, locals_context: Dict[str, Any], tree: ast.Module) -> Transput:
    # TODO: use exec to resolve transput as an initial sanity check
    parameters = None
    artifacts = None
    node_args = get_variables_from_args_and_kwargs(transput_node, locals_context)

    if "parameters" in node_args:
        raw_parameters = node_args["parameters"]

        if not isinstance(raw_parameters, ast.Dict):
            raise ScargoTranspilerError("Transputs parameters should be assigned dictionaries.")

        parameters = {}
        for name, value in zip(raw_parameters.keys, raw_parameters.values):
            if not isinstance(name, ast.Constant):
                raise ScargoTranspilerError("Scargo can only transpile constant string dictionary keys.")

            if isinstance(value, ast.Constant):
                parameters[name.value] = value.value
            elif isinstance(value, ast.Subscript):
                parameters[name.value] = resolve_subscript(value, locals_context, tree)
            else:
                raise ScargoTranspilerError("Should be a subscript or a constant?")

        if len(parameters) == 0:
            parameters = None

    if "artifacts" in node_args:
        raw_artifacts = node_args["artifacts"]

        if not isinstance(raw_artifacts, ast.Dict):
            raise ScargoTranspilerError("Transputs parameters should be assigned dictionaries.")

        artifacts = {}
        for name, value in zip(raw_artifacts.keys, raw_artifacts.values):
            if not isinstance(name, ast.Constant):
                raise ScargoTranspilerError("Scargo can only handle constant dictionary keys.")

            if isinstance(value, ast.Constant):
                artifacts[name.value] = value.value
            elif isinstance(value, ast.Call):
                artifacts[name.value] = resolve_artifact(value, locals_context, tree)
            else:
                raise ScargoTranspilerError("Unrecognized assignment for artifact.")

        if len(artifacts) == 0:
            artifacts = None

    if artifacts is None and parameters is None:
        raise ScargoTranspilerError("Empty transput")

    return Transput(parameters=parameters, artifacts=artifacts)
