import ast
from typing import Dict, List, Optional

import astor

from scargo.errors import ScargoTranspilerError
from scargo.transpile.types import Transput
from scargo.transpile import utils
from scargo.transpile.workflow_step import WorkflowStep


class EntrypointTranspiler(ast.NodeVisitor):
    def __init__(self, script_locals, tree) -> None:
        # TODO: there should be an alternative to importing all the locals from the global scope
        # mount_points and workflow_params should be saved in it's own attribute
        self.script_locals = script_locals
        self.tree = tree
        self.steps: List[List[WorkflowStep]] = []
        self.inputs: Dict[str, Transput] = {}
        self.outputs: Dict[str, Transput] = {}

    def visit_Call(self, node: ast.Call):
        """
        Convert all function calls into Workflow Steps.

        TODO: make sure the function calls are marked with @scargo
        TODO: allow evaluation of non-scargo functions?
        """
        # TODO: easier to read if transput were resolved and passed
        self.steps.append(
            [WorkflowStep(call_node=node, context_inputs=self.inputs, context_outputs=self.outputs, tree=self.tree)]
        )

    @staticmethod
    def _scargo_transput(node: ast.Assign) -> Optional[str]:
        call_func = node.value
        if isinstance(call_func, ast.Call):
            if call_func.func.id == "ScargoInput":
                return "ScargoInput"
            elif call_func.func.id == "ScargoOutput":
                return "ScargoOutput"
            else:
                return None
        else:
            return None

    def visit_Assign(self, node: ast.Assign):
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

            resolved_transput = utils.resolve_transput(call_func, locals_context=self.script_locals, tree=self.tree)
            if transput == "ScargoInput":
                self.inputs[node.targets[0].id] = resolved_transput
            else:
                self.outputs[node.targets[0].id] = resolved_transput
        else:
            exec(astor.to_source(node), {}, self.script_locals)

    def _resolve_compare(self, node: ast.expr) -> str:
        """
        TODO: allow for other comparison inputs, such as Transputs and CSV values
        """
        if isinstance(node, ast.Subscript) and utils.is_workflow_param(node.value.id, self.script_locals):
            return utils.resolve_workflow_param(node, self.script_locals)
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
            return WorkflowStep(
                call_node=body.value,
                tree=self.tree,
                context_inputs=self.inputs,
                context_outputs=self.outputs,
                condition=condition,
            )
        else:
            raise NotImplementedError("Can only transpile function call inside of conditional statements.")

    def visit_If(self, node: ast.If):
        """

        # TODO: support nested if-statements
        """
        all_steps: List[WorkflowStep] = []
        all_steps.append(self._resolve_If(node))
        for child in node.orelse:
            assert isinstance(child, ast.If)
            all_steps.append(self._resolve_If(child))

        self.steps.append(all_steps)
