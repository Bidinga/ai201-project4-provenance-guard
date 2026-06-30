from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreResult:
    attribution: str
    ai_probability: float
    confidence: float
    label_variant: str


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def combine_scores(llm_score: float, stylometric_score: float) -> float:
    """Combine distinct signal scores into an AI-likelihood probability.

    LLM judgment gets slightly more weight because it can consider semantic context,
    while stylometrics keeps the ensemble grounded in measurable text structure.
    When the two signals strongly disagree, the score is pulled toward uncertainty.
    """
    llm_score = clamp(llm_score)
    stylometric_score = clamp(stylometric_score)
    weighted = (0.6 * llm_score) + (0.4 * stylometric_score)

    disagreement = abs(llm_score - stylometric_score)
    if disagreement > 0.35:
        weighted = (weighted * 0.75) + (0.5 * 0.25)

    return round(clamp(weighted), 3)


def classify(ai_probability: float) -> ScoreResult:
    """Map AI probability to attribution, confidence, and label variant."""
    ai_probability = clamp(ai_probability)
    if ai_probability >= 0.70:
        return ScoreResult(
            attribution="likely_ai",
            ai_probability=round(ai_probability, 3),
            confidence=round(ai_probability, 3),
            label_variant="high_confidence_ai",
        )
    if ai_probability <= 0.30:
        return ScoreResult(
            attribution="likely_human",
            ai_probability=round(ai_probability, 3),
            confidence=round(1.0 - ai_probability, 3),
            label_variant="high_confidence_human",
        )
    return ScoreResult(
        attribution="uncertain",
        ai_probability=round(ai_probability, 3),
        confidence=round(1.0 - abs(ai_probability - 0.5) * 2.0, 3),
        label_variant="uncertain",
    )

