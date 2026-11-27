"""Thin model evaluation and persisted-panel training routes."""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from finhealth.api.dependencies import get_active_model_bundle, get_db, require_write_access
from finhealth.api.schemas import (
    BatchPredictionRequestSchema,
    BatchPredictionResponseSchema,
    ManualPredictionResponseSchema,
    ManualStatementInputSchema,
    ModelEvaluationResponseSchema,
    ModelVersionSummarySchema,
    TrainModelRequest,
)
from finhealth.api.security import check_prediction_rate, request_limit, require_admin, require_user
from finhealth.api.services import FinancialAnalysisService
from finhealth.core.config import Settings, get_settings
from finhealth.core.exceptions import ModelPipelineError, SecResourceNotFoundError
from finhealth.db.account_models import AdminAuditLog, User
from finhealth.ml.registry import ModelArtifactBundle, load_bundle

router = APIRouter(tags=["models"])
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


@lru_cache(maxsize=8)
def _cached_bundle(resolved_dir: str, mtime_ns: int) -> ModelArtifactBundle:
    """Cache immutable read-only model bundles by resolved path and artifact timestamp."""
    _ = mtime_ns
    return load_bundle(Path(resolved_dir))


def _resolve_bundle(
    model_version: str | None,
    active_bundle: ModelArtifactBundle | None,
    settings: Settings,
) -> ModelArtifactBundle:
    """Return the active bundle or safely load a named version confined to model_path."""
    if model_version is None or (
        active_bundle is not None and model_version == active_bundle.model_version
    ):
        if active_bundle is None:
            raise SecResourceNotFoundError("No active model bundle is loaded")
        return active_bundle
    if not _VERSION_RE.fullmatch(model_version):
        raise ModelPipelineError(f"Invalid model version identifier: {model_version}")
    root = settings.model_path.resolve()
    target = (root / model_version).resolve()
    if target.parent != root or not (target / "models.joblib").is_file():
        raise SecResourceNotFoundError(f"Model bundle not found: {model_version}")
    if (target / ".unpublished").exists():
        raise SecResourceNotFoundError(f"Model bundle not found: {model_version}")
    return _cached_bundle(str(target), (target / "models.joblib").stat().st_mtime_ns)


@router.get("/models/versions", response_model=list[ModelVersionSummarySchema])
def list_model_versions(
    active_bundle: Annotated[ModelArtifactBundle | None, Depends(get_active_model_bundle)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ModelVersionSummarySchema]:
    """List published model artifact bundles available for evaluation and manual scoring."""
    root = settings.model_path
    if not root.exists():
        return []
    active_version = active_bundle.model_version if active_bundle is not None else None
    versions: list[ModelVersionSummarySchema] = []
    for candidate in sorted(root.iterdir()):
        if (
            not candidate.is_dir()
            or not _VERSION_RE.fullmatch(candidate.name)
            or (candidate / ".unpublished").exists()
            or not (candidate / "models.joblib").is_file()
            or not (candidate / "evaluation_report.json").is_file()
        ):
            continue
        meta_path = candidate / "metadata.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
        report = json.loads((candidate / "evaluation_report.json").read_text(encoding="utf-8"))
        version = str(meta.get("model_version") or candidate.name)
        provenance = report.get("data_provenance") or {}
        live_info = str(provenance.get("live_ingestion", "")).lower()
        dataset = (
            "kaggle"
            if "kaggle" in version.lower() or "kaggle" in live_info
            else "sec"
        )
        versions.append(
            ModelVersionSummarySchema(
                model_version=version,
                created_at=str(meta.get("created_at", "")),
                is_active=version == active_version,
                dataset=dataset,
                selected_model_name=report.get("selected_model_name"),
                imbalance_strategy=str(report.get("imbalance_strategy") or "class_weight"),
            )
        )
    versions.sort(
        key=lambda item: (not item.is_active, item.dataset != "kaggle", item.model_version)
    )
    return versions


@router.get("/models/evaluation", response_model=ModelEvaluationResponseSchema)
def model_evaluation(
    bundle: Annotated[ModelArtifactBundle | None, Depends(get_active_model_bundle)],
    settings: Annotated[Settings, Depends(get_settings)],
    model_version: Annotated[
        str | None,
        Query(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"),
    ] = None,
) -> ModelEvaluationResponseSchema:
    """Return the active or requested fitted model's actual stored benchmark report."""
    selected = _resolve_bundle(model_version, bundle, settings)
    return ModelEvaluationResponseSchema(
        model_version=selected.model_version,
        created_at=selected.created_at,
        evaluation_report=selected.evaluation_report,
    )


@router.post(
    "/models/train", response_model=ModelEvaluationResponseSchema,
    dependencies=[Depends(require_write_access)],
)
def train_model(
    options: TrainModelRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    actor: Annotated[User, Depends(require_admin)],
) -> ModelEvaluationResponseSchema:
    """Explicitly fit an annual model and calibrate on the eligible validation window."""
    request_limit(db, request, "train-model", 5)
    db.add(AdminAuditLog(actor_id=actor.id, action="model.train", target=options.model_version,
                         outcome="requested"))
    db.commit()
    result = FinancialAnalysisService().train_models(
        db, options, settings, request.app.state.model_registry
    )
    db.add(AdminAuditLog(actor_id=actor.id, action="model.publish", target=options.model_version))
    db.commit()
    return result


@router.post("/models/predict-manual", response_model=ManualPredictionResponseSchema,
             dependencies=[Depends(require_user), Depends(check_prediction_rate)])
def predict_manual(
    payload: ManualStatementInputSchema,
    bundle: Annotated[ModelArtifactBundle | None, Depends(get_active_model_bundle)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ManualPredictionResponseSchema:
    """Score user-entered financial statement figures with the active or selected model."""
    selected = _resolve_bundle(payload.model_version, bundle, settings)
    return FinancialAnalysisService().predict_manual_statement(payload, selected)


@router.post("/models/predict-batch", response_model=BatchPredictionResponseSchema,
             dependencies=[Depends(require_user), Depends(check_prediction_rate)])
def predict_batch(
    payload: BatchPredictionRequestSchema,
    bundle: Annotated[ModelArtifactBundle | None, Depends(get_active_model_bundle)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BatchPredictionResponseSchema:
    """Score a batch portfolio of corporate financial statements in a single request."""
    selected = _resolve_bundle(payload.model_version, bundle, settings)
    return FinancialAnalysisService().predict_batch_statements(payload, selected)
