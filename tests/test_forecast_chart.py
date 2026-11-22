from datetime import date, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.forecasting.repository import ForecastRepository
from app.forecasting.schemas import PredictionRow
from app.main import create_app
from app.models import UserRole

RUN_ID = "frv1-" + "9" * 64
BASE = f"/api/v1/forecasts/runs/{RUN_ID}"
PARAMS = {"horizon": "7", "algorithm": "xgboost", "lead": "6"}


def _row(index, *, series="series-a", horizon=7, lead=6, actual=None, algorithm="xgboost"):
    origin = date(2022, 1, 1) + timedelta(days=index)
    return PredictionRow(
        series_key=series, origin=origin, target_date=origin + timedelta(days=lead),
        lead=lead, horizon=horizon, algorithm=algorithm, prediction=2, actual=actual,
        unit="unit",
    )


def test_chart_latest_window_is_one_lead_and_one_series_and_table_contract_stays(
    unit_settings, monkeypatch,
):
    artifact = SimpleNamespace(binding=None, rows=tuple(reversed([
        *[_row(i, actual=0 if i == 18 else None) for i in range(48)],
        *[_row(i, lead=1) for i in range(48)],
        *[_row(i, series="series-b") for i in range(5)],
        *[_row(i, algorithm="seasonal_naive") for i in range(60)],
    ])))
    reads = []

    def read(_self, run_id, scopes):
        reads.append((run_id, scopes))
        return artifact

    monkeypatch.setattr(ForecastRepository, "get_scoped", read)
    actor = SimpleNamespace(role=UserRole.WAREHOUSE)
    app = create_app(unit_settings)
    with TestClient(app) as client:
        assert client.get(BASE + "/chart", params=PARAMS).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: actor
        response = client.get(BASE + "/chart", params=PARAMS)
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        payload = response.json()
        assert payload["series_key"] == "series-a"
        rows = payload["items"]
        assert len(rows) == 30
        assert [r["target_date"] for r in rows] == [
            _row(i).target_date.isoformat() for i in range(18, 48)
        ]
        assert all((r["series_key"], r["lead"], r["algorithm"]) == ("series-a", 6, "xgboost")
                   for r in rows)
        assert [r["actual"] for r in rows] == [0] + [None] * 29
        no_data = client.get(BASE + "/chart", params=PARAMS | {"lead": "3"})
        assert no_data.json() == {"series_key": None, "items": []}
        pages = [client.get(BASE + "/predictions", params={
            "horizon": 7, "algorithm": "xgboost", "page": page,
        }).json() for page in (1, 2)]
        assert [p["page_size"] for p in pages] == [20, 20]
        assert all(len(p["items"]) == 20 for p in pages)
        assert pages[0]["items"] != pages[1]["items"]
        assert client.get(BASE + "/chart", params=PARAMS).json() == payload
        assert all(scopes == ("operational",) for _, scopes in reads)

        total_reads = len(reads)
        bad = [
            PARAMS | {"horizon": "1"},
            PARAMS | {"horizon": "2"},
            PARAMS | {"lead": "8"},
            PARAMS | {"lead": "0"},
            PARAMS | {"page": "1"},
            {"horizon": "7", "algorithm": "xgboost"},
            [*PARAMS.items(), ("lead", "1")],
        ]
        for params in bad:
            assert client.get(BASE + "/chart", params=params).status_code == 422
        actor.role = UserRole.CLIENT
        assert client.get(BASE + "/chart", params=PARAMS).status_code == 403
        assert len(reads) == total_reads


def test_chart_short_window_is_not_padded_and_uses_stable_tie(unit_settings, monkeypatch):
    artifact = SimpleNamespace(binding=None, rows=(
        _row(3, series="series-a", horizon=1, lead=1, actual=0),
        _row(3, series="series-b", horizon=1, lead=1),
        _row(1, series="series-a", horizon=1, lead=1),
        _row(1, series="series-b", horizon=1, lead=1),
    ))
    monkeypatch.setattr(ForecastRepository, "get_scoped", lambda *_args: artifact)
    app = create_app(unit_settings)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.ADMIN)
    with TestClient(app) as client:
        result = client.get(BASE + "/chart", params=PARAMS | {"horizon": "1", "lead": "1"})
        assert result.status_code == 200
        assert result.json()["series_key"] == "series-a"
        assert [r["target_date"] for r in result.json()["items"]] == ["2022-01-03", "2022-01-05"]
        assert [r["actual"] for r in result.json()["items"]] == [None, 0]
