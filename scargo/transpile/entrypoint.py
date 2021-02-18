import ast

from scargo.transpile.workflow_step import WorkflowStep


class EntrypointTranspiler(ast.NodeVisitor):
    def __init__(self, script_locals, tree) -> None:
        self.script_locals = script_locals
        self.tree = tree
        self.steps = []

    def visit_Call(self, node: ast.Call):
        self.steps.append(WorkflowStep(call_node=node, locals_context=self.script_locals, tree=self.tree))

    def visit_Assign(self, node: ast.Assign):
        # add Input or Output to locals
        # or other variables I guess
        pass

    def visit_If(self, node: ast.If):
        # process conditional somehow
        pass
