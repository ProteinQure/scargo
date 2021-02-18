from pathlib import Path
from typing import Any, Dict
import yaml

from scargo.core import WorkflowParams


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


def write_workflow_to_yaml(path_to_script: Path, transpiled_workflow: Dict[str, Any]) -> None:
    """
    Writes the `transpiled_workflow` to a YAML file in the same directory as the
    original Python input script.
    """

    def repr_str(dumper, data):
        """
        Custom string representation to ensure a leading "|" followed by a
        line break in the source section of the Argo YAML workflow file.
        """
        if "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.org_represent_str(data)

    # back up the default string representer and register the custom one
    ArgoYamlDumper.org_represent_str = ArgoYamlDumper.represent_str
    yaml.add_representer(str, repr_str, Dumper=ArgoYamlDumper)

    filename = f"{path_to_script.stem.replace('_', '-')}.yaml"
    with open(path_to_script.parent / filename, "w+") as yaml_out:
        yaml.dump(transpiled_workflow, yaml_out, Dumper=ArgoYamlDumper, sort_keys=False)


def write_params_to_yaml(path_to_script: Path, parameters: WorkflowParams) -> None:
    """
    Writes the `parameters` to a YAML file in the same directory as the
    original Python input script.
    """

    filename = f"{path_to_script.stem.replace('_', '-')}-parameters.yaml"
    with open(path_to_script.parent / filename, "w+") as yaml_out:
        yaml.dump(dict(parameters), yaml_out)
