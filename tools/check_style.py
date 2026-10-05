import ast
import sys
from pathlib import Path

MAX_FILE_LINES = 250
MAX_FUNCTION_LINES = 40
CHECKED_FOLDERS = ("src", "tests", "tools")


# Problems with one function: a missing comment line above it, a docstring, or too many lines
def function_problems(path: Path, lines: list[str], node: ast.AST) -> list[str]:
    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return []
    problems = []
    first_line = min([node.lineno] + [decorator.lineno for decorator in node.decorator_list])
    above = lines[first_line - 2].strip() if first_line >= 2 else ""
    is_test = node.name.startswith("test_")
    if not is_test and not above.startswith("#"):
        problems.append(f"{path}:{node.lineno} {node.name} has no comment line above it")
    if ast.get_docstring(node) is not None:
        problems.append(f"{path}:{node.lineno} {node.name} has a docstring")
    length = (node.end_lineno or node.lineno) - node.lineno + 1
    if length > MAX_FUNCTION_LINES:
        problems.append(f"{path}:{node.lineno} {node.name} is {length} lines long")
    return problems


# Problems with one Python file: its length, a header comment, and each function in it
def file_problems(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    problems = []
    if len(lines) > MAX_FILE_LINES:
        problems.append(f"{path} is {len(lines)} lines long")
    if lines and lines[0].startswith("#"):
        problems.append(f"{path} starts with a header comment")
    tree = ast.parse(text)
    if ast.get_docstring(tree) is not None:
        problems.append(f"{path} has a module docstring")
    for node in ast.walk(tree):
        problems += function_problems(path, lines, node)
    return problems


# Checks every Python file in the project and exits non-zero if any rule is broken
def main() -> None:
    root = Path(__file__).resolve().parent.parent
    problems = []
    for folder in CHECKED_FOLDERS:
        for path in sorted((root / folder).rglob("*.py")):
            problems += file_problems(path.relative_to(root))
    for problem in problems:
        print(problem)
    print(f"style rules: {len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
