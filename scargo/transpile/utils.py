"""
Utility functions used in the transpilation process.
"""
import ast
from typing import Any, Dict, List

from scargo.core import MountPoints, WorkflowParams


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
