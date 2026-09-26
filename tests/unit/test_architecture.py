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


def test_master_data_router_module_has_no_sql_or_transaction_operations() -> None:
    path = Path("app/master_data/router.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_imports = {"select", "func", "IntegrityError"}
    direct_database_methods = {
        "get",
        "execute",
        "scalars",
        "scalar",
        "query",
        "add",
        "delete",
        "flush",
        "refresh",
        "commit",
        "rollback",
    }
    database_receivers = {
        "session",
        "db_session",
        "db",
        "database",
        "connection",
        "conn",
        "engine",
    }
    imports: list[str] = []
    database_calls: list[str] = []

    def root_name(expression: ast.expr) -> str | None:
        while isinstance(expression, ast.Attribute):
            expression = expression.value
        return expression.id if isinstance(expression, ast.Name) else None

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imports.extend(alias.name for alias in node.names if alias.name in forbidden_imports)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = root_name(node.func.value)
            if node.func.attr in direct_database_methods and receiver in database_receivers:
                database_calls.append(f"{path}:{node.lineno} {receiver}.{node.func.attr}()")
    assert imports == []
    assert database_calls == []


def test_warehouse_router_module_has_no_sql_or_transaction_operations() -> None:
    path = Path("app/warehouse/router.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_imports = {"select", "func", "IntegrityError"}
    direct_database_methods = {
        "get",
        "execute",
        "scalars",
        "scalar",
        "query",
        "add",
        "delete",
        "flush",
        "refresh",
        "commit",
        "rollback",
    }
    database_receivers = {
        "session",
        "db_session",
        "db",
        "database",
        "connection",
        "conn",
        "engine",
    }
    imports = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name in forbidden_imports
    ]
    database_calls: list[str] = []

    def root_name(expression: ast.expr) -> str | None:
        while isinstance(expression, ast.Attribute):
            expression = expression.value
        return expression.id if isinstance(expression, ast.Name) else None

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = root_name(node.func.value)
            if node.func.attr in direct_database_methods and receiver in database_receivers:
                database_calls.append(f"{path}:{node.lineno} {receiver}.{node.func.attr}()")
    assert imports == []
    assert database_calls == []


def test_legacy_router_debt_is_removed_from_master_data() -> None:
    path = Path("app/master_data/_legacy_router.py")
    assert not path.exists()
    router = ast.parse(Path("app/master_data/router.py").read_text(encoding="utf-8"))
    legacy_imports = [
        node
        for node in ast.walk(router)
        if isinstance(node, ast.ImportFrom)
        and node.module == "app.master_data._legacy_router"
    ]
    assert legacy_imports == []
