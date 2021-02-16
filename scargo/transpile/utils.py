"""
Utility functions used in the transpilation process.
"""

import ast
from typing import Dict, NamedTuple, Optional, Union

import yaml


def hyphenate(text: str) -> str:
    """
    Converts underscores to hyphens.

    Python functions use underscores while Argo uses hyphens for Argo template names by convention.
    """
    return text.replace("_", "-")


class Transput(NamedTuple):
    """
    Transput is the hypernym of inputs & outputs. Provides
    access to the WorkflowStep input/output parameters and artifacts.
    """

    parameters: Optional[Dict] = None
    artifacts: Optional[Dict] = None

    @property
    def exist(self) -> bool:
        """
        True if at least one of the two class attributes is not None or an
        empty dict.
        """
        return (self.parameters is None or not self.parameters) or (self.artifacts is None or not self.artifacts)


class ArgoYamlDumper(yaml.SafeDumper):
    """
    Custom YAML dumper to generate Argo-compatible YAML files.

    Inspired by https://stackoverflow.com/a/44284819/3786245
    """

    def write_line_break(self, data=None) -> None:
        """
        Inserts a blank line between top-level objects in the YAML file.
        """
        super().write_line_break(data)

        if len(self.indents) == 1:
            super().write_line_break()


class SourceToArgoTransformer(ast.NodeTransformer):
    """
    Transforms the source code of a @scargo decorated function to be compatible
    with Argo YAML.

    For example, any reference to the `ScargoInput` argument
    e.g. `scargo_in.parameters['x']` needs to be converted to
    `{{inputs.parameters.x}}`.

    Examples
    --------
    tree = ast.parse(source_code_of_scargo_decorated_function, type_comments=True)
    # NOTE: changes tree in-place!! use copy.deepcopy if you want to avoid this
    SourceToArgoTransformer("scargo_in", "scargo_out").visit(tree)
    """

    def __init__(self, input_argument: str, output_argument: str):
        """
        Create a new SourceToArgoTransformer.

        Parameters
        ----------
        input_argument : str
            The name of the ScargoInput argument to the @scargo-decorated
            function whose node is being transformed.
        output_argument : str
            The name of the ScargoOutput argument to the @scargo-decorated
            function whose node is being transformed.
        """
        self.input_argument = input_argument
        self.output_argument = output_argument

    def visit_Subscript(self, node: ast.Subscript) -> Union[ast.Subscript, ast.Constant]:
        """
        Converts Subscript nodes operating on ScargoInput/ScargoOutput argument names into strings refering to the
        inputs/outputs parameters/artifacts.
        """
        if self._resolve_subscript(node):
            return ast.Constant(value=self._resolve_subscript(node), kind=None, ctx=node.ctx)
        else:
            return node

    def _resolve_subscript(self, node: ast.Subscript) -> Optional[str]:
        """
        Given an ast.Subscript node, translates its content into a Argo workflow parameter reference.
        """
        if node.value.value.id == self.input_argument and node.value.attr == "parameters":
            return "{{" + f"inputs.{node.value.attr}.{node.slice.value.value}" + "}}"
        if node.value.value.id == self.input_argument and node.value.attr == "artifacts":
            return "{{" + f"inputs.{node.value.attr}.{node.slice.value.value}.path" + "}}"
        elif node.value.value.id == self.output_argument and node.value.attr == "parameters":
            return "{{" + f"outputs.{node.value.attr}.{node.slice.value.value}" + "}}"
        elif node.value.value.id == self.output_argument and node.value.attr == "artifacts":
            return "{{" + f"outputs.{node.value.attr}.{node.slice.value.value}.path" + "}}"
        else:
            return None

    @staticmethod
    def _resolve_string(node: ast.JoinedStr) -> str:
        """
        Given a node that either represent a normal string or an f-string,
        resolve the content of that string from the node.
        """
        string_parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                string_parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                format_str_val = value.value
                if isinstance(format_str_val, ast.Constant):
                    string_parts.append(format_str_val.value)
                else:
                    raise NotImplementedError("Unimplemented f-string type.")

        return "".join(string_parts)

    def visit_Call(self, node: ast.Call) -> ast.Call:
        """
        Custom visitor method for ast.Call nodes.

        Performs transpiling by:

        1. Identifying calls to `open()` methods on `FileInput` or `FileOutput` objects.
        2. Modifying the call node in such a way that the file read/write operation works in an Argo workflow.

        Accomplished by:

        1. Assembling the path to the file from the `open()` method from `FileOutput` or `FileInput`.
        2. Converting it to the built-in `open()` function with Argo compatible paths.
        """

        # Visit child nodes to ensure all nested Call nodes are transformed by `visit_Call`.
        self.generic_visit(node)

        if isinstance(node.func, ast.Attribute) and node.func.attr == "open":
            # then we know that we're dealing with the `open` method of either
            # FileInput or FileOutput

            # determine if it's read or write mode
            # these are the same modes as the ones used in the `open` methods
            # of `FileInput` and `FileOutput`
            if "inputs" in node.func.value.value:
                mode = "r"
            elif "outputs" in node.func.value.value:
                mode = "w+"
            else:
                raise ValueError("Invalid output mode.")

            # get the prefix from the object whose `open` method is being called
            path_prefix = node.func.value.value

            # get the second part of the path + filename
            if isinstance(node.args[0], ast.Constant):
                path = node.args[0].value
            elif type(node.args[0]) in [ast.Constant, ast.JoinedStr]:
                path = self._resolve_string(node.args[0])

            return ast.Call(
                func=ast.Name(id="open", ctx=ast.Load()),
                args=[
                    ast.Constant(value=f"{path_prefix}/{path}", kind=None),
                    ast.Constant(value=mode, kind=None),
                ],
                keywords=[],
            )

        # otherwise don't change anything
        return node
