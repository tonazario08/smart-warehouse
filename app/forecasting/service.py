"""Scope-aware read service for verified public forecast runs."""

from datetime import UTC, datetime, timedelta

from app.analytics.schemas import load_timezone
from app.auth.dependencies import PERMISSION_ROLES, Permission
from app.core.errors import DomainError
from app.forecasting.repository import ForecastRepository, UnsupportedSchema
from app.models import Product, Warehouse


class ForecastService:
    def __init__(self, repository: ForecastRepository, session, clock=None):
        self.repository = repository
        self.session = session
        self.clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def scopes(actor):
        if actor.role not in PERMISSION_ROLES[Permission.FORECAST_READ]:
            raise DomainError(403, "FORECAST_FORBIDDEN", "Permission denied.")
        if actor.role in PERMISSION_ROLES[Permission.FORECAST_RESEARCH_READ]:
            return ("operational", "research")
        return ("operational",)

    def _binding(self, run):
        binding = run.binding
        if binding is None:
            return None
        product = self.session.get(Product, binding.product_id)
        warehouse = self.session.get(Warehouse, binding.warehouse_id)
        if product is None or warehouse is None or product.unit != binding.unit:
            raise DomainError(409, "FORECAST_ARTIFACT_INVALID", "Forecast binding is unavailable.")
        return {
            "product_id": product.id,
            "product_name": product.name,
            "sku": product.sku,
            "warehouse_id": warehouse.id,
            "warehouse_name": warehouse.name,
            "warehouse_code": warehouse.code,
        }

    def _view(self, run):
        manifest = run.manifest
        display = self._binding(run)
        stale = None
        applicability = "retrospective" if manifest.mode == "research" else "operational"
        if manifest.mode == "operational" and manifest.kind == "forecast":
            today = self.clock().astimezone(load_timezone(manifest.business_timezone)).date()
            stale = manifest.origin_end != today - timedelta(days=1) or not any(
                row.target_date == today for row in run.rows
            )
        return {
            "manifest": manifest.model_dump(mode="json"),
            "metrics": run.metrics,
            "binding": run.binding.model_dump(mode="json") if run.binding else None,
            "entity": display,
            "applicability": applicability,
            "stale": stale,
            "fixture_label": "Dữ liệu kiểm thử" if manifest.dataset_class == "fixture" else None,
        }

    def list_runs(self, actor, mode, page, page_size):
        if mode not in self.scopes(actor):
            raise DomainError(403, "FORECAST_FORBIDDEN", "Permission denied.")
        try:
            runs = self.repository.list_scope(mode)
        except OSError:
            raise DomainError(
                503, "FORECAST_CATALOG_UNAVAILABLE", "Forecast catalog unavailable."
            ) from None
        except UnsupportedSchema:
            raise DomainError(
                409, "FORECAST_SCHEMA_UNSUPPORTED", "Forecast schema unsupported."
            ) from None
        except Exception:
            raise DomainError(
                409, "FORECAST_ARTIFACT_INVALID", "Forecast artifact invalid."
            ) from None
        start = (page - 1) * page_size
        return {
            "items": [self._view(run) for run in runs[start : start + page_size]],
            "total": len(runs),
            "page": page,
            "page_size": page_size,
        }

    def status(self, actor, mode):
        if mode not in self.scopes(actor):
            raise DomainError(403, "FORECAST_FORBIDDEN", "Permission denied.")
        try:
            runs = self.repository.list_scope(mode)
            failure = self.repository.latest_failure(mode)
        except OSError:
            return {"state": "unavailable", "reason_code": "CATALOG_UNAVAILABLE", "latest": None}
        except UnsupportedSchema:
            raise DomainError(
                409, "FORECAST_SCHEMA_UNSUPPORTED", "Forecast schema unsupported."
            ) from None
        except Exception:
            raise DomainError(
                409, "FORECAST_ARTIFACT_INVALID", "Forecast artifact invalid."
            ) from None
        if not runs:
            if failure is not None:
                return {
                    "state": "failed",
                    "reason_code": failure.error_code,
                    "latest": None,
                    "latest_failure_code": failure.error_code,
                }
            return {
                "state": "unavailable",
                "reason_code": "NO_ADMITTED_OPERATIONAL_SERIES"
                if mode == "operational"
                else "NO_RUNS",
                "latest": None,
            }
        return {
            "state": "ready",
            "reason_code": None,
            "latest": self._view(runs[0]),
            "latest_failure_code": failure.error_code if failure else None,
        }

    def get_run(self, actor, run_id):
        scopes = self.scopes(actor)
        try:
            run = self.repository.get_scoped(run_id, scopes)
        except OSError:
            raise DomainError(
                503, "FORECAST_CATALOG_UNAVAILABLE", "Forecast catalog unavailable."
            ) from None
        except UnsupportedSchema:
            raise DomainError(
                409, "FORECAST_SCHEMA_UNSUPPORTED", "Forecast schema unsupported."
            ) from None
        except Exception:
            raise DomainError(
                409, "FORECAST_ARTIFACT_INVALID", "Forecast artifact invalid."
            ) from None
        if run is None:
            raise DomainError(404, "FORECAST_NOT_FOUND", "Forecast not found.")
        return run
