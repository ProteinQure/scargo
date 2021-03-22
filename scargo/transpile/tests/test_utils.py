import ast
from typing import List, Union

import pytest

from scargo.transpile.utils import get_variables_from_call


def compare_ast(node1: Union[ast.expr, List[ast.expr]], node2: Union[ast.expr, List[ast.expr]]) -> bool:
    """
    Checks if the value of two ASTs are equivalent.
    """
    if type(node1) is not type(node2):
        return False

    if isinstance(node1, ast.AST):
        for k, v in vars(node1).items():
            if k in ("lineno", "col_offset", "ctx"):
                continue
            if not compare_ast(v, getattr(node2, k)):
                return False
        return True

    elif isinstance(node1, list) and isinstance(node2, list):
        return all(compare_ast(n1, n2) for n1, n2 in zip(node1, node2))
    else:
        return node1 == node2


@pytest.mark.parametrize(
    "node, args, expected",
    [
        # test single kwarg
        (
            ast.Call(
                func=ast.Attribute(
                    value=ast.Constant(value="{{inputs.artifacts.csv-file.path}}"), attr="open", ctx=ast.Load()
                ),
                args=[],
                keywords=[ast.keyword(arg="mode", value=ast.Constant(value="r"))],
            ),
            ["mode"],
            {"mode": ast.Constant(value="r")},
        ),
        # test single arg
        (
            ast.Call(
                func=ast.Attribute(
                    value=ast.Constant(value="{{outputs.artifacts.out-file.path}}"), attr="open", ctx=ast.Load()
                ),
                args=[ast.Constant(value="w+")],
                keywords=[],
            ),
            ["mode"],
            {"mode": ast.Constant(value="w+")},
        ),
        # test multiple args
        (
            ast.Call(
                func=ast.Attribute(
                    value=ast.Constant(value="{{outputs.artifacts.txt-out.path}}"), attr="open", ctx=ast.Load()
                ),
                args=[
                    ast.JoinedStr(
                        values=[
                            ast.Constant(value="add_multi_"),
                            ast.FormattedValue(
                                value=ast.Constant(value="{{inputs.parameters.init-value}}"), conversion=-1
                            ),
                            ast.Constant(value=".txt"),
                        ]
                    ),
                    ast.Constant(value="w+"),
                ],
                keywords=[],
            ),
            ["file_name", "mode"],
            {
                "file_name": ast.JoinedStr(
                    values=[
                        ast.Constant(value="add_multi_"),
                        ast.FormattedValue(value=ast.Constant(value="{{inputs.parameters.init-value}}"), conversion=-1),
                        ast.Constant(value=".txt"),
                    ]
                ),
                "mode": ast.Constant(value="w+"),
            },
        ),
        # TODO: test multiple kwargs?
    ],
)
def test_get_variables_from_call(node, args, expected):
    for name, value in get_variables_from_call(node, args).items():
        assert compare_ast(value, expected[name])
