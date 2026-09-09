import os
from dataclasses import dataclass

DEFAULT_MODEL = "claude-opus-5"


@dataclass(frozen=True)
class LLMSettings:
    """Configuration for the optional LLM insight layer.

    The application is fully functional without an API key: when no key is
    configured the analysis falls back to the deterministic rule-based layer
    and reports an ``LLM_UNAVAILABLE`` warning instead of failing.
    """

    api_key: str | None = None
    model: str = DEFAULT_MODEL
    max_reviews: int = 120
    timeout_seconds: float = 120.0
    effort: str = "medium"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @classmethod
    def from_env(cls) -> "LLMSettings":
        return cls(
            api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            model=os.getenv("APP_LLM_MODEL", DEFAULT_MODEL),
            max_reviews=int(os.getenv("APP_LLM_MAX_REVIEWS", "120")),
            timeout_seconds=float(os.getenv("APP_LLM_TIMEOUT_SECONDS", "120")),
            effort=os.getenv("APP_LLM_EFFORT", "medium"),
        )
