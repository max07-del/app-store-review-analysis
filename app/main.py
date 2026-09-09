import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.analyses import router as analyses_router
from app.api.reviews import router as reviews_router
from app.config import LLMSettings
from app.exceptions import ReviewCollectorError
from app.repository import AnalysisRepository
from app.services.llm_insights import LLMInsightGenerator


def create_app() -> FastAPI:
    api = FastAPI(
        title="App Store Review Analysis API",
        description="Collect and analyze a random sample of Apple App Store reviews.",
        version="0.1.0",
    )
    api.state.analysis_repository = AnalysisRepository(
        os.getenv("APP_DATABASE_PATH", "data/app_store_reviews.db")
    )
    api.state.llm_insight_generator = LLMInsightGenerator(LLMSettings.from_env())

    @api.exception_handler(ReviewCollectorError)
    async def review_collector_exception_handler(
        request: Request,
        exc: ReviewCollectorError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @api.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request
        first_error = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(part) for part in first_error.get("loc", [])[1:])
        message = str(first_error.get("msg", "Invalid request"))
        if location:
            message = f"{location}: {message}"
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "message": message}},
        )

    @api.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "llm_insights": (
                "enabled" if api.state.llm_insight_generator.is_available else "disabled"
            ),
        }

    api.include_router(reviews_router)
    api.include_router(analyses_router)
    return api


app = create_app()
