import ast

from typing import Optional, Union


from scargo.errors import ScargoTranspilerError
from scargo.transpile.types import Artifacts, FilePut, FileTmp, Transput
from scargo.transpile import utils


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

    def __init__(self, input_argument: str, inputs: Transput, output_argument: str, outputs: Transput):
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
        self.inputs = inputs
        self.output_argument = output_argument
        self.outputs = outputs

    def visit_Subscript(self, node: ast.Subscript) -> Union[ast.Subscript, ast.Constant]:
        """
        Converts Subscript nodes operating on ScargoInput/ScargoOutput argument names into strings refering to the
        inputs/outputs parameters/artifacts.
        """
        if self._resolve_subscript(node, self.input_argument, self.output_argument) is not None:
            return ast.Constant(
                value=self._resolve_subscript(node, self.input_argument, self.output_argument), kind=None, ctx=node.ctx
            )
        else:
            return node

    @staticmethod
    def _resolve_subscript(node: ast.Subscript, input_arg: str, output_arg: str) -> Optional[str]:
        """
        Given an ast.Subscript node, translates its content into a Argo workflow parameter reference.
        """
        node_attr = node.value
        if not isinstance(node_attr, ast.Attribute):
            # raise NotImplementedError("Expected Attribute value for this node.")
            return None

        attr_name = node_attr.value
        if not isinstance(attr_name, ast.Name):
            # raise NotImplementedError("Expected Attribute to have name.")
            return None

        node_slice = node.slice
        if not isinstance(node_slice, ast.Index):
            # raise NotImplementedError("Expected slice to have an index.")
            return None

        node_slice_val = node_slice.value
        if not isinstance(node_slice_val, ast.Constant):
            # raise NotImplementedError("Expected slice value to be constant.")
            return None

        if attr_name.id == input_arg and node_attr.attr == "parameters":
            return "{{" + f"inputs.{node_attr.attr}.{node_slice_val.value}" + "}}"
        if attr_name.id == input_arg and node_attr.attr == "artifacts":
            return "{{" + f"inputs.{node_attr.attr}.{node_slice_val.value}.path" + "}}"
        elif attr_name.id == output_arg and node_attr.attr == "parameters":
            return "{{" + f"outputs.{node_attr.attr}.{node_slice_val.value}" + "}}"
        elif attr_name.id == output_arg and node_attr.attr == "artifacts":
            return "{{" + f"outputs.{node_attr.attr}.{node_slice_val.value}.path" + "}}"
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

    @staticmethod
    def _resolve_open(
        node: ast.Call, inputs: Optional[Artifacts] = None, outputs: Optional[Artifacts] = None
    ) -> ast.Call:
        """
        Convert the `open` method of either FileInput or FileOutput into an ast.Constant

        Accomplished by:
        1. Assembling the path to the file from the `open()` method from `FileOutput` or `FileInput`.
        2. Converting it to the built-in `open()` function with Argo compatible paths.
        """
        assert isinstance(node.func, ast.Attribute)
        assert isinstance(node.func.value, ast.Constant)

        # the full artifact path, for example: {{outputs.artifacts.txt-out.path}}
        full_path = node.func.value.value

        # determine if it's read or write mode
        # these are the same modes as the ones used in the `open` methods
        # of `FileInput` and `FileOutput`
        if "inputs" in full_path:
            mode = "r"
            put_obj = inputs[full_path.split(".")[2]]
        elif "outputs" in full_path:
            mode = "w+"
            put_obj = outputs[full_path.split(".")[2]]
        else:
            raise ScargoTranspilerError("Unexpected open() target. Expected `inputs` or `outputs`.")

        if isinstance(put_obj, FilePut):
            if mode == "r":
                vars = utils.get_variables_from_call(node, ["mode"])
            else:
                # get the second part of the path + filename
                vars = utils.get_variables_from_call(node, ["file_name", "mode"])

                if "file_name" in vars:
                    raw_path = vars["file_name"]
                    if isinstance(raw_path, ast.Constant):
                        path = raw_path.value
                    elif isinstance(raw_path, ast.JoinedStr):
                        path = SourceToArgoTransformer._resolve_string(raw_path)
                    else:
                        raise NotImplementedError(f"Unknown path type for file_name: {raw_path}")

                    full_path = f"{full_path}/{path}"

        elif isinstance(put_obj, FileTmp):
            vars = utils.get_variables_from_call(node, ["mode"])
        else:
            raise ScargoTranspilerError("Unexpected open() target. Expected `inputs` or `outputs`.")

        # Mode sanity check
        if "mode" in vars:
            node_mode = vars["mode"]
            assert isinstance(node_mode, ast.Constant)
            assert mode == node_mode.value

        return ast.Call(
            func=ast.Name(id="open"),
            args=[
                ast.Constant(value=full_path, kind=None),
                ast.Constant(value=mode, kind=None),
            ],
            keywords=[],
        )

    def visit_Call(self, node: ast.Call) -> ast.Call:
        """
        Custom visitor method for ast.Call nodes.

        Performs transpiling by:

        1. Identifying calls to `open()` methods on `FileInput` or `FileOutput` objects.
        2. Modifying the call node in such a way that the file read/write operation works in an Argo workflow.
        """
        # Visit child nodes to ensure all nested nodes are transformed by the
        # custom `visit_Call` and `visit_Subscript` methods
        self.generic_visit(node)

        if isinstance(node.func, ast.Attribute) and node.func.attr == "open":
            return SourceToArgoTransformer._resolve_open(node, self.inputs.artifacts, self.outputs.artifacts)
        else:
            return node
