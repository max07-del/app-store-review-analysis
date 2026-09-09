import re
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from uuid import uuid4

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.schemas.reviews import (
    ActionableInsight,
    AnalysisResponse,
    AnalyzedReview,
    CollectReviewsResponse,
    DistributionItem,
    KeywordPhrase,
    Metrics,
)

URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"[a-z][a-z'-]{2,}", re.IGNORECASE)
WHITESPACE_PATTERN = re.compile(r"\s+")

STOPWORDS = {
    "can",
    "can't",
    "had",
    "has",
    "hasn't",
    "he",
    "her",
    "him",
    "his",
    "how",
    "i'm",
    "if",
    "in",
    "into",
    "is",
    "isn't",
    "it",
    "it's",
    "its",
    "may",
    "me",
    "most",
    "must",
    "my",
    "myself",
    "never",
    "no",
    "not",
    "now",
    "of",
    "off",
    "on",
    "once",
    "or",
    "our",
    "ours",
    "out",
    "over",
    "same",
    "she",
    "since",
    "so",
    "was",
    "wasn't",
    "we",
    "we're",
    "were",
    "weren't",
    "who",
    "why",
    "will",
    "won't",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "aren't",
    "as",
    "at",
    "about",
    "after",
    "again",
    "also",
    "always",
    "another",
    "app",
    "because",
    "but",
    "by",
    "been",
    "before",
    "being",
    "could",
    "did",
    "didn't",
    "does",
    "doesn't",
    "don't",
    "don",
    "each",
    "even",
    "few",
    "for",
    "from",
    "get",
    "gets",
    "getting",
    "have",
    "having",
    "here",
    "just",
    "like",
    "more",
    "much",
    "make",
    "makes",
    "need",
    "only",
    "one",
    "other",
    "please",
    "really",
    "should",
    "some",
    "still",
    "such",
    "than",
    "that",
    "that's",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "thing",
    "this",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "use",
    "used",
    "using",
    "very",
    "want",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "you",
    "you're",
    "your",
}

KEYWORD_ALIASES = {
    "accounts": "account",
    "cards": "card",
    "charges": "charge",
    "payments": "payment",
    "refunds": "refund",
    "subscriptions": "subscription",
}

ISSUE_AREAS = {
    "stability_and_performance": {
        "terms": {
            "bug",
            "bugs",
            "crash",
            "crashes",
            "crashing",
            "freeze",
            "freezes",
            "lag",
            "loading",
            "slow",
            "update",
        },
        "recommendation": "Prioritize crash, loading, and performance diagnostics; segment incidents by app version.",
    },
    "account_and_access": {
        "terms": {
            "account",
            "banned",
            "blocked",
            "hack",
            "hacked",
            "login",
            "password",
            "suspended",
        },
        "recommendation": "Improve account recovery, login reliability, and explanations for restrictions or suspensions.",
    },
    "support": {
        "terms": {"answer", "contact", "help", "human", "response", "service", "support"},
        "recommendation": "Offer a clearer escalation path to human support and expose case status to users.",
    },
    "billing_and_subscription": {
        "terms": {
            "billing",
            "charge",
            "charged",
            "expensive",
            "payment",
            "price",
            "refund",
            "subscription",
        },
        "recommendation": "Clarify pricing and subscription terms and simplify refund and billing support flows.",
    },
    "privacy_and_security": {
        "terms": {"data", "hack", "hacked", "privacy", "safe", "security", "stolen"},
        "recommendation": "Strengthen security communication and provide immediate, guided actions after suspicious activity.",
    },
    "ads": {
        "terms": {"ad", "ads", "advert", "advertising", "commercial", "sponsored"},
        "recommendation": "Review ad frequency and relevance, especially where ads interrupt core user journeys.",
    },
    "usability_and_features": {
        "terms": {
            "button",
            "difficult",
            "feature",
            "interface",
            "missing",
            "navigation",
            "option",
            "search",
        },
        "recommendation": "Validate the most requested workflows with usability tests and prioritize frequently requested controls.",
    },
}


class ReviewAnalyzer:
    def __init__(self) -> None:
        self.sentiment_analyzer = SentimentIntensityAnalyzer()

    def analyze(
        self,
        collection: CollectReviewsResponse,
    ) -> tuple[AnalysisResponse, list[AnalyzedReview]]:
        analyzed_reviews = [self._analyze_review(review) for review in collection.reviews]
        negative_reviews = [review for review in analyzed_reviews if review.sentiment == "negative"]

        metrics = Metrics(
            total_reviews=len(analyzed_reviews),
            average_rating=self._average_rating(analyzed_reviews),
            rating_distribution=self._distribution(
                [str(review.rating) for review in analyzed_reviews],
                ["1", "2", "3", "4", "5"],
            ),
            sentiment_distribution=self._distribution(
                [review.sentiment for review in analyzed_reviews],
                ["positive", "neutral", "negative"],
            ),
        )

        result = AnalysisResponse(
            analysis_id=str(uuid4()),
            created_at=datetime.now(UTC).isoformat(),
            app=collection.app,
            requested_count=collection.requested_count,
            collected_count=collection.collected_count,
            available_pool_size=collection.available_pool_size,
            is_partial=collection.is_partial,
            warnings=collection.warnings,
            metrics=metrics,
            negative_keywords=self._negative_keywords(negative_reviews),
            insights=self._actionable_insights(negative_reviews),
        )
        return result, analyzed_reviews

    def _analyze_review(self, review):
        cleaned_text = self.clean_text(f"{review.title}. {review.text}")
        text_score = self.sentiment_analyzer.polarity_scores(cleaned_text)["compound"]
        rating_signal = (review.rating - 3) / 2
        score = round(0.5 * text_score + 0.5 * rating_signal, 4)
        if score >= 0.05:
            sentiment = "positive"
        elif score <= -0.05:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return AnalyzedReview(
            **review.model_dump(),
            cleaned_text=cleaned_text,
            sentiment=sentiment,
            sentiment_score=score,
        )

    @staticmethod
    def clean_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value)
        without_urls = URL_PATTERN.sub(" ", normalized)
        return WHITESPACE_PATTERN.sub(" ", without_urls).strip()

    @staticmethod
    def _average_rating(reviews: list[AnalyzedReview]) -> float | None:
        if not reviews:
            return None
        return round(sum(review.rating for review in reviews) / len(reviews), 2)

    @staticmethod
    def _distribution(
        values: list[str],
        categories: list[str],
    ) -> dict[str, DistributionItem]:
        total = len(values)
        counts = Counter(values)
        return {
            category: DistributionItem(
                count=counts[category],
                percentage=round((counts[category] / total * 100) if total else 0.0, 2),
            )
            for category in categories
        }

    def _negative_keywords(
        self,
        reviews: list[AnalyzedReview],
        limit: int = 10,
    ) -> list[KeywordPhrase]:
        counter: Counter[str] = Counter()
        for review in reviews:
            tokens = [
                KEYWORD_ALIASES.get(normalized, normalized)
                for token in TOKEN_PATTERN.findall(review.cleaned_text)
                if (normalized := token.lower().strip("'-"))
            ]
            tokens = [token for token in tokens if token and token not in STOPWORDS]
            counter.update(tokens)
            counter.update(
                f"{first} {second}"
                for first, second in zip(tokens, tokens[1:], strict=False)
                if first != second
            )

        return [
            KeywordPhrase(phrase=phrase, count=count)
            for phrase, count in counter.most_common(limit)
        ]

    def _actionable_insights(
        self,
        reviews: list[AnalyzedReview],
        limit: int = 4,
    ) -> list[ActionableInsight]:
        if not reviews:
            return []

        area_counts: Counter[str] = Counter()
        for review in reviews:
            tokens = {token.lower() for token in TOKEN_PATTERN.findall(review.cleaned_text)}
            for area, config in ISSUE_AREAS.items():
                if tokens & config["terms"]:
                    area_counts[area] += 1

        return [
            ActionableInsight(
                area=area,
                evidence_count=count,
                share_of_negative_reviews=round(count / len(reviews) * 100, 2),
                recommendation=ISSUE_AREAS[area]["recommendation"],
            )
            for area, count in area_counts.most_common(limit)
        ]
