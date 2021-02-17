import ast

from scargo.transpile.utils import SourceToArgoTransformer


def test_resolve_string():
    """
    Testing if a JoinedStr node representing an f-string is correctly resolved
    by the SourceToArgoTransformer.
    """
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


def test_resolve_subscript():
    """
    Testing if a Subscript node is correctly resolved
    by the SourceToArgoTransformer.
    """
    node = ast.Subscript(
        value=ast.Attribute(
            value=ast.Name(id="scargo_in"),
            attr="parameters",
        ),
        slice=ast.Index(
            value=ast.Constant(value="init-value", kind=None),
        ),
    )

    assert (
        SourceToArgoTransformer._resolve_subscript(node, input_arg="scargo_in", output_arg="scargo_out")
        == r"{{inputs.parameters.init-value}}"
    )
