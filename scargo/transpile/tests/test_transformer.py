import ast

import pytest

from scargo.transpile.transformer import SourceToArgoTransformer


@pytest.mark.parametrize("path_value, ext", [("add_alpha_", ".txt"), ("add_beta_", ".csv")])
def test_resolve_string(path_value, ext):
    """
    Testing if a JoinedStr node representing an f-string is correctly resolved
    by the SourceToArgoTransformer.
    """
    node = ast.JoinedStr(
        values=[
            ast.Constant(value=path_value, kind=None),
            ast.FormattedValue(
                value=ast.Constant(value="{{inputs.parameters.init-value}}", kind=None),
                conversion=-1,
                format_spec=None,
            ),
            ast.Constant(value=ext, kind=None),
        ],
    )

    assert SourceToArgoTransformer._resolve_string(node) == "%s{{inputs.parameters.init-value}}%s" % (path_value, ext)


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
