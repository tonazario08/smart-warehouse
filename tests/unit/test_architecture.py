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
    database_acquisition_methods = {
        "connect",
        "connection",
        "cursor",
        "get_bind",
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
            self.bound_callables: dict[str, set[str]] = {}

        def references_database(self, expression: ast.expr) -> bool:
            if isinstance(expression, ast.Name):
                return expression.id in self.aliases or expression.id in self.bound_callables
            if isinstance(expression, ast.Attribute):
                return expression.attr in database_receivers or self.references_database(
                    expression.value
                )
            if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Attribute):
                return self.references_database(expression.func.value)
            if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Name):
                return expression.func.id in self.bound_callables
            return False

        def bound_method_names(self, expression: ast.expr) -> set[str]:
            if isinstance(expression, ast.Attribute) and self.references_database(
                expression.value
            ):
                return {expression.attr}
            if isinstance(expression, ast.Name):
                return self.bound_callables.get(expression.id, set()).copy()
            return set()

        def target_bound_methods(
            self, target: ast.expr, value: ast.expr
        ) -> dict[str, set[str]]:
            if isinstance(target, ast.Name):
                methods = self.bound_method_names(value)
                return {target.id: methods} if methods else {}
            if isinstance(target, (ast.Tuple, ast.List)) and isinstance(
                value, (ast.Tuple, ast.List)
            ):
                methods: dict[str, set[str]] = {}
                for target_item, value_item in zip(target.elts, value.elts, strict=False):
                    methods.update(self.target_bound_methods(target_item, value_item))
                return methods
            return {}

        def assign_aliases(self, target: ast.expr, value: ast.expr) -> None:
            is_database_alias = self.references_database(value)
            bound_methods = self.target_bound_methods(target, value)
            for name in self.assigned_names(target):
                self.aliases.discard(name)
                self.bound_callables.pop(name, None)
                if is_database_alias:
                    self.aliases.add(name)
            for name, methods in bound_methods.items():
                self.aliases.add(name)
                self.bound_callables[name] = methods

        def assigned_names(self, target: ast.expr) -> set[str]:
            if isinstance(target, ast.Name):
                return {target.id}
            if isinstance(target, (ast.Tuple, ast.List)):
                return set().union(*(self.assigned_names(item) for item in target.elts))
            return set()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            saved_aliases = self.aliases
            saved_bound_callables = self.bound_callables
            local_aliases = set(saved_aliases)
            local_bound_callables = {
                name: methods.copy() for name, methods in saved_bound_callables.items()
            }
            arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            if node.args.vararg:
                arguments.append(node.args.vararg)
            if node.args.kwarg:
                arguments.append(node.args.kwarg)
            for argument in arguments:
                local_aliases.discard(argument.arg)
                local_bound_callables.pop(argument.arg, None)
                if argument.arg in database_receivers:
                    local_aliases.add(argument.arg)
            self.aliases = local_aliases
            self.bound_callables = local_bound_callables
            for statement in node.body:
                self.visit(statement)
            self.aliases = saved_aliases
            self.bound_callables = saved_bound_callables

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Assign(self, node: ast.Assign) -> None:
            self.visit(node.value)
            for target in node.targets:
                self.assign_aliases(target, node.value)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if node.value is not None:
                self.visit(node.value)
                self.assign_aliases(node.target, node.value)

        def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
            self.visit(node.value)
            self.assign_aliases(node.target, node.value)

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            self.visit(node.value)
            for name in self.assigned_names(node.target):
                self.aliases.discard(name)
                self.bound_callables.pop(name, None)

        def visit_Delete(self, node: ast.Delete) -> None:
            for target in node.targets:
                for name in self.assigned_names(target):
                    self.aliases.discard(name)
                    self.bound_callables.pop(name, None)

        def visit_If(self, node: ast.If) -> None:
            self.visit(node.test)
            before = set(self.aliases)
            before_callables = {
                name: methods.copy() for name, methods in self.bound_callables.items()
            }
            self.aliases = set(before)
            self.bound_callables = {
                name: methods.copy() for name, methods in before_callables.items()
            }
            for statement in node.body:
                self.visit(statement)
            body_aliases = set(self.aliases)
            body_callables = {
                name: methods.copy() for name, methods in self.bound_callables.items()
            }
            self.aliases = set(before)
            self.bound_callables = {
                name: methods.copy() for name, methods in before_callables.items()
            }
            for statement in node.orelse:
                self.visit(statement)
            else_aliases = set(self.aliases)
            else_callables = {
                name: methods.copy() for name, methods in self.bound_callables.items()
            }
            self.aliases = body_aliases | else_aliases
            self.bound_callables = {}
            for name in body_callables.keys() | else_callables.keys():
                methods = body_callables.get(name, set()) | else_callables.get(name, set())
                if methods:
                    self.bound_callables[name] = methods

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Attribute):
                method = node.func.attr
                if method in {"commit", "rollback"} or (
                    method in (direct_database_methods | database_acquisition_methods)
                    and self.references_database(node.func.value)
                ):
                    offenders.append(f"{path}:{node.lineno} direct database call {method}()")
            elif isinstance(node.func, ast.Name):
                methods = self.bound_callables.get(node.func.id, set())
                forbidden_methods = methods.intersection(
                    direct_database_methods | database_acquisition_methods | {"commit", "rollback"}
                )
                offenders.extend(
                    f"{path}:{node.lineno} direct database call {method}()"
                    for method in sorted(forbidden_methods)
                )
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


def test_router_guard_drops_connection_alias_after_reassignment() -> None:
    source = (
        "def route(session):\n"
        "    connection = session.connection()\n"
        "    connection = make_client()\n"
        "    connection.execute(statement)\n"
        "    adapter = make_adapter()\n"
        "    adapter.execute(statement)\n"
        "    adapter.connect().execute(statement)\n"
    )

    violations = _router_boundary_violations(source, "app/dashboard/router.py")
    assert len(violations) == 1
    assert "connection()" in violations[0]


def test_global_router_guard_tracks_session_derived_method_chains() -> None:
    mutations = {
        "app/dashboard/router.py": (
            "def route(session):\n"
            "    session.get_bind().execute(statement)\n"
        ),
        "app/inventory/router.py": (
            "def route(session):\n"
            "    session.get_bind().connect().exec_driver_sql(statement)\n"
        ),
        "app/users/router.py": (
            "def route(session):\n"
            "    engine = session.get_bind()\n"
            "    engine.connect().exec_driver_sql(statement)\n"
        ),
        "app/warehouse/router.py": (
            "def route(session):\n"
            "    local_session = session\n"
            "    engine = local_session.get_bind()\n"
            "    local_engine = engine\n"
            "    local_engine.connect().execute(statement)\n"
        ),
    }

    for path, mutation in mutations.items():
        violations = _router_boundary_violations(mutation, path)
        assert violations, (
            f"global router guard missed session-derived chain in {path}: {mutation!r}"
        )


def test_global_router_guard_rejects_session_derived_connection_acquisition() -> None:
    mutations = {
        "app/dashboard/router.py": "session.get_bind()\n",
        "app/inventory/router.py": "session.connection()\n",
        "app/warehouse/router.py": "session.get_bind().connect()\n",
    }

    for path, mutation in mutations.items():
        violations = _router_boundary_violations(mutation, path)
        assert violations, (
            f"global router guard missed connection acquisition in {path}: {mutation!r}"
        )


def test_router_guard_drops_session_derived_alias_and_ignores_service_calls() -> None:
    source = (
        "def route(session):\n"
        "    engine = session.get_bind()\n"
        "    engine = make_engine()\n"
        "    engine.connect().exec_driver_sql(statement)\n"
        "    _service(session).get()\n"
        "    make_adapter().connect().execute(statement)\n"
    )

    violations = _router_boundary_violations(source, "app/dashboard/router.py")
    assert len(violations) == 1
    assert "get_bind()" in violations[0]


def test_router_guard_ignores_service_and_factory_method_chains() -> None:
    source = (
        "def route(session):\n"
        "    _service(session).get()\n"
        "    make_adapter().connect().execute(statement)\n"
        "    make_repository().list()\n"
    )

    assert _router_boundary_violations(source, "app/dashboard/router.py") == []


def test_global_router_guard_tracks_tainted_bound_database_methods() -> None:
    mutations = {
        "app/dashboard/router.py": (
            "def route(session):\n"
            "    acquire = session.get_bind\n"
            "    engine = acquire()\n"
            "    engine.connect().exec_driver_sql(statement)\n"
        ),
        "app/inventory/router.py": (
            "def route(session):\n"
            "    connect = session.connection\n"
            "    connection = connect()\n"
            "    connection.exec_driver_sql(statement)\n"
        ),
        "app/users/router.py": (
            "def route(session):\n"
            "    db = session\n"
            "    (acquire,) = (db.connection,)\n"
            "    connect = acquire\n"
            "    connection = connect()\n"
            "    connection.execute(statement)\n"
        ),
        "app/warehouse/router.py": (
            "def route(session):\n"
            "    (bind, connection) = (session.get_bind, session.connection)\n"
            "    engine = bind()\n"
            "    conn = connection()\n"
            "    engine.connect().execute(statement)\n"
            "    conn.execute(statement)\n"
        ),
        "app/audit/router.py": (
            "def route(session):\n"
            "    execute = session.execute\n"
            "    add = session.add\n"
            "    execute(statement)\n"
            "    add(record)\n"
        ),
    }

    for path, mutation in mutations.items():
        violations = _router_boundary_violations(mutation, path)
        assert violations, (
            f"global router guard missed bound database method in {path}: {mutation!r}"
        )


def test_router_guard_tracks_bound_methods_until_safe_reassignment() -> None:
    source = (
        "def route(session):\n"
        "    acquire = session.connection\n"
        "    safe_acquire = acquire\n"
        "    acquire = make_connection\n"
        "    safe_adapter = acquire()\n"
        "    safe_adapter.execute(statement)\n"
        "    connection = safe_acquire()\n"
        "    connection.execute(statement)\n"
    )

    violations = _router_boundary_violations(source, "app/dashboard/router.py")
    assert len(violations) == 2
    assert all("connection()" in violation or "execute()" in violation for violation in violations)


def test_router_guard_ignores_untainted_bound_factory_methods() -> None:
    source = (
        "def route(session):\n"
        "    adapter = make_adapter()\n"
        "    connect = adapter.connect\n"
        "    connection = connect()\n"
        "    connection.execute(statement)\n"
        "    _service(session).get()\n"
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
