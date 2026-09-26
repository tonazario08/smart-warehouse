"""Static checks for backend domain boundaries."""

import ast
from pathlib import Path


def test_repository_modules_never_call_commit() -> None:
    offenders: list[str] = []
    for path in Path("app").glob("**/repository.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "commit":
                    offenders.append(f"{path}:{node.lineno}")
    assert offenders == []


def test_master_data_router_keeps_database_operations_in_service() -> None:
    path = Path("app/master_data/router.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {"select", "func", "IntegrityError"}
    imports: list[str] = []
    transaction_calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imports.extend(alias.name for alias in node.names if alias.name in forbidden)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"commit", "rollback"}:
                transaction_calls.append(f"{path}:{node.lineno}")
    assert imports == []
    assert transaction_calls == []
