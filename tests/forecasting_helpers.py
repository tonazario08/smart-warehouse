from datetime import UTC, date, datetime, timedelta

from app.forecasting.schemas import (
    ForecastConfig,
    ForecastDataset,
    ForecastProtocol,
    ModelConfig,
    Observation,
    Partition,
)


def config(**changes):
    values = dict(
        schema_version="forecast-config/1",
        mode="research",
        dataset_class="fixture",
        data_version="ddv2-" + "a" * 64,
        target="reported_daily_unit_sales",
        reporting_scope="company_aggregate",
        unit="unit",
        feature_version="lag-calendar/1",
        knowledge_time_mode="retrospective_final_vintage",
        protocol=ForecastProtocol(
            schema_version="forecast-protocol/1",
            partitions=tuple(
                Partition(name=name, start=date(year, 1, 1), end=date(year + 1, 1, 1))
                for name, year in (("train", 2020), ("validation", 2021), ("final_holdout", 2022))
            ),
            horizons=(1, 7),
            history_days=28,
            imputation="none",
        ),
        candidates=(ModelConfig(max_depth=2), ModelConfig(max_depth=3)),
    )
    protocol_changes = {
        key: changes.pop(key)
        for key in ("partitions", "horizons", "history_days", "imputation")
        if key in changes
    }
    if changes.get("mode") == "operational":
        partitions = protocol_changes.get("partitions", values["protocol"].partitions)
        if len(partitions) == 3:
            protocol_changes.update(
                train_information_cutoff=datetime.combine(
                    partitions[1].start, datetime.min.time(), UTC
                )
                - timedelta(days=1),
                selection_information_cutoff=datetime.combine(
                    partitions[2].start, datetime.min.time(), UTC
                )
                - timedelta(days=1),
                refit_information_cutoff=datetime.combine(
                    partitions[2].start, datetime.min.time(), UTC
                )
                - timedelta(days=1),
            )
    if protocol_changes:
        values["protocol"] = ForecastProtocol(
            **{**values["protocol"].model_dump(), **protocol_changes}
        )
    values.update(changes)
    return ForecastConfig(**values)


def dataset(*, missing=(), future_value=1, available_at=None):
    start = date(2020, 1, 1)
    rows = tuple(
        Observation(
            day=start + timedelta(days=i),
            value=None if i in missing else (float(i + 1) if i < 28 else float(future_value)),
            available_at=available_at or datetime(2022, 1, 1, tzinfo=UTC),
        )
        for i in range(40)
    )
    return ForecastDataset(
        config=config(), series_key="synthetic", observations=rows, limitations=()
    )
