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


def _router_boundary_violations(source: str, path: str) -> list[str]:
    tree = ast.parse(source)
    forbidden_imports = {
        "and_",
        "delete",
        "func",
        "insert",
        "IntegrityError",
        "or_",
        "select",
        "text",
        "update",
    }
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
    offenders: list[str] = []

    def name_chain(expression: ast.expr) -> set[str]:
        names: set[str] = set()
        while isinstance(expression, ast.Attribute):
            names.add(expression.attr)
            expression = expression.value
        if isinstance(expression, ast.Name):
            names.add(expression.id)
        return names

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("sqlalchemy"):
                offenders.append(f"{path}:{node.lineno} SQLAlchemy import")
            offenders.extend(
                f"{path}:{node.lineno} forbidden SQL import {alias.name}"
                for alias in node.names
                if alias.name in forbidden_imports
            )
        if isinstance(node, ast.Import):
            offenders.extend(
                f"{path}:{node.lineno} SQLAlchemy import"
                for alias in node.names
                if alias.name == "sqlalchemy" or alias.name.startswith("sqlalchemy.")
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver_names = name_chain(node.func.value)
            if node.func.attr in {"commit", "rollback"} or (
                node.func.attr in direct_database_methods
                and receiver_names.intersection(database_receivers)
            ):
                offenders.append(f"{path}:{node.lineno} direct database call {node.func.attr}()")
    return offenders


def test_every_router_module_stays_inside_the_service_boundary() -> None:
    offenders = [
        violation
        for path in Path("app").glob("**/router.py")
        for violation in _router_boundary_violations(path.read_text(encoding="utf-8"), str(path))
    ]

    assert offenders == []


def test_global_router_guard_detects_sql_and_session_mutations_across_modules() -> None:
    mutations = {
        "app/dashboard/router.py": "from sqlalchemy import select\n",
        "app/warehouse/router.py": "session.execute(statement)\n",
        "app/users/router.py": "session.add(record)\n",
        "app/audit/router.py": "session.commit()\n",
    }

    for path, mutation in mutations.items():
        violations = _router_boundary_violations(mutation, path)
        assert violations, f"global router guard missed mutation in {path}: {mutation!r}"


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


def test_inventory_read_service_methods_do_not_manage_transactions() -> None:
    path = Path("app/inventory/service.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    read_methods = {
        "list_stock",
        "get_stock",
        "list_inbounds",
        "get_inbound",
        "list_outbounds",
        "get_outbound",
        "list_transactions",
        "get_transaction",
    }
    transaction_calls: list[str] = []
    for method in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
        if method.name not in read_methods:
            continue
        transaction_calls.extend(
            f"{path}:{node.lineno} {node.func.attr}()"
            for node in ast.walk(method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"commit", "rollback"}
        )
    assert transaction_calls == []


def test_inventory_write_handlers_delegate_database_work_to_service() -> None:
    path = Path("app/inventory/router.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for handler_name in ("create_inbound", "create_outbound"):
        handler = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == handler_name
        )
        delegated = False
        for node in ast.walk(handler):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {
                    "commit",
                    "rollback",
                    "add",
                    "flush",
                    "refresh",
                    "get",
                    "scalar",
                }:
                    offenders.append(
                        f"{path}:{node.lineno} direct {node.func.attr}() in {handler_name}"
                    )
                delegated |= node.func.attr == handler_name
        if not delegated:
            offenders.append(
                f"{path}:{handler.lineno} {handler_name} does not delegate to its service"
            )
    assert offenders == []


def test_inventory_write_transactions_are_owned_by_write_service_methods() -> None:
    path = Path("app/inventory/service.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    methods = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }
    expected = {"create_inbound", "create_outbound"}
    assert expected <= methods.keys()
    for name in expected:
        transaction_calls = [
            node.func.attr
            for node in ast.walk(methods[name])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"commit", "rollback"}
        ]
        assert transaction_calls.count("commit") == 1
        assert transaction_calls.count("rollback") == 1


def test_inventory_service_does_not_use_administrative_audit_repository() -> None:
    path = Path("app/inventory/service.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    audit_references = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and any("AuditRepository" in alias.name for alias in node.names)
    ]
    assert audit_references == []


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
