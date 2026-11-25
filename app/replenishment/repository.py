"""Bounded read-only catalog index and same-byte verified snapshots."""

import re
from pathlib import Path

from app.analytics.schemas import parse_timestamp
from app.replenishment.artifacts import _checked, _decode, _json, _sha, verify_public_projection
from app.replenishment.schemas import ReplenishmentFailureReceipt


class UnsupportedSchema(ValueError):
    pass


def _bounded(path, limit):
    with _checked(path).open("rb") as stream:
        body = stream.read(limit + 1)
    if len(body) > limit:
        raise ValueError("index input too large")
    return body


class ReplenishmentRepository:
    def __init__(self, root: Path | None, *, allow_fixture=False):
        self.root = root
        self.allow_fixture = allow_fixture

    def _root(self):
        if self.root is None:
            return None
        root = _checked(self.root)
        if not root.is_dir():
            raise OSError("catalog unavailable")
        return root

    def _scope(self, mode):
        root = self._root()
        if root is None:
            return None
        folder = root / mode
        if not folder.exists():
            return None
        folder = _checked(folder)
        if not folder.is_dir():
            raise ValueError("invalid scope")
        return folder

    def index(self, mode):
        folder = self._scope(mode)
        if folder is None:
            return ()
        entries = tuple(folder.iterdir())
        if len(entries) > 101:
            raise ValueError("catalog limit")
        result = []
        for entry in entries:
            if entry.name == "failures":
                continue
            if re.fullmatch(r"rrv1-[0-9a-f]{64}", entry.name) is None:
                raise ValueError("invalid catalog entry")
            root = _checked(entry)
            try:
                body = _bounded(root / "public-manifest.json", 262144)
            except FileNotFoundError:
                raise ValueError("partial artifact") from None
            manifest = _decode(body)
            if manifest.get("schema_version") != "replenishment-public-run/1":
                raise UnsupportedSchema("unsupported schema")
            if manifest.get("mode") != mode or manifest.get("run_id") != entry.name:
                raise ValueError("scope mismatch")
            identity = {k: v for k, v in manifest.items() if k != "projection_sha256"}
            if manifest.get("projection_sha256") != _sha(_json(identity)):
                raise ValueError("manifest hash mismatch")
            if manifest.get("dataset_class") == "fixture" and not self.allow_fixture:
                continue
            if manifest.get("dataset_class") not in ("research", "fixture"):
                raise ValueError("invalid class")
            created = parse_timestamp(manifest.get("created_at"))
            result.append((created, entry.name, root))
        return tuple(sorted(result, reverse=True))

    def snapshot(self, path):
        try:
            snapshot = verify_public_projection(path, include_snapshot=True)
        except FileNotFoundError:
            raise ValueError("partial artifact") from None
        if snapshot["manifest"]["dataset_class"] == "fixture" and not self.allow_fixture:
            raise ValueError("fixture not allowed")
        return snapshot

    def scoped(self, run_id, scopes):
        for mode in scopes:
            folder = self._scope(mode)
            if folder is None:
                continue
            candidate = folder / run_id
            if not candidate.exists():
                continue
            try:
                raw = _decode(_bounded(candidate / "public-manifest.json", 262144))
            except FileNotFoundError:
                raise ValueError("partial artifact") from None
            if raw.get("schema_version") != "replenishment-public-run/1":
                raise UnsupportedSchema("unsupported schema")
            if raw.get("dataset_class") == "fixture" and not self.allow_fixture:
                return None
            return self.snapshot(candidate)
        return None

    def latest_failure(self, mode):
        folder = self._scope(mode)
        if folder is None or not (folder / "failures").exists():
            return None
        failures = _checked(folder / "failures")
        paths = tuple(failures.iterdir())
        if len(paths) > 100:
            raise ValueError("failure limit")
        records = []
        for path in paths:
            body = _bounded(path, 4096)
            record = ReplenishmentFailureReceipt.model_validate_json(body)
            if (
                record.mode != mode
                or path.name != record.attempt_id + ".json"
                or _json(record) != body
            ):
                raise ValueError("invalid failure receipt")
            if record.dataset_class == "fixture" and not self.allow_fixture:
                continue
            records.append(record)
        return max(records, key=lambda r: (r.created_at, r.attempt_id), default=None)
