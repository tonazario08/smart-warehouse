"""Read-only verifier for owner-controlled public projections."""

import hashlib
import re
import stat
from datetime import UTC, date, timedelta
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from app.analytics.export import canonical_json
from app.analytics.ingestion import _bounded_read, _decode_json
from app.analytics.schemas import (
    AwareTime,
    Contract,
    Identifier,
    PipelineError,
    Unit,
    business_day_bounds,
    load_timezone,
)
from app.forecasting.schemas import ForecastProtocol, PredictionRow


class UnsupportedSchema(ValueError):
    pass


def _manifest(raw):
    decoded = _decode_json(raw.decode("utf-8"))
    if (
        isinstance(decoded, dict)
        and isinstance(decoded.get("schema_version"), str)
        and decoded["schema_version"] != "forecast-public-run/1"
    ):
        raise UnsupportedSchema("unsupported schema")
    return PublicManifest.model_validate_json(raw)


class FailureReceipt(Contract):
    state: Literal["failed"]
    error_code: Literal[
        "INPUT_INVALID", "INPUT_UNADMITTED", "OUTPUT_CONFLICT", "IO_UNAVAILABLE", "FIT_FAILED"
    ]
    mode: Literal["research", "operational"]
    dataset_class: Literal["research", "fixture"]
    reporting_scope: Literal["company_aggregate", "warehouse"]
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: AwareTime
    attempt_id: str = Field(pattern=r"^[0-9a-f]{32}$")

    @model_validator(mode="after")
    def scope_matches(self):
        if (self.mode, self.reporting_scope) not in (
            ("research", "company_aggregate"),
            ("operational", "warehouse"),
        ):
            raise ValueError("failure scope mismatch")
        if self.created_at.utcoffset() != timedelta(0):
            raise ValueError("failure time must be UTC")
        return self


class PublicBinding(Contract):
    product_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    product_key: Identifier
    warehouse_key: Identifier
    unit: Unit
    data_version: str
    approved_at: AwareTime
    available_at: AwareTime
    binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PublicManifest(Contract):
    schema_version: Literal["forecast-public-run/1"]
    run_id: str = Field(pattern=r"^frv1-[0-9a-f]{64}$")
    projection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: Literal["evaluation", "forecast"]
    mode: Literal["research", "operational"]
    dataset_class: Literal["research", "fixture"]
    data_version: str = Field(pattern=r"^ddv[12]-[0-9a-f]{64}$")
    target: Literal["reported_daily_unit_sales", "gross_fulfilled_units"]
    reporting_scope: Literal["company_aggregate", "warehouse"]
    unit: Unit
    protocol: ForecastProtocol
    knowledge_time_mode: Literal["retrospective_final_vintage", "historical_as_of"]
    business_timezone: str | None
    trained_through: date
    training_information_cutoff: AwareTime | None
    knowledge_bound: AwareTime | None
    admission_cutoff: AwareTime | None
    origin_start: date | None
    origin_end: date | None
    horizons: tuple[int, ...]
    generated_at: AwareTime
    limitations: tuple[str, ...]
    row_count: int = Field(ge=0, le=50000)
    artifacts: dict[str, str]
    binding: PublicBinding | None

    @model_validator(mode="after")
    def coherent(self):
        if (
            self.horizons != self.protocol.horizons
            or self.origin_start
            and (not self.origin_end or self.origin_start > self.origin_end)
            or self.origin_end
            and not self.origin_start
        ):
            raise ValueError("invalid public range")
        if self.mode == "research":
            if (
                (
                    self.target,
                    self.reporting_scope,
                    self.knowledge_time_mode,
                    self.business_timezone,
                )
                != (
                    "reported_daily_unit_sales",
                    "company_aggregate",
                    "retrospective_final_vintage",
                    None,
                )
                or self.kind != "evaluation"
                or not self.data_version.startswith("ddv2-")
                or self.binding is not None
            ):
                raise ValueError("invalid research projection")
            expected = tuple(
                (name, date(year, 1, 1), date(year + 1, 1, 1))
                for name, year in (("train", 2020), ("validation", 2021), ("final_holdout", 2022))
            )
            if (
                tuple((p.name, p.start, p.end) for p in self.protocol.partitions) != expected
                or self.horizons != (1, 7)
                or any(
                    (
                        self.protocol.train_information_cutoff,
                        self.protocol.selection_information_cutoff,
                        self.protocol.refit_information_cutoff,
                    )
                )
            ):
                raise ValueError("invalid research protocol")
        elif (
            (self.target, self.reporting_scope, self.knowledge_time_mode)
            != ("gross_fulfilled_units", "warehouse", "historical_as_of")
            or not self.business_timezone
            or not self.data_version.startswith("ddv1-")
            or self.binding is None
        ):
            raise ValueError("invalid operational projection")
        if self.binding and (
            self.binding.unit != self.unit or self.binding.data_version != self.data_version
        ):
            raise ValueError("public binding mismatch")
        if (
            tuple(p.name for p in self.protocol.partitions)
            != ("train", "validation", "final_holdout")
            or any(
                a.end > b.start
                for a, b in zip(
                    self.protocol.partitions, self.protocol.partitions[1:], strict=False
                )
            )
            or not self.horizons
            or len(set(self.horizons)) != len(self.horizons)
            or any(h not in (1, 7) for h in self.horizons)
        ):
            raise ValueError("invalid public protocol")
        if self.mode == "operational":
            try:
                load_timezone(self.business_timezone)
                train = self.protocol.train_information_cutoff
                selection = self.protocol.selection_information_cutoff
                refit = self.protocol.refit_information_cutoff
                if (
                    not train
                    or not selection
                    or not refit
                    or any(t.utcoffset() != timedelta(0) for t in (train, selection, refit))
                    or not train <= selection <= refit
                ):
                    raise ValueError("invalid public cutoffs")
                validation_bound = business_day_bounds(
                    self.protocol.partitions[1].start - timedelta(days=1), self.business_timezone
                )[1].astimezone(UTC)
                holdout_bound = business_day_bounds(
                    self.protocol.partitions[2].start - timedelta(days=1), self.business_timezone
                )[1].astimezone(UTC)
                if (
                    train > validation_bound
                    or selection > holdout_bound
                    or refit > holdout_bound
                    or self.training_information_cutoff != refit
                ):
                    raise ValueError("invalid public cutoffs")
            except PipelineError:
                raise ValueError("invalid public timezone") from None
        elif self.training_information_cutoff != self.admission_cutoff:
            raise ValueError("invalid retrospective provenance")
        if self.trained_through >= self.protocol.partitions[2].start:
            raise ValueError("invalid trained-through date")
        return self


class PublicRun(Contract):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    manifest: PublicManifest
    rows: tuple[PredictionRow, ...]
    metrics: dict | None
    binding: PublicBinding | None


def _checked(path: Path) -> Path:
    path = Path(path)
    if ".." in path.parts or str(path).startswith(("\\\\", "//")):
        raise ValueError("unsafe path")
    absolute = path.absolute()
    for part in (*reversed(absolute.parents), absolute):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("unsafe path")
    return absolute.resolve(strict=True)


def verify_catalog_run(
    path: Path, *, allow_fixture: bool = False, require_name: bool = True
) -> PublicRun:
    root = _checked(path)
    raw = _bounded_read(_checked(root / "public-manifest.json"), 256 * 1024 * 1024)
    decoded = _decode_json(raw.decode("utf-8"))
    if canonical_json(decoded) != raw:
        raise ValueError("noncanonical manifest")
    manifest = _manifest(raw)
    if (
        (require_name and root.name != manifest.run_id)
        or (require_name and root.parent.name != manifest.mode)
        or (manifest.dataset_class == "fixture" and allow_fixture is not True)
    ):
        raise ValueError("public scope mismatch")
    identity = {k: v for k, v in decoded.items() if k != "projection_sha256"}
    if hashlib.sha256(canonical_json(identity)).hexdigest() != manifest.projection_sha256:
        raise ValueError("public projection hash mismatch")
    extra = "metrics.json" if manifest.kind == "evaluation" else "binding.json"
    names = {"public-manifest.json", "predictions.jsonl", extra}
    if {p.name for p in root.iterdir()} != names or set(manifest.artifacts) != names - {
        "public-manifest.json"
    }:
        raise ValueError("public file set mismatch")
    contents, size = {}, len(raw)
    for name in sorted(manifest.artifacts):
        body = _bounded_read(_checked(root / name), 256 * 1024 * 1024 - size)
        size += len(body)
        if hashlib.sha256(body).hexdigest() != manifest.artifacts[name]:
            raise ValueError("public artifact hash mismatch")
        contents[name] = body
    lines = contents["predictions.jsonl"].splitlines(keepends=True)
    if len(lines) != manifest.row_count or len(lines) > 50000:
        raise ValueError("public row count mismatch")
    rows = tuple(PredictionRow.model_validate_json(line) for line in lines)
    if len({row.target_date for row in rows}) > 10000:
        raise ValueError("public calendar limit")
    if b"".join(canonical_json(row) for row in rows) != contents["predictions.jsonl"]:
        raise ValueError("noncanonical rows")
    if tuple(rows) != tuple(
        sorted(
            rows, key=lambda row: (row.horizon, row.algorithm, row.series_key, row.origin, row.lead)
        )
    ):
        raise ValueError("public row order mismatch")
    groups = {}
    for row in rows:
        if (
            row.unit != manifest.unit
            or row.horizon not in manifest.horizons
            or ((row.actual is None) != (manifest.kind == "forecast"))
        ):
            raise ValueError("public prediction mismatch")
        groups.setdefault((row.horizon, row.algorithm, row.series_key, row.origin), []).append(row)
    if manifest.kind == "forecast":
        identities = {(row.series_key, row.origin) for row in rows}
        if len(identities) != 1:
            raise ValueError("forecast requires one nonempty series and origin")
        series, origin = next(iter(identities))
        required = {
            (horizon, algorithm, series, origin)
            for horizon in manifest.horizons
            for algorithm in ("persistence", "seasonal_naive", "xgboost")
        }
        if set(groups) != required:
            raise ValueError("forecast horizon population mismatch")
        if (
            manifest.trained_through > origin
            or manifest.training_information_cutoff
            > business_day_bounds(origin, manifest.business_timezone)[1]
        ):
            raise ValueError("forecast knowledge after origin")
    else:
        holdout = manifest.protocol.partitions[2]
        if any(not holdout.start <= row.target_date < holdout.end for row in rows):
            raise ValueError("evaluation target outside holdout")
    for (horizon, _, series, origin), members in groups.items():
        if tuple(r.lead for r in members) != tuple(range(1, horizon + 1)):
            raise ValueError("incomplete group")
        for algorithm in ("persistence", "seasonal_naive", "xgboost"):
            other = groups.get((horizon, algorithm, series, origin))
            if other is None or tuple(r.actual for r in members) != tuple(r.actual for r in other):
                raise ValueError("inconsistent groups")
    if (
        min((r.origin for r in rows), default=None),
        max((r.origin for r in rows), default=None),
    ) != (manifest.origin_start, manifest.origin_end):
        raise ValueError("origin range mismatch")
    auxiliary = _decode_json(contents[extra].decode("utf-8"))
    if canonical_json(auxiliary) != contents[extra]:
        raise ValueError("noncanonical auxiliary")
    binding, metrics = manifest.binding, None
    if manifest.kind == "forecast":
        file_binding = PublicBinding.model_validate_json(contents[extra])
        if binding != file_binding:
            raise ValueError("public binding mismatch")
    else:
        # score imports only Python contracts; native ML modules are never imported or called.
        from app.forecasting.evaluation import score

        metrics = auxiliary
        expected = {}
        for horizon in manifest.horizons:
            for algorithm in ("persistence", "seasonal_naive", "xgboost"):
                subset = tuple(r for r in rows if r.horizon == horizon and r.algorithm == algorithm)
                expected[f"{algorithm}:{horizon}"] = score(subset).model_dump(mode="json")
        if metrics != expected:
            raise ValueError("public metrics mismatch")
    return PublicRun(manifest=manifest, rows=rows, metrics=metrics, binding=binding)


class ForecastRepository:
    def __init__(self, root: Path | None, *, allow_fixture: bool = False):
        self.root = root
        self.allow_fixture = allow_fixture

    def _root(self):
        if self.root is None:
            raise OSError("catalog unavailable")
        root = _checked(self.root)
        if not root.is_dir():
            raise OSError("catalog unavailable")
        return root

    def list_scope(self, mode: Literal["research", "operational"]) -> tuple[PublicRun, ...]:
        root = self._root()
        folder = root / mode
        if not folder.exists():
            return ()
        folder = _checked(folder)
        entries = tuple(folder.iterdir())
        if len(entries) > 1000:
            raise ValueError("catalog size limit")
        runs = []
        for entry in entries:
            if entry.name == "failures":
                continue
            if re.fullmatch(r"frv1-[0-9a-f]{64}", entry.name) is None:
                raise ValueError("invalid catalog entry")
            raw = _bounded_read(_checked(entry / "public-manifest.json"), 256 * 1024 * 1024)
            manifest = _manifest(raw)
            if manifest.dataset_class == "fixture" and not self.allow_fixture:
                continue
            run = verify_catalog_run(entry, allow_fixture=self.allow_fixture)
            if run.manifest.mode != mode:
                raise ValueError("catalog scope mismatch")
            runs.append(run)
        return tuple(
            sorted(
                runs, key=lambda run: (run.manifest.generated_at, run.manifest.run_id), reverse=True
            )
        )

    def latest_failure(self, mode):
        folder = self._root() / mode / "failures"
        if not folder.exists():
            return None
        entries = tuple(_checked(folder).iterdir())
        if len(entries) > 1000:
            raise ValueError("failure count limit")
        receipts = []
        for path in entries:
            body = _bounded_read(_checked(path), 4096)
            receipt = FailureReceipt.model_validate_json(body)
            if (
                path.name != receipt.attempt_id + ".json"
                or receipt.mode != mode
                or canonical_json(receipt) != body
            ):
                raise ValueError("invalid failure receipt")
            if receipt.dataset_class != "fixture" or self.allow_fixture:
                receipts.append(receipt)
        return max(receipts, key=lambda item: (item.created_at, item.attempt_id), default=None)

    def get_scoped(self, run_id: str, scopes: tuple[str, ...]) -> PublicRun | None:
        root = self._root()
        for scope in scopes:
            folder = root / scope
            if not folder.exists():
                continue
            _checked(folder)
            candidate = folder / run_id
            if not candidate.exists():
                continue
            raw = _bounded_read(_checked(candidate / "public-manifest.json"), 256 * 1024 * 1024)
            manifest = _manifest(raw)
            if manifest.dataset_class == "fixture" and not self.allow_fixture:
                return None
            return verify_catalog_run(candidate, allow_fixture=self.allow_fixture)
        return None
