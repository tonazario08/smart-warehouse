from datetime import UTC, date, datetime

import pytest


def test_supply_cannot_be_known_before_it_is_ordered():
    from pydantic import ValidationError

    from app.replenishment.schemas import SupplyOrder

    with pytest.raises(ValidationError):
        SupplyOrder(
            order_id="supply",
            quantity=5,
            unit="unit",
            ordered_at=datetime(2022, 6, 30, tzinfo=UTC),
            known_at=datetime(2022, 6, 29, tzinfo=UTC),
            due_date=date(2022, 7, 1),
        )


def test_verified_publication_reuses_bytes_and_rejects_tamper(tmp_path):
    from app.replenishment.artifacts import (
        publish_catalog,
        publish_run,
        verify_public_projection,
        verify_run,
    )
    from app.replenishment.calibration import calibrate
    from app.replenishment.inputs import load_inputs
    from app.replenishment.simulation import simulate
    from tests.replenishment_helpers import operational_context

    bundle, forecast, auth, config = operational_context(tmp_path)
    inputs = load_inputs(forecast, bundle, config, auth)
    result = simulate(inputs, calibrate(inputs, config), config)
    root = tmp_path / "results"
    published = publish_run(inputs, config, result, auth, root)
    original = {p.name: p.read_bytes() for p in published.path.iterdir()}
    assert verify_run(published.path, auth).run_id == published.run_id
    assert publish_run(inputs, config, result, auth, root).run_id == published.run_id
    assert {p.name: p.read_bytes() for p in published.path.iterdir()} == original
    projection = publish_catalog(published.path, auth, tmp_path / "catalog")
    assert projection.is_dir()
    assert verify_public_projection(projection)["run_id"] == published.run_id
    from tests.reconcile_replenishment_run import reconcile

    assert reconcile(published.path, forecast, bundle, config, auth) == {
        "status": "reconciled",
        "cases": 36,
        "days": 6408,
    }
    first = (published.path / "days.jsonl").read_text(encoding="utf8").splitlines()[0]
    import hashlib
    import json

    assert set(json.loads(first)["case"]) == {"algorithm", "horizon", "service", "policy"}
    from app.analytics.export import canonical_json

    private_summary_path = published.path / "summaries.json"
    private_manifest_path = published.path / "manifest.json"
    private_summary_original = private_summary_path.read_bytes()
    private_manifest_original = private_manifest_path.read_bytes()
    private_summary = json.loads(private_summary_original)
    private_summary[0]["summary"]["fill_rate"] = "0.123"
    private_body = canonical_json(private_summary)
    private_summary_path.write_bytes(private_body)
    private_manifest = json.loads(private_manifest_original)
    private_manifest["scientific_files"]["summaries.json"] = hashlib.sha256(
        private_body
    ).hexdigest()
    private_manifest_path.write_bytes(canonical_json(private_manifest))
    with pytest.raises(ValueError):
        reconcile(published.path, forecast, bundle, config, auth)
    private_summary_path.write_bytes(private_summary_original)
    private_manifest_path.write_bytes(private_manifest_original)

    public_summary_original = (projection / "summaries.json").read_bytes()
    public_manifest_original = (projection / "public-manifest.json").read_bytes()
    summaries = json.loads(public_summary_original)
    manifest = json.loads(public_manifest_original)
    manifest["config"]["initial_on_hand"] += 1
    for case in summaries:
        case["initial_on_hand"] += 1
    body = canonical_json(summaries)
    (projection / "summaries.json").write_bytes(body)
    manifest["artifacts"]["summaries.json"] = hashlib.sha256(body).hexdigest()
    manifest.pop("projection_sha256")
    manifest["projection_sha256"] = hashlib.sha256(canonical_json(manifest)).hexdigest()
    (projection / "public-manifest.json").write_bytes(canonical_json(manifest))
    with pytest.raises(ValueError, match="opening stock mismatch"):
        verify_public_projection(projection)
    (projection / "summaries.json").write_bytes(public_summary_original)
    (projection / "public-manifest.json").write_bytes(public_manifest_original)

    summaries = json.loads(public_summary_original)
    summaries[0]["summary"]["fill_rate"] = "0.123"
    body = canonical_json(summaries)
    (projection / "summaries.json").write_bytes(body)
    manifest = json.loads((projection / "public-manifest.json").read_bytes())
    manifest["artifacts"]["summaries.json"] = hashlib.sha256(body).hexdigest()
    manifest.pop("projection_sha256")
    manifest["projection_sha256"] = hashlib.sha256(canonical_json(manifest)).hexdigest()
    (projection / "public-manifest.json").write_bytes(canonical_json(manifest))
    with pytest.raises(ValueError):
        verify_public_projection(projection)
    (projection / "summaries.json").write_bytes(b"[]\n")
    with pytest.raises(ValueError):
        verify_public_projection(projection)
    forecast_predictions = forecast / "predictions.jsonl"
    forecast_original = forecast_predictions.read_bytes()
    forecast_predictions.write_bytes(b"{}\n")
    with pytest.raises(ValueError, match="MISMATCH"):
        reconcile(published.path, forecast, bundle, config, auth)
    forecast_predictions.write_bytes(forecast_original)
    (published.path / "days.jsonl").write_bytes(b"{}\n")
    with pytest.raises(ValueError):
        verify_run(published.path, auth)
