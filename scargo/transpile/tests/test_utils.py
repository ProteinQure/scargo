import ast

from scargo.transpile.utils import SourceToArgoTransformer


def test_resolve_string():
    node = ast.JoinedStr(
        values=[
            ast.Constant(value="add_alpha_", kind=None),
            ast.FormattedValue(
                value=ast.Constant(value="{{inputs.parameters.init-value}}", kind=None),
                conversion=-1,
                format_spec=None,
            ),
            ast.Constant(value=".txt", kind=None),
        ],
    )

    assert SourceToArgoTransformer._resolve_string(node) == r"add_alpha_{{inputs.parameters.init-value}}.txt"

