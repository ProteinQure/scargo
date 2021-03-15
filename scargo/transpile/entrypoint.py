import ast
from typing import Any, Dict, List, Optional

import astor

from scargo.core import WorkflowParams
from scargo.errors import ScargoTranspilerError
from scargo.transpile import resolve
from scargo.transpile.types import Context
from scargo.transpile.workflow_step import WorkflowStep, make_workflow_step


class EntrypointTranspiler(ast.NodeVisitor):
    """
    Visit and transpile all nodes of a function marked `@entrypoint`.

    Transpilation includes:
    1. Collecting Scargo Inputs and Outputs
    2. Creating WorkflowSteps
    """

    def __init__(
        self,
        script_locals: Dict[str, Any],
        workflow_params: WorkflowParams,
        mount_points: Dict[str, str],
        tree: ast.Module,
    ) -> None:
        self.tree = tree
        self.steps: List[List[WorkflowStep]] = []
        self.context = Context(
            locals=script_locals, inputs={}, outputs={}, workflow_params=workflow_params, mount_points=mount_points
        )

    def visit_Call(self, node: ast.Call) -> None:
        """
        Convert all function calls into Workflow Steps.

        TODO: make sure the function calls are marked with @scargo
        TODO: allow evaluation of non-scargo functions?
        """
        self.steps.append(
            [
                make_workflow_step(
                    call_node=node,
                    context=self.context,
                    tree=self.tree,
                )
            ]
        )

    @staticmethod
    def _scargo_transput(node: ast.Assign) -> Optional[str]:
        """
        Determine if a variable is being assigned:
        1. A ScargoInput
        2. A ScargoOutput
        3. Neither
        """
        call_func = node.value
        if isinstance(call_func, ast.Call):
            func_name = call_func.func.id
            if func_name == "ScargoInput":
                return "ScargoInput"
            elif func_name == "ScargoOutput":
                return "ScargoOutput"
            else:
                return None
        else:
            return None

    def visit_Assign(self, node: ast.Assign) -> None:
        """
        Evaluate all assignments, except for ScargoInput and ScargoOutput.

        Currently, no assignments exist that would require transpiling to YAML.
        """
        transput = EntrypointTranspiler._scargo_transput(node)
        if transput is not None:
            call_func = node.value
            assert isinstance(call_func, ast.Call)

            if len(node.targets) > 1:
                raise ScargoTranspilerError("Multiple assignment not supported by Scargo Transpiler.")

            resolved_transput = resolve.resolve_transput(
                call_func,
                context=Context(
                    locals=self.context.locals,
                    inputs=self.context.inputs,
                    outputs=self.context.outputs,
                    workflow_params=self.context.workflow_params,
                    mount_points=self.context.mount_points,
                ),
            )
            transput_name = node.targets[0].id
            if transput == "ScargoInput":
                self.context.inputs[transput_name] = resolved_transput
            else:
                self.context.outputs[transput_name] = resolved_transput
        else:
            exec(astor.to_source(node), {}, self.context.locals)

    def visit_If(self, node: ast.If) -> None:
        """
        Conditionals (if-statements) should be transpiled into Argo steps marked with `when: ` field.

        TODO: support nested if-statements
        """
        all_steps: List[WorkflowStep] = []
        all_steps.append(resolve.resolve_If(node, self.tree, self.context))
        for child in node.orelse:
            assert isinstance(child, ast.If)
            all_steps.append(resolve.resolve_If(child, self.tree, self.context))

        self.steps.append(all_steps)
