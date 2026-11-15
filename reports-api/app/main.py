from __future__ import annotations

from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.auth import current_user
from app.config import CORS_ORIGIN
from app.olap import OlapUnavailable, ReportResponse, build_report

app = FastAPI(title="BionicPRO Reports API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGIN],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/reports", response_model=ReportResponse)
def get_report(
    user: str = Depends(current_user),
    user_id: str | None = None,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> ReportResponse:
    # Идентичность берётся из токена. Чужой user_id не подменяется молча.
    if user_id is not None and user_id != user:
        raise HTTPException(status_code=403, detail="Доступ только к собственному отчёту")

    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from позже date_to")

    try:
        return build_report(user, date_from, date_to)
    except OlapUnavailable as exc:
        raise HTTPException(status_code=503, detail="OLAP временно недоступна") from exc
