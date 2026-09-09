class ReviewCollectorError(Exception):
    """Base exception for errors that can be safely exposed through the API."""

    code = "REVIEW_COLLECTOR_ERROR"
    status_code = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidAppIdentifierError(ReviewCollectorError):
    code = "INVALID_APP_IDENTIFIER"
    status_code = 422


class AppNotFoundError(ReviewCollectorError):
    code = "APP_NOT_FOUND"
    status_code = 404


class ReviewSourceUnavailableError(ReviewCollectorError):
    code = "REVIEW_SOURCE_UNAVAILABLE"
    status_code = 503


class InvalidSourceResponseError(ReviewCollectorError):
    code = "INVALID_SOURCE_RESPONSE"
    status_code = 502


class AnalysisNotFoundError(ReviewCollectorError):
    code = "ANALYSIS_NOT_FOUND"
    status_code = 404
