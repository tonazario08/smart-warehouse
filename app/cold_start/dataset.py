"""Read verified M5 fixture bundles under a confined input root."""

import hashlib
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from app.analytics.export import _bounded_read, _verify
from app.analytics.ingestion import checked_path
from app.analytics.schemas import MAX_INPUT_BYTES, DailyObservation
from app.cold_start.schemas import ColdStartConfig, ColdStartDataset, Observation, Series


def load_fixture_dataset(config: ColdStartConfig, input_root: Path) -> ColdStartDataset:
    config = ColdStartConfig.model_validate(config.model_dump())
    root = checked_path(Path(input_root), directory=True)
    if config.created_at.utcoffset() is None:
        raise ValueError("timezone required")
    partitions = config.partitions
    if (
        len(partitions) != 3
        or tuple(p.name for p in partitions) != ("train", "validation", "holdout")
        or any(
            p.start > p.end
            or p.start <= date.min + timedelta(days=7)
            or p.end >= date.max - timedelta(days=1)
            for p in partitions
        )
        or any(a.end >= b.start for a, b in zip(partitions, partitions[1:], strict=False))
    ):
        raise ValueError("invalid partitions")
    if config.created_at < datetime.combine(partitions[-1].end + timedelta(days=1), time.min, UTC):
        raise ValueError("created_at precedes holdout endpoint")
    keys = set()
    identities = set()
    series = []
    for sku in sorted(config.skus, key=lambda x: x.product_key):
        relative = Path(sku.bundle_path)
        if (
            relative.is_absolute()
            or len(relative.parts) != 1
            or relative.name != sku.data_version
            or "/" in sku.bundle_path
            or "\\" in sku.bundle_path
            or ":" in sku.bundle_path
        ):
            raise ValueError("unsafe bundle path")
        if sku.product_key in keys:
            raise ValueError("duplicate sku")
        keys.add(sku.product_key)
        if sku.snapshot.available_at.utcoffset() is None:
            raise ValueError("timezone required")
        if sku.snapshot.available_at > config.created_at:
            raise ValueError("snapshot after created_at")
        path = checked_path(root / relative, directory=True)
        if not path.is_relative_to(root):
            raise ValueError("unsafe bundle path")
        manifest = _verify(path)
        admission = manifest.admission
        if admission.cutoff > config.created_at:
            raise ValueError("admission cutoff after created_at")
        if (
            manifest.schema_version != "demand-data-bundle/1"
            or manifest.data_version != sku.data_version
            or admission.dataset_class != "fixture"
            or admission.target != config.target
            or admission.business_timezone != "UTC"
            or not admission.source.availability_policy_ref
            or any(
                p.start < admission.window_start or p.end >= admission.window_end
                for p in partitions
            )
            or not any(
                (m.product_key, m.warehouse_key, m.unit)
                == (sku.product_key, sku.warehouse_key, sku.unit)
                for m in admission.mappings
            )
        ):
            raise ValueError("bundle metadata mismatch")
        identities.add((admission.source.namespace, sku.warehouse_key, sku.unit))
        body = _bounded_read(checked_path(path / "observations.jsonl"), MAX_INPUT_BYTES)
        if hashlib.sha256(body).hexdigest() != manifest.artifacts["observations.jsonl"]:
            raise ValueError("bundle changed during read")
        rows = []
        for line in body.splitlines():
            row = DailyObservation.model_validate_json(line)
            if (row.product_key, row.warehouse_key, row.unit) == (
                sku.product_key,
                sku.warehouse_key,
                sku.unit,
            ):
                rows.append(
                    Observation(
                        day=row.business_date,
                        value=row.target_quantity,
                        available_at=row.available_at,
                    )
                )
        if not rows or len(rows) > 366:
            raise ValueError("invalid series length")
        series.append(Series(sku=sku, observations=tuple(rows), admission_cutoff=admission.cutoff))
    if len(identities) != 1 or {s.sku.split for s in series} != {"train", "validation", "holdout"}:
        raise ValueError("incompatible population")
    return ColdStartDataset(
        config=config, series=tuple(series), namespace=next(iter(identities))[0]
    )
