import re
from typing import List, Literal, Match, NamedTuple, Tuple

from scargo.args import ScargoInput, ScargoOutput


VAR_REGEX = re.compile(r"(?<=\{\{)[^{}]+(?=\}\})")
VAR_NAME_RE = re.compile(r"^[\w\-]+")

VarType = Literal["inputs", "outputs"]
IOType = Literal["parameters", "artifacts"]


class BashVar(NamedTuple):
    """
    Variable extracted from bash template with associated information for replacement by ScargoInput or ScargoOutput
    """

    var_type: VarType
    io_type: IOType
    name: str
    location: slice


LineMatches = List[Tuple[int, List[Match[str]]]]
LineBashVars = List[Tuple[int, List[BashVar]]]


def valid_name(name: str) -> bool:
    """
    Check if string is valid name for an Argo variable.
    """
    found_pattern = VAR_NAME_RE.match(name)
    if found_pattern is None:
        return False
    else:
        return found_pattern.span()[1] == len(name)


def extract_vars_from_str(tmpl_lines: List[str]) -> Tuple[LineMatches, int]:
    """
    Extract variables from each line while counting the total number of variables.
    """
    total_vars = 0
    all_vars = []
    for l_i, tmpl in enumerate(tmpl_lines):
        line_vars = list(VAR_REGEX.finditer(tmpl))
        total_vars += len(line_vars)
        if len(line_vars) > 0:
            all_vars.append((l_i, line_vars))

    return all_vars, total_vars


def get_bash_vars(all_vars: LineMatches) -> LineBashVars:
    """
    Convert bash template variable matches in each line to Scargo-compatible variables.
    """
    all_bash_vars = []
    invalid_vars = []
    for l_i, line_vars in all_vars:
        bash_vars = []

        for line_var in line_vars:
            var_str = line_var.group(0).strip()
            var_parts = var_str.split(".")

            if len(var_parts) != 3:
                invalid_vars.append(
                    (
                        f"Line {l_i+1}: Invalid variable format. "
                        f"Expected something like inputs.artifacts.name, but found '{var_str}'."
                    )
                )
            else:
                var_type = var_parts[0]
                io_type = var_parts[1]
                name = var_parts[2]

                if var_type != "inputs" and var_type != "outputs":
                    invalid_vars.append(
                        (
                            f"Line {l_i+1}: Invalid variable type. "
                            f"Expected 'inputs' or 'outputs', but found '{var_type}' in '{var_str}'."
                        )
                    )
                elif io_type != "parameters" and io_type != "artifacts":
                    invalid_vars.append(
                        (
                            f"Line {l_i+1}: Invalid IO type."
                            f"Expected 'parameters' or 'artifacts', but found '{name}' in '{var_str}'."
                        )
                    )
                elif not valid_name(name):
                    invalid_vars.append(
                        (
                            f"Line {l_i+1}: Invalid variable name of '{name}'."
                            "Names can only contain dashes, underscores and alpha-numeric characters."
                        )
                    )
                else:
                    # increase span by 2 in both directions to get curly braces
                    span = (line_var.span()[0] - 2, line_var.span()[1] + 2)
                    bash_vars.append(BashVar(var_type=var_type, io_type=io_type, name=name, location=slice(*span)))

        all_bash_vars.append((l_i, bash_vars))

    if len(invalid_vars) > 0:
        err_str = f"Found {len(invalid_vars)} invalid variables:\n" + "\n".join(invalid_vars)
        raise ValueError(err_str)

    return all_bash_vars


def get_vars(tmpl_lines: List[str]) -> LineBashVars:
    """
    Extract all Scargo-compatible template variables from a Bash template.
    """
    all_vars, total_vars = extract_vars_from_str(tmpl_lines)

    if total_vars == 0:
        raise ValueError("No variables found in template.")
    else:
        return get_bash_vars(all_vars)


def get_missing_vars(
    all_vars: LineBashVars, scargo_in: ScargoInput, scargo_out: ScargoOutput
) -> List[Tuple[int, BashVar]]:
    """
    Return missing variable with line number for the purposes of reporting legible errors to the user.

    Parameters
    ----------
    all_vars : LineBashVars
        All variables extracted from a bash template
    scargo_in : ScargoInput
        Input Parameters and Artifacts to be inserted into the template
    scargo_out : ScargoOutput
        Output Parameters and Artifacts to be inserted into the template
    """
    missing_vars = []
    for l_i, line_vars in all_vars:
        for line_var in line_vars:
            if line_var.var_type == "outputs":
                insert_var = scargo_out
            else:
                insert_var = scargo_in

            insert_vars_names = getattr(insert_var, line_var.io_type)
            if insert_vars_names is None:
                missing_vars.append((l_i, line_var))
                insert_vars_names = None

            elif line_var.name not in insert_vars_names:
                missing_vars.append((l_i, line_var))

    return missing_vars


def replace_vars(
    orig_str: str, replace_vars: List[BashVar], scargo_in: ScargoInput, scargo_out: ScargoOutput
) -> List[str]:
    """
    Replace all variables in a Bash template with values determined from a ScargoInput and ScargoOutput.
    """
    last_stop = 0
    new_str = []

    for var in replace_vars:
        new_str.append(orig_str[last_stop : var.location.start])

        if var.var_type == "outputs":
            insert_var = scargo_out
        else:
            insert_var = scargo_in
        new_str.append(getattr(insert_var, var.io_type)[var.name].bash_str())

        last_stop = var.location.stop

    new_str.append(orig_str[last_stop:])

    return new_str


def fill_template(tmpl_lines: List[str], scargo_in: ScargoInput, scargo_out: ScargoOutput) -> List[str]:
    """
    Extract and fill all Scargo-compatible variables in a bash template.

    Parameters
    ----------
    tmpl_lines : List[str]
        All lines of a given bash template
    scargo_in : ScargoInput
        Input Parameters and Artifacts to be inserted into the template
    scargo_out : ScargoOutput
        Output Parameters and Artifacts to be inserted into the template
    """
    all_vars = get_vars(tmpl_lines)
    missing_vars = get_missing_vars(all_vars, scargo_in, scargo_out)
    if len(missing_vars) > 0:
        err_str = f"{len(missing_vars)} template variables were not provided:\n" + "\n".join(
            [f"  Line {l_i}, {line_var.location.start}: {line_var.name}" for l_i, line_var in missing_vars]
        )
        raise ValueError(err_str)

    for l_i, line_vars in all_vars:
        tmpl_lines[l_i] = "".join(replace_vars(tmpl_lines[l_i], line_vars, scargo_in, scargo_out))

    return tmpl_lines
