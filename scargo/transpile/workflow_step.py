import ast
import copy
from typing import Any, Dict, Optional

import astor

from scargo.errors import ScargoTranspilerError
from scargo.transpile import utils
from scargo.transpile.transformer import SourceToArgoTransformer
from scargo.transpile.types import Transput


class WorkflowStep:
    """
    A single step/template in the workflow.

    Transforms @scargo functions into Argo-compatible workflow functions.

    Specifically, transpile.build_template() uses the properties:
     - `.inputs` and others to provide the Argo template definition
     - `.template` to provide the Argo template implementation

     # TODO: made this class immutable
    """

    def __init__(
        self, call_node: ast.Call, tree: ast.Module, context_inputs, context_outputs, condition: Optional[str] = None
    ) -> None:
        """
        Create a new WorkflowStep.

        Parameters
        ----------
        call_node : ast.Call
            The Call node that invokes this workflow step. In other words the
            Call node which calls the @scargo decorated function in the
            @entrypoint function.
        locals_context : Dict
            The locals() context resulting from `exec`uting the Python scargo
            script. Should contain all the global imports, variables and
            function definitions.
        tree : ast.Module
            The entire (!) Abstract Syntax Tree of the Python scargo script.
        """
        self.call_node = call_node
        self.context_inputs = context_inputs
        self.context_outputs = context_outputs
        # TODO: the context extracted from the tree should be passed as an argument, instead of processed in this class
        self.tree = tree
        self.condition = condition

    @property
    def name(self) -> str:
        """
        Returns the name of the workflow step.
        """
        return self.call_node.func.id

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
        return f"{self.hyphenated_name}-template"

    @property
    def image(self) -> str:
        """
        Returns the Docker image that this workflow step is supposed to be
        executed in.
        """
        scargo_decorator_node = list(filter(lambda d: d.func.id == "scargo", self.functiondef_node.decorator_list))[0]
        assert isinstance(scargo_decorator_node, ast.Call)
        return utils.get_variable_from_args_or_kwargs(scargo_decorator_node, "image", 0).value

    @property
    def functiondef_node(self) -> Optional[ast.FunctionDef]:
        """
        Returns the FunctionDef node which represents the definition of the
        Python function corresponding to this workflow step.
        """
        for toplevel_node in ast.iter_child_nodes(self.tree):
            if isinstance(toplevel_node, ast.FunctionDef) and toplevel_node.name == self.name:
                return toplevel_node

    @property
    def source_code(self) -> Optional[str]:
        """
        Returns the source code for this workflow step.
        """

        if self.functiondef_node is None:
            return None

        # Get the names of the ScargoInput/ScargoOutput arguments.
        # In the docs, it is required the first argument to be ScargoInput and the
        # second to be ScargoOutput
        # TODO: check argument types, instead of assuming
        # https://gitlab.proteinqure.com/pq/platform/core/scargo/-/issues/19
        input_arg_name = self.functiondef_node.args.args[0].arg
        output_arg_name = self.functiondef_node.args.args[1].arg

        # Resolves f-strings with WorkflowParams/MountPoints
        converted_functiondef = SourceToArgoTransformer(input_arg_name, output_arg_name).visit(
            copy.deepcopy(self.functiondef_node)
        )

        # TODO: format the output source with black
        # https://gitlab.proteinqure.com/pq/platform/core/scargo/-/issues/20
        source = []
        for node in converted_functiondef.body:
            if not isinstance(node, ast.Expr):  # if it's not a docstring
                source.append(astor.to_source(node))

        return "".join(source)

    @property
    def inputs(self) -> Transput:
        """
        Parses the input parameters and artifacts from the workflow step and
        returns them as a Transput object (which has a `parameters` and an
        `artifacts` attribute for easy access.

        TODO: inputs and outputs use similar logic
        TODO: do this on initialization instead of when called
        """
        input_node = utils.get_variable_from_args_or_kwargs(self.call_node, "scargo_in", 0)

        if isinstance(input_node, ast.Call) and input_node.func.id == "ScargoInput":
            # TODO: somehow exec the call node
            scargo_input = Transput()
        elif isinstance(input_node, ast.Name) and isinstance(self.context_inputs[input_node.id], Transput):
            scargo_input = self.context_inputs[input_node.id]
        else:
            raise ScargoTranspilerError(
                "Unexpected input type. First argument to a @scargo function must be a `ScargoInput`."
            )

        return scargo_input

    @property
    def outputs(self) -> Transput:
        """
        Parses the input parameters and artifacts from the workflow step and
        returns them as a Transput object (which has a `parameters` and an
        `artifacts` attribute for easy access.
        """
        output_node = utils.get_variable_from_args_or_kwargs(self.call_node, "scargo_out", 1)
        if isinstance(output_node, ast.Call) and output_node.func.id == "ScargoOutput":
            # TODO: somehow exec the call node
            scargo_output = Transput()
        elif isinstance(output_node, ast.Name) and isinstance(self.context_outputs[output_node.id], Transput):
            scargo_output = self.context_outputs[output_node.id]
        else:
            raise ScargoTranspilerError(
                "Unexpected input type. Second argument to a @scargo function must be a `ScargoOutput`."
            )

        return scargo_output

    @property
    def template(self) -> Dict[str, Any]:
        """
        Returns the dictionary defining the Argo template for this workflow
        step.
        """

        template: Dict[str, Any] = {"name": self.template_name}

        inputs_section = {"inputs": dict()}
        if self.inputs.parameters is not None:
            inputs_section["inputs"]["parameters"] = [{"name": key} for key in self.inputs.parameters]
        if self.inputs.artifacts is not None:
            # TODO: that's not how an input artifact works
            inputs_section["inputs"]["artifacts"] = [
                dict({"name": name, "path": f"/workdir/in/{file_input.name}"})
                for name, file_input in self.inputs.artifacts.items()
            ]
        template.update(inputs_section)

        outputs_section = {"outputs": dict()}
        if self.outputs.parameters is not None:
            outputs_section["outputs"]["parameters"] = [{"name": key} for key in self.outputs.parameters]
        if self.outputs.artifacts is not None:
            outputs_section["outputs"]["artifacts"] = [
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
                for name, file_output in self.outputs.artifacts.items()
            ]
        template.update(outputs_section)

        template.update(
            {
                "initContainers": [
                    {
                        "name": "mkdir",
                        "image": "alpine:latest",
                        "command": ["mkdir", "-p", "/workdir/out"],
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
                    "image": self.image,
                    "command": ["python"],  # TODO: needs to be dynamic
                    "source": self.source_code,
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
