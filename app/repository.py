import json
import sqlite3
from pathlib import Path

from app.schemas.reviews import AnalysisResponse, AnalyzedReview


class AnalysisRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def save(
        self,
        analysis: AnalysisResponse,
        reviews: list[AnalyzedReview],
    ) -> None:
        self._initialize()
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO analyses
                    (id, created_at, analysis_json, reviews_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    analysis.analysis_id,
                    analysis.created_at,
                    analysis.model_dump_json(),
                    json.dumps(
                        [review.model_dump() for review in reviews],
                        ensure_ascii=False,
                    ),
                ),
            )

    def get_analysis(self, analysis_id: str) -> AnalysisResponse | None:
        row = self._read_column(analysis_id, "analysis_json")
        return AnalysisResponse.model_validate_json(row) if row is not None else None

    def get_reviews(self, analysis_id: str) -> list[AnalyzedReview] | None:
        row = self._read_column(analysis_id, "reviews_json")
        if row is None:
            return None
        return [AnalyzedReview.model_validate(item) for item in json.loads(row)]

    def _read_column(self, analysis_id: str, column: str) -> str | None:
        if not self.database_path.exists():
            return None
        self._initialize()
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                f"SELECT {column} FROM analyses WHERE id = ?",  # noqa: S608
                (analysis_id,),
            ).fetchone()
        return row[0] if row else None

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    analysis_json TEXT NOT NULL,
                    reviews_json TEXT NOT NULL
                )
                """
            )
