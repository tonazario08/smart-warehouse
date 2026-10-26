import pytest
from sqlalchemy.engine import URL, make_url

from app.analytics.schemas import DatabaseIdentity, PipelineError
from app.analytics.snapshot import validate_database_url
from tests.postgres import test_purchase_request_migration as migration


def pair(
    port=18546,
    user="sw_m5_demand_test",
    test_db="sw_m5_demand_test",
    migration_db="sw_m5_demand_migration_test",
    host="127.0.0.1",
    driver="postgresql+psycopg",
):
    base = URL.create(driver, username=user, password="fixture-only", host=host, port=port)
    return (
        base.set(database=migration_db).render_as_string(hide_password=False),
        base.set(database=test_db).render_as_string(hide_password=False),
    )


@pytest.mark.parametrize(
    "values",
    [
        pair(),
        pair(18545, "sw_m4_requests_test", "sw_m4_requests_test", "sw_m4_requests_migration_test"),
    ],
)
def test_migration_pair_old_and_m5_allowed(values, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Guard must decide before any engine/DDL.")

    monkeypatch.setattr(migration, "create_engine", forbidden)
    migration_url, test_url = migration.validate_migration_pair(*values)
    assert migration_url.database != test_url.database


@pytest.mark.parametrize(
    "values",
    [
        ("", ""),
        pair(host="remote.example"),
        pair(port=18545),
        pair(user="sw_m4_requests_test"),
        pair(test_db="sw_m4_requests_test"),
        pair(migration_db="sw_m4_requests_migration_test"),
        pair(driver="postgresql"),
        pair(test_db="sw_m5_demand_migration_test"),
        (
            pair()[0],
            pair(
                18545, "sw_m4_requests_test", "sw_m4_requests_test", "sw_m4_requests_migration_test"
            )[1],
        ),
        (pair()[0], pair(host="localhost")[1]),
        (pair()[0], pair(user="wrong-user")[1]),
    ],
)
def test_migration_pair_hybrids_remote_and_missing_refused(values, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Guard must decide before any engine/DDL.")

    monkeypatch.setattr(migration, "create_engine", forbidden)
    with pytest.raises(ValueError, match="separate guarded"):
        migration.validate_migration_pair(*values)


@pytest.mark.parametrize(
    "query",
    [
        {"host": "unused.example.invalid"},
        {"hostaddr": "192.0.2.1"},
        {"port": "5432"},
        {"dbname": "other"},
        {"database": "other"},
        {"user": "other"},
        {"service": "other"},
        {"options": "-csearch_path=other"},
        {"connect_timeout": "0"},
        {"connect_timeout": ("5", "9")},
    ],
)
@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize(
    "values",
    [
        pair(),
        pair(18545, "sw_m4_requests_test", "sw_m4_requests_test", "sw_m4_requests_migration_test"),
    ],
)
def test_connection_query_cannot_override_guarded_identity(values, index, query, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Guard must reject overrides before creating any engine.")

    monkeypatch.setattr(migration, "create_engine", forbidden)
    changed = list(values)
    changed[index] = make_url(changed[index]).set(query=query).render_as_string(hide_password=False)
    with pytest.raises(ValueError, match="separate guarded"):
        migration.validate_migration_pair(*changed)


def test_safe_bounded_timeout_preserves_exact_pair():
    values = tuple(
        make_url(value).set(query={"connect_timeout": "5"}).render_as_string(hide_password=False)
        for value in pair()
    )
    assert migration.validate_migration_pair(*values)[0].port == 18546


IDENTITY = DatabaseIdentity(
    host="127.0.0.1", port=18546, database="sw_m5_demand_test", username="sw_m5_demand_test"
)


def test_snapshot_explicit_identity_accepts_safe_url_without_connection():
    value = make_url(pair()[1]).set(query={"connect_timeout": "5"})
    assert validate_database_url(value, IDENTITY) == value


@pytest.mark.parametrize(
    "query",
    [
        {key: "PRIVATE_OVERRIDE"}
        for key in (
            "host",
            "hostaddr",
            "port",
            "dbname",
            "database",
            "user",
            "service",
            "options",
        )
    ],
)
def test_snapshot_rejects_driver_override_before_connection(query):
    value = make_url(pair()[1]).set(query=query)
    with pytest.raises(PipelineError, match="DATABASE_IDENTITY"):
        validate_database_url(value, IDENTITY)
