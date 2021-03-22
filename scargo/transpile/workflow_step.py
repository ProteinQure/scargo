import ast
import copy
from typing import Any, Dict, NamedTuple, Optional

import astor

from scargo.errors import ScargoTranspilerError
from scargo.transpile import resolve, utils
from scargo.transpile.transformer import SourceToArgoTransformer
from scargo.transpile.types import Context, FilePut, FileTmp, Origin, Parameter, Transput


class WorkflowStep(NamedTuple):
    """
    Representation of Scargo Workflow step for transpilation into Argo YAML.
    """

    call_node: ast.Call
    name: str
    image: str
    inputs: Transput
    outputs: Transput
    functiondef_node: ast.FunctionDef
    condition: Optional[str] = None

    @property
    def hyphenated_name(self) -> str:
        """
        Returns the name of the workflow step.
        """
        return utils.hyphenate(self.name)

    @property
    def template_name(self) -> str:
        """
        Returns the template name of the workflow step.
        """
        return f"exec-{self.hyphenated_name}"


def get_functiondef_node(name: str, tree: ast.Module) -> Optional[ast.FunctionDef]:
    """
    Returns the FunctionDef node which represents the definition of the
    Python function corresponding to this workflow step.
    """
    for toplevel_node in ast.iter_child_nodes(tree):
        if isinstance(toplevel_node, ast.FunctionDef) and toplevel_node.name == name:
            return toplevel_node


def get_inputs(call_node: ast.Call, context: Context) -> Transput:
    """
    Parses the input parameters and artifacts from the workflow step and
    returns them as a Transput object (which has a `parameters` and an
    `artifacts` attribute for easy access.

    TODO: get_inputs and get_outputs use similar logic
    """
    input_node = utils.get_variables_from_call(call_node, ["scargo_in", "scargo_out"])["scargo_in"]

    if isinstance(input_node, ast.Call) and input_node.func.id == "ScargoInput":
        scargo_inputs = resolve.resolve_transput(input_node, context)
    elif isinstance(input_node, ast.Name) and isinstance(context.inputs[input_node.id], Transput):
        scargo_inputs = context.inputs[input_node.id]
    else:
        raise ScargoTranspilerError(
            "Unexpected input type. First argument to a @scargo function must be a `ScargoInput`."
        )

    return scargo_inputs


def get_outputs(call_node: ast.Call, context: Context, name: str) -> Transput:
    """
    Parses the output parameters and artifacts from the workflow step and
    returns them as a Transput object (which has a `parameters` and an
    `artifacts` attribute for easy access.
    """
    output_node = utils.get_variables_from_call(call_node, ["scargo_in", "scargo_out"])["scargo_out"]

    if isinstance(output_node, ast.Call) and output_node.func.id == "ScargoOutput":
        scargo_outputs = resolve.resolve_transput(output_node, context)
    elif isinstance(output_node, ast.Name) and isinstance(context.outputs[output_node.id], Transput):
        scargo_outputs = context.outputs[output_node.id]

        if scargo_outputs.parameters is not None:
            param_update = dict()
            for key, param in scargo_outputs.parameters.items():
                param_update[key] = Parameter(value=param.value, origin=Origin(step=name, name=key))

            scargo_outputs.parameters.update(param_update)

        if scargo_outputs.artifacts is not None:
            artifact_update = dict()
            for key, artifact in scargo_outputs.artifacts.items():
                if isinstance(artifact, FileTmp):
                    if artifact.origin is not None:
                        raise ScargoTranspilerError(
                            f"Assigning a TmpFile as output for {name}, but it's already been used as an output for"
                            f"step {artifact.origin.step}"
                        )

                    artifact_update[key] = FileTmp(path=artifact.path, origin=Origin(step=name, name=key))

            scargo_outputs.artifacts.update(artifact_update)
    else:
        raise ScargoTranspilerError(
            "Unexpected input type. Second argument to a @scargo function must be a `ScargoOutput`."
        )

    return scargo_outputs


def get_image(functiondef_node: ast.FunctionDef) -> str:
    """
    Get image argument from @scargo(image=image_name)
    """
    scargo_decorator_node = list(filter(lambda d: d.func.id == "scargo", functiondef_node.decorator_list))[0]
    assert isinstance(scargo_decorator_node, ast.Call)
    image_node = utils.get_variables_from_call(scargo_decorator_node, ["image"])["image"]
    assert isinstance(image_node, ast.Constant)
    return image_node.value


def make_workflow_step(
    call_node: ast.Call,
    tree: ast.Module,
    context: Context,
    condition: Optional[str] = None,
) -> WorkflowStep:
    """
    WorkflowStep contructor.

    Since NamedTuples can't use constructors and @dataclass doesn't like modifying attributes in __post_init__
    if frozen=True.
    """

    name = call_node.func.id
    functiondef_node = get_functiondef_node(name, tree)
    if functiondef_node is None:
        raise ScargoTranspilerError(f"No function definition found for name: {name}")

    return WorkflowStep(
        call_node=call_node,
        name=name,
        image=get_image(functiondef_node),
        inputs=get_inputs(call_node, context),
        outputs=get_outputs(call_node, context, utils.hyphenate(name)),
        functiondef_node=functiondef_node,
        condition=condition,
    )


def source_code(step: WorkflowStep) -> Optional[str]:
    """
    Returns the source code for this workflow step.
    """

    # Get the names of the ScargoInput/ScargoOutput arguments.
    # In the docs, it is required the first argument to be ScargoInput and the
    # second to be ScargoOutput
    # TODO: check argument types, instead of assuming
    # https://gitlab.proteinqure.com/pq/platform/core/scargo/-/issues/19
    function_args = step.functiondef_node.args.args
    input_arg_name = function_args[0].arg
    output_arg_name = function_args[1].arg

    # Resolves f-strings with WorkflowParams/MountPoints
    converted_functiondef = SourceToArgoTransformer(input_arg_name, step.inputs, output_arg_name, step.outputs).visit(
        copy.deepcopy(step.functiondef_node)
    )

    # TODO: format the output source with black
    # https://gitlab.proteinqure.com/pq/platform/core/scargo/-/issues/20
    source = []
    for node in converted_functiondef.body:
        if not isinstance(node, ast.Expr):  # if it's not a docstring
            source.append(astor.to_source(node))

    return "".join(source)


def generate_template(step: WorkflowStep) -> Dict[str, Any]:
    """
    Returns the dictionary defining the Argo template for this workflow
    step.
    """

    template: Dict[str, Any] = {"name": step.template_name}

    inputs_section = {"inputs": dict()}

    if step.inputs.parameters is not None:
        inputs_section["inputs"]["parameters"] = [{"name": key} for key in step.inputs.parameters]

    if step.inputs.artifacts is not None:
        inputs_section["inputs"]["artifacts"] = [
            dict({"name": name, "path": f"/workdir/in/{name}"}) for name in step.inputs.artifacts
        ]

    template.update(inputs_section)

    outputs_section = {"outputs": dict()}

    if step.outputs.parameters is not None:
        outputs_section["outputs"]["parameters"] = [
            {"name": name, "valueFrom": {"path": f"/workdir/out/{name}"}} for name in step.outputs.parameters
        ]

    if step.outputs.artifacts is not None:
        artifacts = []
        for name, file_output in step.outputs.artifacts.items():
            if isinstance(file_output, FilePut):
                artifacts.append(
                    dict(
                        {
                            "name": name,
                            "path": "/workdir/out",
                            "s3": {
                                "endpoint": "s3.amazonaws.com",
                                "bucket": file_output.root,
                                "key": file_output.path,
                            },
                        }
                    )
                )
            elif isinstance(file_output, FileTmp):
                artifacts.append(
                    dict(
                        {
                            "name": name,
                            "path": f"/workdir/out/{name}",
                        }
                    )
                )
            else:
                raise ScargoTranspilerError("Only FilPut and FileTmp supported.")

        outputs_section["outputs"]["artifacts"] = artifacts

    template.update(outputs_section)

    template.update(
        {
            "initContainers": [
                {
                    "name": "mkdir",
                    "image": "alpine:latest",
                    "command": ["mkdir", "-p", "/workdir/out", "/workdir/in"],
                    "mirrorVolumeMounts": True,
                },
                {
                    "name": "chmod",
                    "image": "alpine:latest",
                    "command": ["chmod", "-R", "a+rwX", "/workdir"],
                    "mirrorVolumeMounts": True,
                },
            ],
            "script": {
                "image": step.image,
                "command": ["python"],  # TODO: needs to be dynamic
                "source": source_code(step),
                "resources": {
                    "requests": {
                        "memory": "30Mi",
                        "cpu": "20m",
                    },
                    "limits": {
                        "memory": "30Mi",
                        "cpu": "20m",
                    },
                },
                "volumeMounts": [{"name": "workdir", "mountPath": "/workdir"}],  # TODO: only include if needed
            },
        }
    )

    return template
