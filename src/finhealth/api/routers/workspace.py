"""Organization-scoped saved financial workspace with RBAC enforcement."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finhealth.api.dependencies import get_active_model_bundle, get_db
from finhealth.api.routers.models import _resolve_bundle
from finhealth.api.schemas.accounts import AnalysisInput, ScreenerInput
from finhealth.api.security import OrgContext, aware_time, request_limit, require_org_role
from finhealth.api.services import FinancialAnalysisService
from finhealth.db.account_models import SavedAnalysis, SavedScreener, WatchlistItem
from finhealth.db.models import Company
from finhealth.ml.registry import ModelArtifactBundle

router = APIRouter(prefix="/me", tags=["personal workspace"])
Db = Annotated[Session, Depends(get_db)]
OrgReader = Annotated[OrgContext, Depends(require_org_role("viewer"))]
OrgWriter = Annotated[OrgContext, Depends(require_org_role("analyst"))]
WorkspaceModel = type[WatchlistItem] | type[SavedScreener] | type[SavedAnalysis]


def limit_saved(db: Session, model: WorkspaceModel, organization_id: int) -> None:
    """Bound per-organization saved collections to prevent unbounded workspace storage."""
    count = (
        db.scalar(
            select(func.count())
            .select_from(model)
            .where(model.organization_id == organization_id)
        )
        or 0
    )
    if count >= 200:
        raise HTTPException(409, "Đã đạt giới hạn 200 mục. Hãy xóa mục không cần thiết.")


@router.get("/watchlist")
def watchlist(ctx: OrgReader, db: Db) -> list[dict[str, object]]:
    """List only the active organization's followed companies."""
    rows = db.execute(
        select(WatchlistItem, Company)
        .join(
            Company,
            Company.id == WatchlistItem.company_id,
        )
        .where(WatchlistItem.organization_id == ctx.organization.id)
        .order_by(WatchlistItem.id.desc())
    ).all()
    return [
        {"id": item.id, "cik": company.cik, "ticker": company.ticker, "name": company.name}
        for item, company in rows
    ]


@router.post("/watchlist/{cik}", status_code=201)
def follow(cik: str, ctx: OrgWriter, db: Db) -> dict[str, object]:
    """Follow an existing company idempotently within the active organization workspace."""
    company = db.scalar(select(Company).where(Company.cik == cik))
    if company is None:
        raise HTTPException(404, "Không tìm thấy doanh nghiệp")
    existing = db.scalar(
        select(WatchlistItem).where(
            WatchlistItem.organization_id == ctx.organization.id,
            WatchlistItem.company_id == company.id,
        )
    )
    if existing:
        return {"id": existing.id}
    limit_saved(db, WatchlistItem, ctx.organization.id)
    item = WatchlistItem(
        user_id=ctx.user.id,
        organization_id=ctx.organization.id,
        company_id=company.id,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_item = db.scalar(
            select(WatchlistItem).where(
                WatchlistItem.organization_id == ctx.organization.id,
                WatchlistItem.company_id == company.id,
            )
        )
        if existing_item is None:
            raise HTTPException(409, "Không thể cập nhật danh sách theo dõi") from None
        item = existing_item
    return {"id": item.id}


@router.get("/screeners")
def screeners(ctx: OrgReader, db: Db) -> list[dict[str, Any]]:
    """Return typed screening snapshots for the active organization."""
    rows = db.scalars(
        select(SavedScreener)
        .where(SavedScreener.organization_id == ctx.organization.id)
        .order_by(SavedScreener.id.desc())
    ).all()
    return [{"id": row.id, "name": row.name, "filters": row.filters} for row in rows]


@router.post("/screeners", status_code=201)
def save_screener(payload: ScreenerInput, ctx: OrgWriter, db: Db) -> dict[str, int]:
    """Persist a validated filter configuration under the active organization."""
    limit_saved(db, SavedScreener, ctx.organization.id)
    item = SavedScreener(
        user_id=ctx.user.id,
        organization_id=ctx.organization.id,
        name=payload.name,
        filters=payload.filters.model_dump(mode="json", exclude_none=True),
    )
    db.add(item)
    db.commit()
    return {"id": item.id}


@router.get("/analyses")
def analyses(ctx: OrgReader, db: Db) -> list[dict[str, object]]:
    """List private prediction summaries strictly within the active organization."""
    rows = db.scalars(
        select(SavedAnalysis)
        .where(SavedAnalysis.organization_id == ctx.organization.id)
        .order_by(SavedAnalysis.id.desc())
    ).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "model_version": row.model_version,
            "created_at": aware_time(row.created_at),
        }
        for row in rows
    ]


@router.post("/analyses", status_code=201)
def save_analysis(
    payload: AnalysisInput,
    request: Request,
    ctx: OrgWriter,
    db: Db,
    active: Annotated[ModelArtifactBundle | None, Depends(get_active_model_bundle)],
) -> dict[str, int]:
    """Save only after explicit consent and recompute using a trusted server model."""
    request_limit(db, request, "saved-prediction", 20)
    limit_saved(db, SavedAnalysis, ctx.organization.id)
    bundle = _resolve_bundle(payload.inputs.model_version, active, request.app.state.settings)
    result = FinancialAnalysisService().predict_manual_statement(payload.inputs, bundle)
    item = SavedAnalysis(
        user_id=ctx.user.id,
        organization_id=ctx.organization.id,
        name=payload.name,
        model_version=bundle.model_version,
        inputs=payload.inputs.model_dump(mode="json"),
        outputs=result.model_dump(mode="json"),
    )
    db.add(item)
    db.commit()
    return {"id": item.id}


@router.get("/analyses/{item_id}")
def read_analysis(item_id: int, ctx: OrgReader, db: Db) -> dict[str, Any]:
    """Constrain private record lookup by active organization to prevent IDOR leaks."""
    item = db.scalar(
        select(SavedAnalysis).where(
            SavedAnalysis.id == item_id,
            SavedAnalysis.organization_id == ctx.organization.id,
        )
    )
    if item is None:
        raise HTTPException(404, "Không tìm thấy kết quả đã lưu")
    return {
        "id": item.id,
        "name": item.name,
        "inputs": item.inputs,
        "outputs": item.outputs,
        "model_version": item.model_version,
        "created_at": aware_time(item.created_at),
    }


@router.delete("/{collection}/{item_id}", status_code=204)
def delete_saved(collection: str, item_id: int, ctx: OrgWriter, db: Db) -> None:
    """Delete only from a fixed collection and only within the active organization."""
    collections: dict[str, WorkspaceModel] = {
        "watchlist": WatchlistItem,
        "screeners": SavedScreener,
        "analyses": SavedAnalysis,
    }
    model = collections.get(collection)
    if model is None:
        raise HTTPException(404, "Không tìm thấy bộ sưu tập")
    item = db.scalar(
        select(model).where(
            model.id == item_id,
            model.organization_id == ctx.organization.id,
        )
    )
    if item is None:
        raise HTTPException(404, "Không tìm thấy mục đã lưu")
    db.delete(item)
    db.commit()
