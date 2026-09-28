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
        "exec_driver_sql",
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
    database_connection_methods = {
        "connect",
        "connection",
        "cursor",
        "execution_options",
        "raw_connection",
    }
    offenders: list[str] = []

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
    class AliasAwareDatabaseCalls(ast.NodeVisitor):
        def __init__(self) -> None:
            self.aliases = set(database_receivers)

        def references_database(self, expression: ast.expr) -> bool:
            if isinstance(expression, ast.Name):
                return expression.id in self.aliases
            if isinstance(expression, ast.Attribute):
                return expression.attr in database_receivers or self.references_database(
                    expression.value
                )
            if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Attribute):
                return (
                    expression.func.attr in database_connection_methods
                    and self.references_database(expression.func.value)
                )
            return False

        def assigned_names(self, target: ast.expr) -> set[str]:
            if isinstance(target, ast.Name):
                return {target.id}
            if isinstance(target, (ast.Tuple, ast.List)):
                return set().union(*(self.assigned_names(item) for item in target.elts))
            return set()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            saved_aliases = self.aliases
            local_aliases = set(saved_aliases)
            arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            if node.args.vararg:
                arguments.append(node.args.vararg)
            if node.args.kwarg:
                arguments.append(node.args.kwarg)
            for argument in arguments:
                local_aliases.discard(argument.arg)
                if argument.arg in database_receivers:
                    local_aliases.add(argument.arg)
            self.aliases = local_aliases
            for statement in node.body:
                self.visit(statement)
            self.aliases = saved_aliases

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Assign(self, node: ast.Assign) -> None:
            is_database_alias = self.references_database(node.value)
            self.visit(node.value)
            for target in node.targets:
                for name in self.assigned_names(target):
                    self.aliases.discard(name)
                    if is_database_alias:
                        self.aliases.add(name)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            is_database_alias = (
                node.value is not None and self.references_database(node.value)
            )
            if node.value is not None:
                self.visit(node.value)
            for name in self.assigned_names(node.target):
                self.aliases.discard(name)
                if is_database_alias:
                    self.aliases.add(name)

        def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
            is_database_alias = self.references_database(node.value)
            self.visit(node.value)
            for name in self.assigned_names(node.target):
                self.aliases.discard(name)
                if is_database_alias:
                    self.aliases.add(name)

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            self.visit(node.value)
            for name in self.assigned_names(node.target):
                self.aliases.discard(name)

        def visit_Delete(self, node: ast.Delete) -> None:
            for target in node.targets:
                for name in self.assigned_names(target):
                    self.aliases.discard(name)

        def visit_If(self, node: ast.If) -> None:
            self.visit(node.test)
            before = set(self.aliases)
            self.aliases = set(before)
            for statement in node.body:
                self.visit(statement)
            body_aliases = set(self.aliases)
            self.aliases = set(before)
            for statement in node.orelse:
                self.visit(statement)
            else_aliases = set(self.aliases)
            self.aliases = body_aliases | else_aliases

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Attribute):
                method = node.func.attr
                if method in {"commit", "rollback"} or (
                    method in direct_database_methods
                    and self.references_database(node.func.value)
                ):
                    offenders.append(f"{path}:{node.lineno} direct database call {method}()")
            self.generic_visit(node)

    AliasAwareDatabaseCalls().visit(tree)
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


def test_global_router_guard_tracks_local_and_chained_session_aliases() -> None:
    mutations = {
        "app/dashboard/router.py": (
            "def route(session):\n"
            "    local_session = session\n"
            "    chained_session = local_session\n"
            "    chained_session.execute(statement)\n"
        ),
        "app/inventory/router.py": (
            "def route(db):\n"
            "    local_db = db\n"
            "    local_db.add(record)\n"
        ),
        "app/users/router.py": (
            "def route(database):\n"
            "    local_session = database.session\n"
            "    chained_session = local_session\n"
            "    chained_session.commit()\n"
            "    chained_session.rollback()\n"
        ),
    }

    for path, mutation in mutations.items():
        violations = _router_boundary_violations(mutation, path)
        assert violations, f"global router guard missed alias in {path}: {mutation!r}"


def test_global_router_guard_tracks_database_connection_calls_and_aliases() -> None:
    mutations = {
        "app/dashboard/router.py": (
            "def route(session):\n"
            "    session.connection().execute(statement)\n"
        ),
        "app/inventory/router.py": (
            "def route(session):\n"
            "    session.connection().exec_driver_sql(statement)\n"
        ),
        "app/users/router.py": (
            "def route(session):\n"
            "    db = session\n"
            "    connection = db.connection()\n"
            "    local_connection = connection\n"
            "    local_connection.execute(statement)\n"
        ),
        "app/warehouse/router.py": (
            "def route(engine):\n"
            "    engine.connect().exec_driver_sql(statement)\n"
        ),
    }

    for path, mutation in mutations.items():
        violations = _router_boundary_violations(mutation, path)
        assert violations, f"global router guard missed connection call in {path}: {mutation!r}"


def test_router_guard_drops_connection_alias_after_reassignment_and_ignores_factory_calls() -> None:
    source = (
        "def route(session):\n"
        "    connection = session.connection()\n"
        "    connection = make_client()\n"
        "    connection.execute(statement)\n"
        "    adapter = make_adapter()\n"
        "    adapter.execute(statement)\n"
        "    adapter.connect().execute(statement)\n"
    )

    assert _router_boundary_violations(source, "app/dashboard/router.py") == []


def test_router_guard_drops_alias_after_local_reassignment() -> None:
    source = (
        "def route(session):\n"
        "    local_session = session\n"
        "    local_session = object()\n"
        "    local_session.execute(statement)\n"
    )

    assert _router_boundary_violations(source, "app/dashboard/router.py") == []


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
