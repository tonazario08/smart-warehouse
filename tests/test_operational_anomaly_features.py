"""Operational feature boundaries: validated lineage and exact as-of day coverage."""

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.anomalies import operational_features as features


def _proof_file(tmp_path, rows, dataset_class="operational"):
    path = tmp_path / "coverage.json"
    payload = json.dumps(
        {
            "schema_version": "b2b-outbound-coverage/1",
            "dataset_class": dataset_class,
            "rows": rows,
        }
    ).encode()
    path.write_bytes(payload)
    return path, hashlib.sha256(payload).hexdigest()


def _claim():
    claim = SimpleNamespace(
        transaction_id=100,
        outbound_id=300,
        purchase_request_id=110,
        warehouse_id=20,
        product_id=22,
        quantity=21,
        unit="each",
        occurred_at=datetime(2026, 10, 24, 23, 30, tzinfo=UTC),
    )
    claim.source_fingerprint = features.lineage_fingerprint(
        **vars(claim),
        performed_by_id=5,
        request_reference="PR-test",
        quantity_before=30,
        quantity_after=30 - claim.quantity,
    )
    return claim


def _row(claim):
    instant = claim.occurred_at
    return SimpleNamespace(
        transaction_id=claim.transaction_id,
        transaction_type="outbound",
        inbound_id=None,
        purpose="purchase_request_fulfillment",
        transfer_id=None,
        decision_kind="approved",
        status="fulfilled",
        outbound_id=claim.outbound_id,
        voucher_id=claim.outbound_id,
        workflow_outbound=claim.outbound_id,
        request_id=claim.purchase_request_id,
        workflow_request=claim.purchase_request_id,
        request_number="PR-test",
        outbound_reference="PR-test",
        requester=4,
        workflow_requester=4,
        decided_by_id=3,
        fulfilled_by_id=5,
        outbound_actor=5,
        transaction_actor=5,
        product_id=claim.product_id,
        request_product=claim.product_id,
        outbound_product=claim.product_id,
        warehouse_id=claim.warehouse_id,
        request_warehouse=claim.warehouse_id,
        outbound_warehouse=claim.warehouse_id,
        quantity=claim.quantity,
        outbound_quantity=claim.quantity,
        request_quantity=claim.quantity,
        quantity_before=30,
        quantity_after=30 - claim.quantity,
        request_at=instant - timedelta(minutes=3),
        decided_at=instant - timedelta(minutes=2),
        outbound_at=instant - timedelta(seconds=2),
        transaction_at=instant - timedelta(seconds=1),
        fulfilled_at=instant,
        product_name="Test product",
        product_sku="TEST-1",
        warehouse_name="Test warehouse",
        warehouse_code="TEST-W",
    )


def _session(rows):
    return SimpleNamespace(
        execute=lambda query: SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: rows))
    )


def _rows(claim, day_events):
    result = []
    for delta in range(7, 0, -1):
        day = claim.occurred_at.date() - timedelta(days=delta)
        result.append(
            {
                "warehouse_id": claim.warehouse_id,
                "product_id": claim.product_id,
                "unit": claim.unit,
                "day": day.isoformat(),
                "available_at": f"{day + timedelta(days=1)}T00:00:00Z",
                "complete": True,
                "events_digest": features.coverage_events_digest(day_events.get(day, ())),
            }
        )
    return result


def test_lineage_rejects_coherent_actor_reference_and_stock_drift():
    claim = _claim()
    actor = _row(claim)
    actor.fulfilled_by_id = actor.outbound_actor = actor.transaction_actor = 8
    reference = _row(claim)
    reference.request_number = reference.outbound_reference = "PR-replacement"
    stock = _row(claim)
    stock.quantity_before += 1
    stock.quantity_after += 1
    for row in (actor, reference, stock):
        assert features.resolve_lineage(_session([row]), claim) is None


def test_lineage_requires_exact_transaction_to_workflow_and_voucher():
    claim = _claim()
    row = _row(claim)
    result = features.resolve_lineage(_session([row]), claim)
    assert (result.outbound_id, result.quantity, result.performed_by_id) == (300, 21, 5)
    row.voucher_id = claim.transaction_id
    assert features.resolve_lineage(_session([row]), claim) is None
    row.voucher_id = claim.outbound_id
    row.workflow_outbound = claim.transaction_id
    assert features.resolve_lineage(_session([row]), claim) is None


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("purpose", "legacy_unknown"),
        ("quantity_after", -1),
        ("transaction_actor", 99),
        ("outbound_reference", "OTHER"),
        ("decided_by_id", None),
        ("transfer_id", 1),
        ("warehouse_id", 22),
        ("fulfilled_at", datetime(2026, 10, 24, 23, 30)),
    ],
)
def test_lineage_rejects_drift(field, replacement):
    claim = _claim()
    row = _row(claim)
    setattr(row, field, replacement)
    assert features.resolve_lineage(_session([row]), claim) is None


def test_loaded_coverage_binds_exact_history_and_excludes_current_day(tmp_path, monkeypatch):
    claim = _claim()
    row = _row(claim)
    historical = _claim()
    historical.occurred_at -= timedelta(days=2)
    historical.transaction_id = 90
    historical.quantity = 14
    history_row = _row(historical)
    current_day = _claim()
    current_day.occurred_at = claim.occurred_at.replace(hour=0, minute=0)
    current_day.transaction_id = 99
    current_row = _row(current_day)
    rows = _rows(
        claim,
        {historical.occurred_at.date(): [(90, 14, historical.occurred_at)]},
    )
    path, digest = _proof_file(tmp_path, rows)
    release = features.load_coverage(path, digest)
    monkeypatch.setattr(features, "_history", lambda *args: [history_row, current_row])
    values, fingerprint = features.build_features(_session([row]), claim, release)
    assert values == pytest.approx(
        (math.log1p(21), 1, 5 / 6, math.log1p(2), math.log1p(1), math.log1p(7))
    )
    assert len(fingerprint) == 64
    monkeypatch.setattr(features, "_history", lambda *args: [])
    assert features.build_features(_session([row]), claim, release) is None


def test_complete_empty_history_not_confused_with_missing_or_future_proof(tmp_path, monkeypatch):
    claim = _claim()
    monkeypatch.setattr(features, "_history", lambda *args: [])
    rows = _rows(claim, {})
    path, digest = _proof_file(tmp_path, rows)
    release = features.load_coverage(path, digest)
    values, _ = features.build_features(_session([_row(claim)]), claim, release)
    assert values[3:5] == (0, 0)
    rows[-1]["available_at"] = "2026-10-25T00:00:00Z"
    path, digest = _proof_file(tmp_path, rows)
    assert (
        features.build_features(
            _session([_row(claim)]), claim, features.load_coverage(path, digest)
        )
        is None
    )
    path, digest = _proof_file(tmp_path, rows[:-1])
    assert (
        features.build_features(
            _session([_row(claim)]), claim, features.load_coverage(path, digest)
        )
        is None
    )


def test_coverage_approval_and_publication_boundaries(tmp_path):
    rows = _rows(_claim(), {})
    path, digest = _proof_file(tmp_path, rows)
    with pytest.raises(features.CoverageInvalid):
        features.load_coverage(path, "0" * 64)
    path, digest = _proof_file(tmp_path, [rows[0], rows[0]])
    with pytest.raises(features.CoverageInvalid):
        features.load_coverage(path, digest)
    rows[0]["available_at"] = f'{rows[0]["day"]}T23:59:59Z'
    path, digest = _proof_file(tmp_path, rows)
    with pytest.raises(features.CoverageInvalid):
        features.load_coverage(path, digest)



def test_synthetic_coverage_needs_explicit_opt_in(tmp_path):
    path, digest = _proof_file(tmp_path, _rows(_claim(), {}), "synthetic_test")
    with pytest.raises(features.CoverageInvalid):
        features.load_coverage(path, digest)
    result = features.load_coverage(path, digest, allow_synthetic_test=True)
    assert result.dataset_class == "synthetic_test"
