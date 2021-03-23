import ast

import pytest

from scargo.core import WorkflowParams
from scargo.transpile import resolve


@pytest.mark.parametrize(
    "node, locals_context, expected",
    [
        (
            ast.Subscript(
                value=ast.Name(id="workflow_parameters", ctx=ast.Load()),
                slice=ast.Constant(value="word-index"),
                ctx=ast.Load(),
            ),
            {"workflow_parameters": WorkflowParams({"word-index": "1"})},
            "{{workflow.parameters.word-index}}",
        )
    ],
)
def test_resolve_workflow_param(node, locals_context, expected):
    assert resolve.resolve_workflow_param(node, locals_context) == expected
