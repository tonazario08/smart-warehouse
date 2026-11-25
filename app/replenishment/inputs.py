"""Check authorized input paths and complete temporal windows."""

import stat
from datetime import timedelta
from pathlib import Path


def _checked(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or str(path).startswith(("\\\\", "//")):
        raise ValueError("unsafe input path")
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("unsafe input path")
    return path.resolve(strict=True)


def validate_authorization_paths(authorization):
    import getpass
    import os
    import sys
    import tempfile

    workspace = Path(__file__).resolve().parents[2]
    worktrees = workspace.parent.parent
    if authorization.dataset_class == "research":
        expected_roots = (
            worktrees
            / "m5-demand-data"
            / "smart-warehouse"
            / "artifacts"
            / "demand-data"
            / "bundles"
            / "reported-sales-v1",
            worktrees
            / "m6-demand-forecasting"
            / "smart-warehouse"
            / "artifacts"
            / "forecasting"
            / "catalog"
            / "research",
        )
    else:
        expected_roots = (
            workspace / "artifacts" / "demand-data",
            workspace / "artifacts" / "forecasting",
        )
    pytest_root = Path(tempfile.gettempdir()) / f"pytest-of-{getpass.getuser()}"
    pairs = (
        (authorization.approved_bundle_root, authorization.bundle_path),
        (authorization.approved_forecast_root, authorization.forecast_dir),
    )
    for (root, child), expected in zip(pairs, expected_roots, strict=True):
        try:
            checked_root, checked_child = _checked(root), _checked(child)
        except OSError as exc:
            raise ValueError("input unavailable") from exc
        if (
            not checked_root.is_dir()
            or not checked_child.is_dir()
            or (checked_child == checked_root or not checked_child.is_relative_to(checked_root))
        ):
            raise ValueError("input outside authorized root")
        if authorization.dataset_class == "research":
            if checked_root != expected:
                raise ValueError("research root not admitted")
        elif not (
            checked_root == expected
            or checked_root.is_relative_to(expected)
            or (
                checked_root.is_relative_to(pytest_root)
                and "pytest" in sys.modules
                and bool(os.environ.get("PYTEST_CURRENT_TEST"))
            )
        ):
            raise ValueError("fixture root not owned")
    if authorization.dataset_class == "research":
        expected_hashes = {
            "manifest.json": "17b7dd594458912c8e1d02e0535646faa56ed0523bcc595948fa07d3a6b615d1",
            "observations.jsonl": (
                "6a56332fd7e21719122c7978e4bcae0453f39dae6d08d66c3627e19ad6b3b386"
            ),
            "quality.json": "b2f5c76ec497b86f55daa7f68fd7e5ea748185bd7164e95e8ccb049a4ee59c0e",
            "records.jsonl": "05c04fb8140d394d5bd756bd21f3e2c6073656ac8c4ca492742a06ea22969c8c",
        }
        if (
            authorization.bundle_path.name
            != "ddv2-62da0915fdcde6d212f7a5a5c903123a20baed119560be0be17d902eec84b3e7"
            or authorization.forecast_run_id
            != "frv1-398a6c1c260e5277a15b647d3f383ef2bc5458978386dd05ccf88eee527c7b82"
            or authorization.public_manifest_sha256
            != "1e31a3ff9fa86a41e6ff96e51c29e70b6b472215f3b4d46284d02390251124f7"
            or authorization.source_manifest_sha256
            != "8898733f8924dc5ff947f3d3225b832021a61bf01dc84bca6a5bd271d95d63e1"
            or dict(authorization.bundle_hashes) != expected_hashes
        ):
            raise ValueError("research identity not admitted")


def classify_window(rows, start, end):
    if not rows:
        raise ValueError("empty window")
    first = rows[0]
    if first.horizon not in (1, 7) or len(rows) != first.horizon:
        raise ValueError("incomplete window")
    for lead, row in enumerate(rows, 1):
        if (
            (row.series_key, row.origin, row.horizon, row.algorithm, row.unit)
            != (first.series_key, first.origin, first.horizon, first.algorithm, first.unit)
            or row.lead != lead
            or row.target_date != first.origin + timedelta(days=lead)
            or row.actual is None
        ):
            raise ValueError("invalid window")
    return start <= rows[0].target_date and rows[-1].target_date < end


def select_windows(rows, start, end):
    """Group same-origin lead rows without compressing dates or filling labels."""
    groups = {}
    for row in rows:
        key = (row.series_key, row.algorithm, row.horizon, row.origin)
        groups.setdefault(key, []).append(row)
    selected = []
    for key in sorted(groups):
        group = tuple(sorted(groups[key], key=lambda row: row.lead))
        if classify_window(group, start, end):
            selected.append(group)
    return tuple(selected)


def validate_forecast_coverage(rows, start, end):
    """Distinguish a requested range beyond the forecast from internal gaps."""
    count = (end - start).days - 6
    if count <= 0:
        raise ValueError("NO_EVALUATION_WINDOWS")
    required = {start + timedelta(days=i - 1) for i in range(count)}
    for algorithm in ("persistence", "seasonal_naive", "xgboost"):
        for horizon in (1, 7):
            origins = {
                row.origin for row in rows if row.algorithm == algorithm and row.horizon == horizon
            }
            if not origins or min(required) < min(origins) or max(required) > max(origins):
                raise ValueError("FORECAST_STALE")
            if not required <= origins:
                raise ValueError("CALENDAR_UNAVAILABLE")


def load_inputs(forecast_dir, bundle_dir, config, authorization):
    """Verify pinned source identity before admitting observations and forecast rows."""
    import hashlib

    from app.analytics.export import _verify, canonical_json
    from app.analytics.schemas import (
        DailyObservation,
        ReportedSalesObservation,
        business_day_bounds,
    )
    from app.forecasting.repository import verify_catalog_run
    from app.forecasting.schemas import Observation
    from app.replenishment.schemas import InputAuthorization, StudyConfig, StudyInputs

    authorization = InputAuthorization.model_validate_json(authorization.model_dump_json())
    config = StudyConfig.model_validate_json(config.model_dump_json())

    validate_authorization_paths(authorization)
    if (
        Path(bundle_dir) != authorization.bundle_path
        or Path(forecast_dir) != authorization.forecast_dir
    ):
        raise ValueError("input path mismatch")

    def bounded(path):
        checked = _checked(path)
        with checked.open("rb") as stream:
            content = stream.read(67108865)
        if len(content) > 67108864:
            raise ValueError("input too large")
        return content

    def digest(path):
        return hashlib.sha256(bounded(path)).hexdigest()

    if {
        name: digest(authorization.bundle_path / name) for name in authorization.bundle_hashes
    } != dict(authorization.bundle_hashes):
        raise ValueError("bundle hash mismatch")
    if (
        digest(authorization.forecast_dir / "public-manifest.json")
        != authorization.public_manifest_sha256
    ):
        raise ValueError("forecast hash mismatch")
    manifest = _verify(authorization.bundle_path)
    public = verify_catalog_run(
        authorization.forecast_dir, allow_fixture=authorization.allow_fixture
    )
    p = public.manifest
    if (
        p.mode,
        p.dataset_class,
        p.data_version,
        p.target,
        p.reporting_scope,
        p.unit,
        p.run_id,
        p.source_manifest_sha256,
    ) != (
        config.mode,
        config.dataset_class,
        config.data_version,
        config.target,
        config.reporting_scope,
        config.unit,
        config.forecast_run_id,
        config.source_manifest_sha256,
    ):
        raise ValueError("forecast configuration mismatch")
    if (p.mode, p.dataset_class, p.run_id, p.source_manifest_sha256) != (
        authorization.mode,
        authorization.dataset_class,
        authorization.forecast_run_id,
        authorization.source_manifest_sha256,
    ) or config.public_manifest_sha256 != authorization.public_manifest_sha256:
        raise ValueError("input authorization mismatch")
    if (manifest.data_version, manifest.admission.dataset_class, manifest.admission.target) != (
        p.data_version,
        p.dataset_class,
        p.target,
    ):
        raise ValueError("bundle identity mismatch")
    if (
        p.admission_cutoff != manifest.admission.cutoff
        or p.knowledge_bound != manifest.admission.source.available_at_upper_bound
    ):
        raise ValueError("bundle knowledge bound mismatch")
    if p.kind != "evaluation" or p.horizons != (1, 7):
        raise ValueError("evaluation horizons required")
    if p.mode == "research":
        from datetime import date

        if (
            config.calibration_start,
            config.calibration_end,
            config.evaluation_start,
            config.evaluation_end,
        ) != (date(2022, 1, 1), date(2022, 7, 1), date(2022, 7, 1), date(2023, 1, 1)):
            raise ValueError("research partitions differ from approved protocol")
        calibration = select_windows(public.rows, config.calibration_start, config.calibration_end)
        evaluation = select_windows(public.rows, config.evaluation_start, config.evaluation_end)
        for algorithm in ("persistence", "seasonal_naive", "xgboost"):
            for horizon, count in ((1, 94), (7, 76)):
                if (
                    sum(
                        group[0].algorithm == algorithm and group[0].horizon == horizon
                        for group in calibration
                    )
                    != count
                ):
                    raise ValueError("research calibration eligibility mismatch")
        expected_origins = {date(2022, 6, 30) + timedelta(days=i) for i in range(178)}
        for algorithm in ("persistence", "seasonal_naive", "xgboost"):
            for horizon in (1, 7):
                origins = {
                    group[0].origin
                    for group in evaluation
                    if group[0].algorithm == algorithm and group[0].horizon == horizon
                }
                if not expected_origins <= origins:
                    raise ValueError("research evaluation eligibility mismatch")
    if p.mode == "operational":
        binding = public.binding
        if binding is None or authorization.expected_fixture_binding != (
            binding.product_id,
            binding.warehouse_id,
            binding.unit,
        ):
            raise ValueError("fixture binding mismatch")
        if not any(
            (m.product_key, m.warehouse_key, m.unit)
            == (binding.product_key, binding.warehouse_key, binding.unit)
            for m in manifest.admission.mappings
        ):
            raise ValueError("mapping mismatch")
        product, location = binding.product_key, binding.warehouse_key
    else:
        mappings = {
            (m.product_key, m.reporting_entity_key, m.unit) for m in manifest.admission.mappings
        }
        if len(mappings) != 1:
            raise ValueError("single research series required")
        product, location, unit = next(iter(mappings))
        if unit != p.unit:
            raise ValueError("research unit mismatch")
    identity = [
        manifest.admission.source.namespace,
        product,
        location,
        p.unit,
        p.target,
        p.reporting_scope,
    ]
    series_key = "fsk1-" + hashlib.sha256(canonical_json(identity)).hexdigest()
    if any(row.series_key != series_key for row in public.rows):
        raise ValueError("forecast series mismatch")
    model = DailyObservation if p.mode == "operational" else ReportedSalesObservation
    observations = []
    body = bounded(authorization.bundle_path / "observations.jsonl")
    if hashlib.sha256(body).hexdigest() != authorization.bundle_hashes["observations.jsonl"]:
        raise ValueError("bundle changed during read")
    for line in body.splitlines():
        row = model.model_validate_json(line)
        if p.mode == "operational" and (row.product_key, row.warehouse_key, row.unit) != (
            binding.product_key,
            binding.warehouse_key,
            binding.unit,
        ):
            continue
        observations.append(
            Observation(
                day=row.business_date, value=row.target_quantity, available_at=row.available_at
            )
        )
    if not observations or any(
        a.day >= b.day for a, b in zip(observations, observations[1:], strict=False)
    ):
        raise ValueError("invalid source calendar")
    actuals = {row.day: row.value for row in observations}
    if any(
        row.target_date not in actuals or actuals[row.target_date] != row.actual
        for row in public.rows
    ):
        raise ValueError("forecast labels mismatch")
    if p.mode == "operational":
        by_day = {row.day: row for row in observations}
        for origin in {row.origin for row in public.rows}:
            cutoff = business_day_bounds(origin, p.business_timezone)[1]
            if (
                binding.available_at > cutoff
                or binding.approved_at > cutoff
                or p.training_information_cutoff > cutoff
            ):
                raise ValueError("binding or training knowledge unavailable at origin")
            for offset in range(28):
                observed = by_day.get(origin - timedelta(days=offset))
                if (
                    observed is None
                    or observed.value is None
                    or observed.available_at is None
                    or observed.available_at > cutoff
                ):
                    raise ValueError("history unavailable at origin")
        calibration_cutoff = business_day_bounds(
            config.calibration_end - timedelta(days=1), p.business_timezone
        )[1]
        for window in select_windows(public.rows, config.calibration_start, config.calibration_end):
            if any(
                by_day[row.target_date].available_at is None
                or by_day[row.target_date].available_at > calibration_cutoff
                for row in window
            ):
                raise ValueError("calibration labels unavailable at cutoff")
    return StudyInputs(forecast=public, observations=tuple(observations), config=config)
