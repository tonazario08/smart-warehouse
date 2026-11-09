"""Prepare and verify offline road artifacts without network access."""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from app.gis.catalog import (
    SNAPSHOT_ID,
    SnapshotError,
    _open_artifact,
    _read_manifest,
    canonical_json,
    check_age,
    checked_path,
    manifest_id,
    verify_snapshot,
    write_graph,
)
from app.gis.osm_import import import_osm
from app.gis.schemas import (
    PUBLIC_ATTRIBUTION,
    PUBLIC_BOUNDS,
    PUBLIC_LICENSE,
    PUBLIC_SOURCE,
    SOURCE_LIMIT,
    Manifest,
    Snapshot,
    coherent_source_date,
)

SHA256 = re.compile(r"[0-9a-f]{64}")


def _copy_and_hash_source(path: Path, private_copy: Path) -> str:
    """Hash exactly the bounded bytes subsequently parsed from private staging."""
    hasher = hashlib.sha256()
    with _open_artifact(path) as source, private_copy.open("xb") as output:
        if os.fstat(source.fileno()).st_size > SOURCE_LIMIT:
            raise SnapshotError("PBF source size limit exceeded")
        size = 0
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            if size > SOURCE_LIMIT:
                raise SnapshotError("PBF source size limit exceeded")
            output.write(chunk)
            hasher.update(chunk)
    return hasher.hexdigest()


def _existing_snapshot(root: Path, manifest: Manifest, now: datetime) -> Snapshot | None:
    matching = None
    with os.scandir(root) as entries:
        for entry in entries:
            if not SNAPSHOT_ID.fullmatch(entry.name) or not entry.is_dir(follow_symlinks=False):
                continue
            try:
                existing = _read_manifest(Path(entry.path) / "manifest.json", entry.name)
            except (SnapshotError, OSError):
                continue
            if existing == manifest.model_copy(update={"prepared_at": existing.prepared_at}):
                candidate = (existing.prepared_at, entry.name)
                if matching is None or candidate < matching:
                    matching = candidate
    return None if matching is None else verify_snapshot(root, matching[1], now)


def prepare_snapshot(
    path: Path, source_url: str, source_sha256: str, root: Path, now: datetime
) -> Snapshot:
    if not PUBLIC_SOURCE.fullmatch(source_url) or not SHA256.fullmatch(source_sha256):
        raise SnapshotError("invalid PBF source provenance")
    workspace = Path(__file__).resolve().parents[2]
    system_temp = Path(tempfile.gettempdir()).resolve()
    for external in (path, root, system_temp):
        if external.is_relative_to(workspace):
            raise SnapshotError("road artifacts must stay outside the repository")
    checked_path(root, directory=True, create=True)

    def check_header(timestamp: datetime) -> None:
        check_age(timestamp, now)
        if not coherent_source_date(source_url, timestamp):
            raise SnapshotError("PBF replication date conflicts with the source URL")

    with tempfile.TemporaryDirectory(prefix="gis-pbf-", dir=system_temp) as temporary:
        private_copy = Path(temporary) / "source.osm.pbf"
        if _copy_and_hash_source(path, private_copy) != source_sha256:
            raise SnapshotError("PBF source checksum mismatch")
        imported = import_osm(private_copy, check_header=check_header)

    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".gis-stage-", dir=root) as temporary:
        staging = Path(temporary)
        graph_path = staging / "graph.json"
        with graph_path.open("xb") as stream:
            graph_hash = write_graph(stream, imported.graph)
        manifest = Manifest(
            dataset_class="public_osm",
            snapshot_at=imported.snapshot_at,
            prepared_at=now.astimezone(UTC),
            source_url=source_url,
            source_sha256=source_sha256,
            graph_sha256=graph_hash,
            bounds=PUBLIC_BOUNDS,
            license=PUBLIC_LICENSE,
            attribution=PUBLIC_ATTRIBUTION,
            stats=imported.stats,
        )
        existing = _existing_snapshot(root, manifest, now)
        if existing is not None:
            return existing

        manifest_bytes = canonical_json(manifest.model_dump(mode="json"))
        snapshot_id = manifest_id(manifest_bytes)
        candidate = staging / snapshot_id
        candidate.mkdir()
        graph_path.rename(candidate / "graph.json")
        (candidate / "manifest.json").write_bytes(manifest_bytes)
        snapshot = verify_snapshot(staging, snapshot_id, now)
        target = root / snapshot_id
        if target.exists() or target.is_symlink():
            return verify_snapshot(root, snapshot_id, now)
        try:
            candidate.rename(target)
        except OSError:
            if not target.exists():
                raise
            return verify_snapshot(root, snapshot_id, now)
        return snapshot


def main(argv: list[str] | None = None, *, now: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--input", required=True, type=Path)
    prepare.add_argument("--source-url", required=True)
    prepare.add_argument("--source-sha256", required=True)
    prepare.add_argument("--output-root", required=True, type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--catalog-root", required=True, type=Path)
    verify.add_argument("--snapshot-id", required=True)
    args = parser.parse_args(argv)
    at = datetime.now(UTC) if now is None else now
    try:
        if args.command == "prepare":
            snapshot = prepare_snapshot(
                args.input, args.source_url, args.source_sha256, args.output_root, at
            )
        else:
            snapshot = verify_snapshot(args.catalog_root, args.snapshot_id, at)
    except SnapshotError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 1
    except OSError:
        print("invalid: artifact I/O failed", file=sys.stderr)
        return 1
    print(json.dumps({
        "snapshot_id": snapshot.snapshot_id,
        **snapshot.manifest.model_dump(mode="json"),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
