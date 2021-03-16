"""
Utility functions used in the transpilation process.
"""
import ast
from typing import Any, Dict, List

from scargo.core import MountPoints, WorkflowParams
from scargo.errors import ScargoTranspilerError


def hyphenate(text: str) -> str:
    """
    Converts underscores to hyphens.

    Python functions use underscores while Argo uses hyphens for Argo template names by convention.
    """
    return text.replace("_", "-")


def is_workflow_param(node: ast.Subscript, locals_context: Dict[str, Any]) -> bool:
    """
    Checks if the subscripted node is a global WorkflowParams object.
    """
    object_name = node.value.id
    return object_name in locals_context and isinstance(locals_context[object_name], WorkflowParams)


def is_mount_points(node: ast.Subscript, locals_context: Dict[str, Any]) -> bool:
    """
    Checks if the subscripted node is a global MountPoints object.
    """
    object_name = node.value.id
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
    """
    Get all args and kwargs from a function call node.
    """
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
