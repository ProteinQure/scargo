"""
TODO: instead of accessing slices with `node.slice.value` create a utility function to exec them
"""

import ast
from typing import Dict, Any

import astor

from scargo.core import WorkflowParams
from scargo.errors import ScargoTranspilerError
from scargo.transpile.types import Context, FileAny, FileTmp, FilePut, Parameter, Transput
from scargo.transpile.utils import (
    is_workflow_param,
    is_mount_points,
    get_variable_from_args_or_kwargs,
    get_variables_from_args_and_kwargs,
)
from scargo.transpile.workflow_step import WorkflowStep, make_workflow_step


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
                value = "{{" + f"workflow.parameters.{node.slice.value}" + "}}"

    if value is None:
        raise ScargoTranspilerError(f"Cannot resolve parameter value from node type {type(node)}")

    return value


def resolve_mount_points(node: ast.Subscript, mount_points: Dict[str, str]) -> str:
    """
    Resolves a `node` if the object it refers to is a `MountPoints`
    instance.
    """
    subscript = node.slice.value
    return mount_points[subscript]


def resolve_subscript(node: ast.Subscript, context: Context) -> str:
    """
    General method that is used to resolve Subscript nodes which typically
    tend to involve the global workflow parameters or mount points.
    """
    assert isinstance(node, ast.Subscript)

    if is_workflow_param(node, context.locals):
        return resolve_workflow_param(node, context.locals)
    elif is_mount_points(node, context.locals):
        return resolve_mount_points(node, context.mount_points)
    else:
        # TODO: should this error only be triggered if it also isn't resolvable via the locals of the function?
        raise ScargoTranspilerError(f"Cannot resolve {node.value.id}[{node.slice.value}].")


def resolve_artifact(artifact_node: ast.Call, context: Context) -> FileAny:
    """
    Resolve a Transput's artifact initialization into FileTmp and FilePut as an intermediate step before transpilation
    to Argo YAML.
    """
    if artifact_node.func.id == "TmpTransput":
        path = get_variable_from_args_or_kwargs(artifact_node, "name", 0)
        return FileTmp(path=path.value)

    vars = get_variables_from_args_and_kwargs(artifact_node, context.locals)

    root_node = vars["root"]
    if isinstance(root_node, ast.Subscript):
        root = resolve_subscript(root_node, context)
    else:
        raise ScargoTranspilerError("Can only resolve subscripts.")

    path_node = vars["path"]
    if isinstance(path_node, ast.Subscript):
        path = resolve_subscript(path_node, context)

        if "name" in vars:
            name_node = vars["name"]

            if isinstance(name_node, ast.Subscript):
                path = f"{path}/{resolve_subscript(name_node, context)}"
    else:
        raise ScargoTranspilerError("Can only resolve subscripts.")

    return FilePut(root=root, path=path)


def resolve_transput_parameters(raw_parameters: ast.Dict, context: Context) -> Dict[str, Parameter]:
    """
    Resolve a Transput's parameters into a dictionary as an intermediary step before transpilation to Argo YAML.
    """
    parameters = {}
    for name, value in zip(raw_parameters.keys, raw_parameters.values):
        if not isinstance(name, ast.Constant):
            raise ScargoTranspilerError("Scargo can only transpile constant string dictionary keys.")

        if isinstance(value, ast.Constant):
            parameters[name.value] = Parameter(value=value.value, origin=None)
        elif isinstance(value, ast.Subscript):
            subscript = value.value
            sub_slice = value.slice
            if isinstance(subscript, ast.Attribute) and isinstance(sub_slice, ast.Constant):
                assert subscript.attr == "parameters"
                attr_name = subscript.value.id

                if attr_name in context.inputs:
                    context_param = context.inputs[attr_name].parameters[sub_slice.value]
                elif attr_name in context.outputs:
                    context_param = context.outputs[attr_name].parameters[sub_slice.value]
                else:
                    raise ScargoTranspilerError("Only ScargoInput and ScargoOutput work.")

                parameters[name.value] = Parameter(value=context_param.value, origin=context_param.origin)
            else:
                parameters[name.value] = Parameter(value=resolve_subscript(value, context))
        else:
            raise ScargoTranspilerError("Should be a subscript or a constant?")

    return parameters


def resolve_transput_artifacts(raw_artifacts: ast.Dict, context: Context) -> Dict[str, FileAny]:
    """
    Resolve a Transput's artifact into a dictionary mapping artifact names to their associate FilePut or FileTmp.
    """
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

            artifact_name = value.slice.value
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
    """
    Resolve a Scargo Input or Output into a Transput as an intermediate step before transpilation into Argo YAML.
    """
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


def resolve_compare(node: ast.expr, context_locals: Dict[str, Any]) -> str:
    """
    Resolve a variable involved in a comparison.

    TODO: allow for other comparison inputs, such as Transputs and CSV values
    """
    if isinstance(node, ast.Subscript) and is_workflow_param(node, context_locals):
        return resolve_workflow_param(node, context_locals)
    elif isinstance(node, ast.Constant):
        return str(node.value)
    else:
        raise ScargoTranspilerError("Only constants and Workflow allowed in comparison.")


def resolve_cond(node: ast.If, context_locals: Dict[str, Any]) -> str:
    """
    Transpile the condition of an if-statement into an Argo-compatible condition string.

    For example, `workflow_parameters["input-type"] == "alpha"` would be resolved
    into `'{{workflow.parameters.input-type}} == alpha'`

    TODO: determine what operators are supported by Argo
    TODO: support if-statements with multiple conditions/comparisons
    """
    compare = node.test
    if not isinstance(compare, ast.Compare):
        raise NotImplementedError("Only support individual comparisons.")
    elif len(compare.ops) > 1:
        raise NotImplementedError("Only support individual comparisons")

    return " ".join(
        (
            resolve_compare(compare.left, context_locals),
            astor.op_util.get_op_symbol(compare.ops[0]),
            resolve_compare(compare.comparators[0], context_locals),
        )
    )


def resolve_If(node: ast.If, tree: ast.Module, context: Context) -> WorkflowStep:
    """
    Make the resolved condition string and body into a workflow step.

    TODO: support assignments, not just calls
    TODO: support multi-statement bodies
    """
    if len(node.body) > 1:
        raise NotImplementedError("Can't yet handle multi-statement bodies. Only single function-calls are allowed.")

    body = node.body[0]
    if isinstance(body, ast.Expr) and isinstance(body.value, ast.Call):
        condition = resolve_cond(node, context.locals)
        return make_workflow_step(
            call_node=body.value,
            tree=tree,
            context=context,
            condition=condition,
        )
    else:
        raise NotImplementedError("Can only transpile function call inside of conditional statements.")
