import ast
import copy
from typing import Any, Dict, Optional, Union

import astor

from scargo.core import MountPoints, WorkflowParams
from scargo.errors import ScargoTranspilerError
from scargo.transpile.utils import hyphenate, SourceToArgoTransformer, Transput


class WorkflowStep:
    """
    A single step/template in the workflow.
    """

    def __init__(self, call_node: ast.Call, locals_context: Dict, tree: ast.Module) -> None:
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
        self.locals_context = locals_context
        self.tree = tree

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
        return hyphenate(self.name)

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
        return self._get_variable_from_args_or_kwargs(scargo_decorator_node, "image", 0).value

    @property
    def functiondef_node(self) -> Optional[ast.FunctionDef]:
        """
        Returns the FunctionDef node which represents the definition of the
        Python function corresponding to this workflow step.
        """
        for toplevel_node in ast.iter_child_nodes(self.tree):
            if isinstance(toplevel_node, ast.FunctionDef) and toplevel_node.name == self.name:
                return toplevel_node

    @staticmethod
    def _get_variable_from_args_or_kwargs(
        node: ast.Call, variable_name: str, arg_index: int
    ) -> Union[ast.keyword, ast.Dict]:
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
        else:
            raise ScargoTranspilerError(f"Can't parse {variable_name} from {node.func.id}.")

    def _resolve_workflow_param(self, node: ast.Subscript) -> str:
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
            if subscripted_object in self.locals_context:
                if isinstance(self.locals_context[subscripted_object], WorkflowParams):
                    value = "{{" + f"workflow.parameters.{node.slice.value.value}" + "}}"

        if value is None:
            raise ScargoTranspilerError(f"Cannot resolve parameter value from node type {type(node)}")

        return value

    def _is_workflow_param(self, object_name: str) -> bool:
        """
        Checks if the `object_name` is a global WorkflowParams object.
        """
        if object_name in self.locals_context:
            if isinstance(self.locals_context[object_name], WorkflowParams):
                return True
        return False

    def _is_mount_points(self, object_name: str) -> bool:
        """
        Checks if the `object_name` is a global MountPoints object.
        """
        if object_name in self.locals_context:
            if isinstance(self.locals_context[object_name], MountPoints):
                return True
        return False

    def _resolve_mount_points(self, node: ast.Subscript) -> str:
        """
        Resolves a `node` if the object it refers to is a `MountPoints`
        instance. This requires a few extra steps since `MountPoints` tend to
        be nested objects containing one or several `MountPoint` (singular!)
        objects which in turn can be made up of references to the global
        workflow parameter object.
        """
        subscripted_object_name = node.value.id
        subscript = node.slice.value.value

        # use the AST to check if this was defined as a string
        for toplevel_node in ast.iter_child_nodes(self.tree):
            if isinstance(toplevel_node, ast.Assign):
                relevant_target = list(filter(lambda t: t.id == subscripted_object_name, toplevel_node.targets))
                if relevant_target and relevant_target[0].id == subscripted_object_name:

                    subscripted_object = self._get_variable_from_args_or_kwargs(toplevel_node.value, "__dict", 0)
                    resolved_node = list(
                        filter(
                            lambda tuple_: tuple_[0].value == subscript,
                            zip(subscripted_object.keys, subscripted_object.values),
                        )
                    )[0][1]

                    remote_subscript_object = self._get_variable_from_args_or_kwargs(resolved_node, "remote", 1)
                    if self._is_workflow_param(remote_subscript_object.value.id):
                        return self._resolve_workflow_param(remote_subscript_object)

        raise ScargoTranspilerError(f"Cannot resolve mount point {subscripted_object_name}[{subscript}]")

    def _resolve_subscript(self, node: ast.Subscript) -> str:
        """
        General method that is used to resolve Subscript nodes which typically
        tend to involve the global workflow parameters or mount points.
        """
        subscripted_object_name = node.value.id
        subscript = node.slice.value.value

        if self._is_workflow_param(subscripted_object_name):
            return self._resolve_workflow_param(node)
        elif self._is_mount_points(subscripted_object_name):
            return self._resolve_mount_points(node)
        else:
            raise ScargoTranspilerError(f"Cannot resolve {subscripted_object_name}[{subscript}].")

    def _transpile_artifact(self, raw_artifact: Union[ast.Constant, ast.Call], output: bool) -> Dict[str, Any]:
        """
        Given a Call and Constant node (`raw_artifact`) this method uses the
        locals_context of the scargo script and the AST to transpile this node
        either into the actual artifact value or into a reference to the global
        Argo workflow parameters.
        """

        artifact = None
        if isinstance(raw_artifact, ast.Call) and raw_artifact.func.id == "FileOutput":

            root = self._resolve_subscript(self._get_variable_from_args_or_kwargs(raw_artifact, "root", 0))
            path = self._resolve_subscript(self._get_variable_from_args_or_kwargs(raw_artifact, "path", 1))

            artifact = {
                "path": "/workdir/out" if output else "/workdir/in",
                "archive": {
                    "none": {},
                },
                "s3": {
                    "endpoint": "s3.amazonaws.com",
                    "bucket": root,
                    "key": path,
                },
            }

        if artifact is None:
            raise ScargoTranspilerError(
                f"Cannot resolve artifact {raw_artifact.func.id} from node type {type(raw_artifact)}"
            )

        return artifact

    @property
    def source_code(self) -> str:
        """
        Returns the source code for this workflow step.
        """

        # get the names of the ScargoInput/ScargoOutput arguments
        # in the docs, we demand the first argument to be ScargoInput and the
        # second to be ScargoOutput
        input_arg_name = self.functiondef_node.args.args[0].arg
        output_arg_name = self.functiondef_node.args.args[1].arg

        # write a general function that resolves f-strings with WorkflowParams/MountPoints
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
        """
        scargo_inputs = self._get_variable_from_args_or_kwargs(self.call_node, "scargo_in", 0)
        if scargo_inputs.func.id != "ScargoInput":
            raise ScargoTranspilerError("First argument to a @scargo function must be a `ScargoInput`.")

        raw_parameters = self._get_variable_from_args_or_kwargs(scargo_inputs, "parameters", 0)
        parameters = {}
        if raw_parameters:
            for key, value in zip(raw_parameters.keys, raw_parameters.values):
                parameters[key.value] = self._resolve_workflow_param(value)

        raw_artifacts = self._get_variable_from_args_or_kwargs(scargo_inputs, "artifacts", 1)
        artifacts = {}
        if raw_artifacts:
            for key, raw_artifact in zip(raw_artifacts.keys, raw_artifacts.values):
                artifacts[key.value] = self._transpile_artifact(raw_artifact, output=False)

        return Transput(parameters=parameters, artifacts=artifacts)

    @property
    def outputs(self) -> Transput:
        """
        Parses the input parameters and artifacts from the workflow step and
        returns them as a Transput object (which has a `parameters` and an
        `artifacts` attribute for easy access.
        """
        scargo_outputs = self._get_variable_from_args_or_kwargs(self.call_node, "scargo_out", 1)
        if scargo_outputs.func.id != "ScargoOutput":
            raise ScargoTranspilerError("Second argument to a @scargo function must be a `ScargoOutput`.")

        raw_parameters = self._get_variable_from_args_or_kwargs(scargo_outputs, "parameters", 0)
        parameters = {}
        if raw_parameters:
            for key, value in zip(raw_parameters.keys, raw_parameters.values):
                parameters[key.value] = self._resolve_workflow_param(value)

        raw_artifacts = self._get_variable_from_args_or_kwargs(scargo_outputs, "artifacts", 1)
        artifacts = {}
        if raw_artifacts:
            for key, raw_artifact in zip(raw_artifacts.keys, raw_artifacts.values):
                artifacts[key.value] = self._transpile_artifact(raw_artifact, output=True)

        return Transput(parameters=parameters, artifacts=artifacts)

    @property
    def template(self) -> Dict:
        """
        Returns the dictionary defining the Argo template for this workflow
        step.
        """

        template: Dict[str, Any] = {"name": self.template_name}

        if self.inputs.exist:
            inputs_section = {"inputs": dict()}
            if self.inputs.parameters:
                inputs_section["inputs"]["parameters"] = [{"name": key} for key in self.inputs.parameters]
            if self.inputs.artifacts:
                inputs_section["inputs"]["artifacts"] = [
                    dict({"name": key}, **value) for key, value in self.inputs.artifacts.items()
                ]
            template.update(inputs_section)

        if self.outputs.exist:
            outputs_section = {"outputs": dict()}
            if self.outputs.parameters:
                outputs_section["outputs"]["parameters"] = [{"name": key} for key in self.outputs.parameters]
            if self.outputs.artifacts:
                outputs_section["outputs"]["artifacts"] = [
                    dict({"name": key}, **value) for key, value in self.outputs.artifacts.items()
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
