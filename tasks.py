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
def check(c):
    """
    Runs all static checks, such as black, flake8 and pylint.
    """
    print("Black")
    c.run(f"black --line-length 120 {project_name}/")
    print("Style checks")
    c.run(f"flake8 {project_name}/")
    c.run(f"pylint {project_name}/ --rcfile=setup.cfg --output-format=colorized")


@task
def test(c, coverage=False, html_report=False, keyword=None):
    """
    Run tests using pytest. The `-k` flag works exactly like with pytest - it
    will subselect tests according to the provided substring. If you want to
    measure code coverage you just need to provide the `--coverage` flag. On
    top of that, you can get a detailed interactive test coverage report by
    providing the `--html-report` flag. To view the code coverage report,
    navigate to the htmlcov/ directory, open the index.html in your favourite
    browser and view the interactive coverage report.

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
    test_command = f"pytest -vvv {keyword_filter} ."

    if coverage:
        test_command = f"coverage run -m {test_command}"

    c.run(test_command)

    if coverage:
        c.run("coverage report -m")
    if html_report:
        c.run("coverage html")
