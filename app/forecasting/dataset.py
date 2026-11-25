"""Load a verified M5 bundle without modifying or exposing raw records."""

import hashlib
from pathlib import Path

from app.analytics.export import _bounded_read, _verify, canonical_json
from app.analytics.ingestion import checked_path
from app.analytics.schemas import MAX_INPUT_BYTES, DailyObservation, ReportedSalesObservation
from app.forecasting.schemas import ForecastConfig, ForecastDataset, Observation


class FixtureNotAllowed(ValueError):
    """A verified fixture requires an explicit offline opt-in."""


def load_dataset(
    bundle_dir: Path, config: ForecastConfig, *, allow_fixture: bool = False
) -> ForecastDataset:
    manifest = _verify(bundle_dir)
    admission = manifest.admission
    if (
        manifest.data_version != config.data_version
        or admission.dataset_class != config.dataset_class
        or admission.target != config.target
    ):
        raise ValueError("bundle does not match config")
    if admission.dataset_class == "fixture" and allow_fixture is not True:
        raise FixtureNotAllowed("fixture requires opt-in")
    if config.mode == "research":
        if manifest.schema_version != "demand-data-bundle/2":
            raise ValueError("research bundle required")
        mappings = admission.mappings
        keys = {(m.product_key, m.reporting_entity_key, m.unit) for m in mappings}
        model = ReportedSalesObservation
    else:
        binding = config.binding
        if (
            manifest.schema_version != "demand-data-bundle/1"
            or binding is None
            or (
                admission.business_timezone != config.business_timezone
                or not admission.source.availability_policy_ref
            )
        ):
            raise ValueError("operational bundle and availability policy required")
        if any(
            part.start < admission.window_start or part.end > admission.window_end
            for part in config.partitions
        ):
            raise ValueError("partition outside source-supported dates")
        keys = {(binding.product_key, binding.warehouse_key, binding.unit)}
        if not any((m.product_key, m.warehouse_key, m.unit) in keys for m in admission.mappings):
            raise ValueError("binding does not match admission")
        model = DailyObservation
    if len(keys) != 1 or next(iter(keys))[2] != config.unit:
        raise ValueError("single matching series required")
    product, location, unit = next(iter(keys))
    body = _bounded_read(checked_path(bundle_dir / "observations.jsonl"), MAX_INPUT_BYTES)
    if hashlib.sha256(body).hexdigest() != manifest.artifacts["observations.jsonl"]:
        raise ValueError("bundle changed during read")
    observations = []
    for line in body.splitlines():
        row = model.model_validate_json(line)
        row_location = row.reporting_entity_key if config.mode == "research" else row.warehouse_key
        if (row.product_key, row_location, row.unit) != (product, location, unit):
            if config.mode == "research":
                raise ValueError("multiple research series")
            continue
        observations.append(
            Observation(
                day=row.business_date, value=row.target_quantity, available_at=row.available_at
            )
        )
    if not observations:
        raise ValueError("empty series")
    return ForecastDataset(
        config=config,
        series_key="fsk1-"
        + hashlib.sha256(
            canonical_json(
                [
                    admission.source.namespace,
                    product,
                    location,
                    unit,
                    config.target,
                    config.reporting_scope,
                ]
            )
        ).hexdigest(),
        observations=tuple(observations),
        limitations=manifest.limitations,
        knowledge_bound=admission.source.available_at_upper_bound,
        admission_cutoff=admission.cutoff,
    )
