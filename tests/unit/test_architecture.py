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


def test_category_router_module_has_no_sql_or_transaction_operations() -> None:
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


def test_legacy_router_contains_only_deferred_product_and_supplier_routes() -> None:
    path = Path("app/master_data/_legacy_router.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    routes: set[tuple[str, str]] = set()
    handlers: set[str] = set()
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    route_methods = {"get", "post", "put", "patch", "delete", "api_route", "route"}
    nested_route_registrations = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"include_router", "add_api_route"}
    ]

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr not in route_methods:
                continue
            if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                continue
            route_path = decorator.args[0].value
            if isinstance(route_path, str):
                handlers.add(node.name)
                routes.add((decorator.func.attr, route_path))

    assert handlers == {
        "list_products",
        "get_product",
        "create_product",
        "update_product",
        "delete_product",
        "list_suppliers",
        "get_supplier",
        "create_supplier",
        "update_supplier",
        "delete_supplier",
    }
    assert functions == handlers | {"_page"}
    assert nested_route_registrations == []
    assert routes == {
        ("get", "/products"),
        ("get", "/products/{product_id}"),
        ("post", "/products"),
        ("put", "/products/{product_id}"),
        ("delete", "/products/{product_id}"),
        ("get", "/suppliers"),
        ("get", "/suppliers/{supplier_id}"),
        ("post", "/suppliers"),
        ("put", "/suppliers/{supplier_id}"),
        ("delete", "/suppliers/{supplier_id}"),
    }
