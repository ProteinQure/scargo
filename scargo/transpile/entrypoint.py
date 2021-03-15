import ast
from typing import Any, Dict, List, Optional

import astor

from scargo.core import WorkflowParams
from scargo.errors import ScargoTranspilerError
from scargo.transpile import resolve, utils
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

    def _resolve_compare(self, node: ast.expr) -> str:
        """
        TODO: allow for other comparison inputs, such as Transputs and CSV values
        """
        if isinstance(node, ast.Subscript) and utils.is_workflow_param(node.value.id, self.context.locals):
            return resolve.resolve_workflow_param(node, self.context.locals)
        elif isinstance(node, ast.Constant):
            return str(node.value)
        else:
            raise ScargoTranspilerError("Only constants and Workflow allowed in comparison.")

    def _resolve_cond(self, node: ast.If) -> str:
        """
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
                self._resolve_compare(compare.left),
                astor.op_util.get_op_symbol(compare.ops[0]),
                self._resolve_compare(compare.comparators[0]),
            )
        )

    def _resolve_If(self, node: ast.If) -> WorkflowStep:
        """
        TODO: support assignments, not just calls
        TODO: support multi-statement bodies
        """
        if len(node.body) > 1:
            raise NotImplementedError(
                "Can't yet handle multi-statement bodies. Only single function-calls are allowed."
            )

        body = node.body[0]
        if isinstance(body, ast.Expr) and isinstance(body.value, ast.Call):
            condition = self._resolve_cond(node)
            return make_workflow_step(
                call_node=body.value,
                tree=self.tree,
                context=self.context,
                condition=condition,
            )
        else:
            raise NotImplementedError("Can only transpile function call inside of conditional statements.")

    def visit_If(self, node: ast.If) -> None:
        """
        Conditionals (if-statements) should be transpiled into Argo steps marked with `when: ` field.

        TODO: support nested if-statements
        """
        all_steps: List[WorkflowStep] = []
        all_steps.append(self._resolve_If(node))
        for child in node.orelse:
            assert isinstance(child, ast.If)
            all_steps.append(self._resolve_If(child))

        self.steps.append(all_steps)
