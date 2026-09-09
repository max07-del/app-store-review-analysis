import csv
import io
import json
from typing import Literal

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, Response

from app.exceptions import AnalysisNotFoundError
from app.repository import AnalysisRepository
from app.schemas.reviews import (
    AnalysisResponse,
    AnalyzedReview,
    CollectReviewsRequest,
)
from app.services.apple_client import AppleClient
from app.services.report import render_analysis_report
from app.services.review_collector import ReviewCollector
from app.services.text_analysis import ReviewAnalyzer

router = APIRouter(prefix="/api/v1/analyses", tags=["analyses"])


def _repository(request: Request) -> AnalysisRepository:
    return request.app.state.analysis_repository


@router.post("", response_model=AnalysisResponse, status_code=201)
async def create_analysis(
    payload: CollectReviewsRequest,
    request: Request,
) -> AnalysisResponse:
    timeout = httpx.Timeout(15.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as http_client:
        collection = await ReviewCollector(AppleClient(http_client)).collect(payload)

    analysis, reviews = ReviewAnalyzer().analyze(collection)
    _repository(request).save(analysis, reviews)
    return analysis


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(analysis_id: str, request: Request) -> AnalysisResponse:
    analysis = _repository(request).get_analysis(analysis_id)
    if analysis is None:
        raise AnalysisNotFoundError(f"Analysis {analysis_id} was not found")
    return analysis


@router.get("/{analysis_id}/reviews", response_model=list[AnalyzedReview])
async def get_analysis_reviews(
    analysis_id: str,
    request: Request,
) -> list[AnalyzedReview]:
    reviews = _repository(request).get_reviews(analysis_id)
    if reviews is None:
        raise AnalysisNotFoundError(f"Analysis {analysis_id} was not found")
    return reviews


@router.get("/{analysis_id}/reviews/download")
async def download_analysis_reviews(
    analysis_id: str,
    request: Request,
    format: Literal["json", "csv"] = Query(default="json"),
) -> Response:
    reviews = _repository(request).get_reviews(analysis_id)
    if reviews is None:
        raise AnalysisNotFoundError(f"Analysis {analysis_id} was not found")

    filename = f"reviews-{analysis_id}.{format}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    rows = [review.model_dump() for review in reviews]

    if format == "json":
        return Response(
            json.dumps(rows, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers=headers,
        )

    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return Response(output.getvalue(), media_type="text/csv", headers=headers)


@router.get("/{analysis_id}/report", response_class=HTMLResponse)
async def get_analysis_report(analysis_id: str, request: Request) -> HTMLResponse:
    analysis = _repository(request).get_analysis(analysis_id)
    if analysis is None:
        raise AnalysisNotFoundError(f"Analysis {analysis_id} was not found")
    return HTMLResponse(render_analysis_report(analysis))
