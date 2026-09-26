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


def test_inventory_read_handlers_delegate_queries_and_do_not_manage_transactions() -> None:
    path = Path("app/inventory/router.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    read_handlers = {
        "list_stock",
        "get_stock",
        "list_inbounds",
        "get_inbound",
        "list_outbounds",
        "get_outbound",
        "list_transactions",
        "get_transaction",
    }
    direct_database_methods = {
        "get",
        "execute",
        "scalars",
        "scalar",
        "query",
        "commit",
        "rollback",
    }
    offenders: list[str] = []

    def root_name(expression: ast.expr) -> str | None:
        while isinstance(expression, ast.Attribute):
            expression = expression.value
        return expression.id if isinstance(expression, ast.Name) else None

    for node in ast.walk(tree):
        if (
            not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            or node.name not in read_handlers
        ):
            continue
        for call in ast.walk(node):
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "select"
            ):
                offenders.append(f"{path}:{call.lineno} direct select() in {node.name}")
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr in direct_database_methods
                and root_name(call.func.value) in {"session", "db_session", "db", "database"}
            ):
                offenders.append(f"{path}:{call.lineno} direct database call in {node.name}")
    assert offenders == []


def test_inventory_service_does_not_manage_read_transactions() -> None:
    path = Path("app/inventory/service.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    transaction_calls = [
        f"{path}:{node.lineno} {node.func.attr}()"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"commit", "rollback"}
    ]
    assert transaction_calls == []


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
