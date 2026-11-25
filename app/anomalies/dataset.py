"""Read an already verified M5 operational event bundle."""

import hashlib
import json
from pathlib import Path

from app.analytics.export import _bounded_read, _verify
from app.analytics.ingestion import checked_path
from app.analytics.schemas import MAX_INPUT_BYTES, EventRecord
from app.anomalies.schemas import AnomalyConfig, AnomalyDataset


def load_anomaly_dataset(config: AnomalyConfig, input_root: Path) -> AnomalyDataset:
    manifest = _verify(input_root)
    admission = manifest.admission
    if (
        manifest.schema_version != "demand-data-bundle/1"
        or admission.dataset_class != "fixture"
        or not config.allow_fixture
        or admission.target != "gross_fulfilled_units"
        or admission.source.representation != "events"
        or admission.business_timezone != "UTC"
        or manifest.data_version != config.data_version
        or config.created_at < admission.cutoff
    ):
        raise ValueError("verified UTC event fixture required")
    if any(
        p.start < admission.window_start or p.end > admission.window_end for p in config.partitions
    ):
        raise ValueError("partition outside source window")
    body = _bounded_read(checked_path(input_root / "records.jsonl"), MAX_INPUT_BYTES)
    if hashlib.sha256(body).hexdigest() != manifest.artifacts["records.jsonl"]:
        raise ValueError("bundle changed during read")
    events = []
    for line in body.splitlines():
        data = json.loads(line)
        data.pop("event_kind")
        data.pop("original_offset_seconds")
        event = EventRecord.model_validate(data)
        events.append(event)
        if len(events) > 10000:
            raise ValueError("event limit exceeded")
    return AnomalyDataset(
        config=config,
        admission=admission,
        events=tuple(events),
        source_hashes={**manifest.artifacts, "source": manifest.source_checksum},
    )
