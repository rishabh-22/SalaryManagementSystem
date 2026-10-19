from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, get_current_user
from app.schemas.insights import CountryInsights, Distribution, Outliers, Overview
from app.services import insights_service

router = APIRouter(prefix="/insights", tags=["insights"], dependencies=[Depends(get_current_user)])


@router.get("/overview", response_model=Overview)
def overview(db: DbSession):
    return insights_service.overview(db)


@router.get("/country/{code}", response_model=CountryInsights)
def country(code: str, db: DbSession):
    return insights_service.country_insights(db, code)


@router.get("/country/{code}/distribution", response_model=Distribution)
def distribution(code: str, db: DbSession, bins: int = Query(10, ge=1, le=50)):
    return insights_service.distribution(db, code, bins)


@router.get("/country/{code}/outliers", response_model=Outliers)
def outliers(
    code: str,
    db: DbSession,
    threshold: float = Query(0.3, gt=0, allow_inf_nan=False),
    limit: int = Query(50, ge=1, le=200),
):
    return insights_service.outliers(db, code, threshold, limit)
