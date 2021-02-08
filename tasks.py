"""
Definition of all invoke CLI commands for this project.
"""

from invoke import task


project_name = "scargo"


@task
def install(c):
    """
    Install all requirements and setup poetry environment.
    """
    c.run("poetry install")


@task
def check(c, fix=True):
    """
    Runs all static checks, such as black, flake8 and pylint.
    """

    check_command = ""
    if not fix:
        check_command = " --check "

    print("Black")
    c.run(f"black {check_command} --line-length 120 {project_name}/")
    c.run(f"black {check_command} --line-length 120 examples/")
    print("Style checks")
    c.run(f"flake8 {project_name}/")
    c.run(f"flake8 examples/")
    c.run(f"pylint {project_name}/ --rcfile=setup.cfg --output-format=colorized")
    c.run(f"pylint examples/ --rcfile=setup.cfg --output-format=colorized")


@task
def test(c, coverage=False, html_report=False, keyword=None):
    """
    Run tests using pytest.

    Parameters
    ----------
    coverage : bool
        Enable printing out test coverage of code.
    html_report : bool
        Generate detailed interactive test coverage report. To view the report, navigate to the htmlcov/ directory, open
        the index.html in a browser and view the interactive coverage report.
    keyword : str, optional
        Subselects tests given the provided substring/keyword. Works exactly like the `pytest` `-k` flag.

    Example usage:
        inv test
        inv test -k TestUtils
        inv test --coverage --html-report
        inv test --coverage --html-report -k TestUtils
    """

    if keyword is None:
        keyword_filter = ""
    else:
        keyword_filter = f"-k {keyword}"
    test_command = f"pytest -vvv {keyword_filter} . --color=yes"

    if coverage:
        test_command = f"coverage run -m {test_command}"

    c.run(test_command)

    if coverage:
        c.run("coverage report -m")
    if html_report:
        c.run("coverage html")
