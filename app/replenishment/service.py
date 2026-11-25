"""Role-scoped replenishment views over verified immutable snapshots."""

from app.auth.dependencies import PERMISSION_ROLES, Permission
from app.core.errors import DomainError
from app.models import Product, Warehouse
from app.replenishment.repository import UnsupportedSchema


class ReplenishmentService:
    def __init__(self, repository, session):
        self.repository = repository
        self.session = session

    @staticmethod
    def scopes(actor):
        if actor.role not in PERMISSION_ROLES[Permission.REPLENISHMENT_READ]:
            raise DomainError(403, "REPLENISHMENT_FORBIDDEN", "Permission denied.")
        if actor.role in PERMISSION_ROLES[Permission.REPLENISHMENT_RESEARCH_READ]:
            return ("operational", "research")
        return ("operational",)

    @staticmethod
    def _error(error):
        if isinstance(error, OSError):
            return DomainError(503, "REPLENISHMENT_CATALOG_UNAVAILABLE", "Catalog unavailable.")
        if isinstance(error, UnsupportedSchema):
            return DomainError(409, "REPLENISHMENT_SCHEMA_UNSUPPORTED", "Unsupported schema.")
        return DomainError(409, "REPLENISHMENT_ARTIFACT_INVALID", "Artifact invalid.")

    def _view(self, snapshot, *, detail):
        manifest = snapshot["manifest"]
        binding = manifest["binding"]
        entity = None
        if binding is not None:
            product = self.session.get(Product, binding["product_id"])
            warehouse = self.session.get(Warehouse, binding["warehouse_id"])
            if product is None or warehouse is None or product.unit != binding["unit"]:
                raise DomainError(409, "REPLENISHMENT_BINDING_UNAVAILABLE", "Binding unavailable.")
            entity = {
                "product_id": product.id,
                "product_name": product.name,
                "sku": product.sku,
                "warehouse_id": warehouse.id,
                "warehouse_name": warehouse.name,
                "warehouse_code": warehouse.code,
            }
        summaries = None
        calibration = None
        if detail:
            calibration = snapshot["calibration"]
            summaries = []
            for entry in snapshot["summaries"]:
                case = entry["case"]
                key = (case["algorithm"], case["horizon"], case["service"], case["policy"])
                scored = [d.reorder_point for d in snapshot["days"][key] if not d.warmup]
                summaries.append({**entry, "rop_min": min(scored), "rop_max": max(scored)})
        return {
            "manifest": manifest,
            "calibration": calibration,
            "summaries": summaries,
            "applicability": manifest["applicability"],
            "fixture_label": "Dữ liệu kiểm thử" if manifest["dataset_class"] == "fixture" else None,
            "stale": None,
            "reason_codes": [],
            "entity": entity,
        }

    def list_runs(self, actor, mode, page, page_size):
        if mode not in self.scopes(actor):
            raise DomainError(403, "REPLENISHMENT_FORBIDDEN", "Permission denied.")
        try:
            entries = self.repository.index(mode)
            start = (page - 1) * page_size
            selected = [
                self.repository.snapshot(entry[2]) for entry in entries[start : start + page_size]
            ]
            views = [self._view(snapshot, detail=False) for snapshot in selected]
        except DomainError:
            raise
        except Exception as error:
            raise self._error(error) from None
        return {"items": views, "total": len(entries), "page": page, "page_size": page_size}

    def status(self, actor, mode):
        if mode not in self.scopes(actor):
            raise DomainError(403, "REPLENISHMENT_FORBIDDEN", "Permission denied.")
        try:
            entries = self.repository.index(mode)
            failure = self.repository.latest_failure(mode)
            latest = self.repository.snapshot(entries[0][2]) if entries else None
            view = self._view(latest, detail=False) if latest else None
        except DomainError as error:
            if error.code == "REPLENISHMENT_BINDING_UNAVAILABLE":
                return {
                    "state": "unavailable",
                    "reason_code": "BINDING_UNAVAILABLE",
                    "latest": None,
                }
            raise
        except Exception as error:
            raise self._error(error) from None
        if failure and (not entries or failure.created_at > entries[0][0]):
            return {"state": "failed", "reason_code": failure.reason_code, "latest": view}
        if view is None:
            return {
                "state": "unavailable",
                "reason_code": "NO_REVIEWED_POLICY_INPUTS" if mode == "operational" else "NO_RUNS",
                "latest": None,
            }
        return {"state": "ready", "reason_code": None, "latest": view}

    def get(self, actor, run_id):
        scopes = self.scopes(actor)
        try:
            snapshot = self.repository.scoped(run_id, scopes)
        except Exception as error:
            raise self._error(error) from None
        if snapshot is None:
            raise DomainError(404, "REPLENISHMENT_NOT_FOUND", "Run not found.")
        return snapshot
