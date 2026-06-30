from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SignalResult:
    name: str
    score: float
    details: dict


AI_PHRASES = (
    "it is important to note",
    "in conclusion",
    "furthermore",
    "moreover",
    "stakeholders",
    "paradigm shift",
    "ethical implications",
    "responsible deployment",
    "multifaceted",
    "robust framework",
)

HUMAN_MARKERS = (
    "honestly",
    "kinda",
    "sort of",
    "way too",
    "idk",
    "lol",
    "??",
    "!!",
)


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z']+", text.lower())


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def llm_signal(text: str) -> SignalResult:
    """Return an AI-likelihood score from Groq, with a deterministic local fallback."""
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        try:
            return _groq_signal(text, api_key)
        except Exception as exc:  # pragma: no cover - depends on network/API availability
            fallback = _local_llm_fallback(text)
            return SignalResult(
                name="llm_classifier",
                score=fallback.score,
                details={**fallback.details, "provider": "local_fallback", "groq_error": str(exc)},
            )

    fallback = _local_llm_fallback(text)
    return SignalResult(
        name="llm_classifier",
        score=fallback.score,
        details={**fallback.details, "provider": "local_fallback"},
    )


def _groq_signal(text: str, api_key: str) -> SignalResult:
    from groq import Groq

    client = Groq(api_key=api_key)
    prompt = (
        "Classify whether this text is AI-generated or human-written. "
        "Return only compact JSON with keys ai_probability and rationale. "
        "ai_probability must be a number between 0 and 1.\n\n"
        f"TEXT:\n{text[:6000]}"
    )
    completion = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        messages=[
            {"role": "system", "content": "You are a cautious provenance classifier."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    content = completion.choices[0].message.content or "{}"
    parsed = json.loads(content)
    score = _clamp(float(parsed.get("ai_probability", 0.5)))
    return SignalResult(
        name="llm_classifier",
        score=round(score, 3),
        details={"provider": "groq", "rationale": parsed.get("rationale", "")},
    )


def _local_llm_fallback(text: str) -> SignalResult:
    lower = text.lower()
    phrase_hits = sum(1 for phrase in AI_PHRASES if phrase in lower)
    human_hits = sum(1 for marker in HUMAN_MARKERS if marker in lower)
    words = tokenize(text)
    sentences = split_sentences(text)
    avg_word_len = _mean([len(word) for word in words])
    avg_sentence_len = _mean([len(tokenize(sentence)) for sentence in sentences])

    score = 0.45
    score += min(0.30, phrase_hits * 0.08)
    score -= min(0.28, human_hits * 0.09)
    if avg_sentence_len >= 18:
        score += 0.10
    if avg_word_len >= 5.2:
        score += 0.06
    if re.search(r"\b(I|my|me|we|our)\b", text):
        score -= 0.07

    return SignalResult(
        name="llm_classifier",
        score=round(_clamp(score), 3),
        details={
            "phrase_hits": phrase_hits,
            "human_marker_hits": human_hits,
            "avg_word_length": round(avg_word_len, 2),
            "avg_sentence_length": round(avg_sentence_len, 2),
        },
    )


def stylometric_signal(text: str) -> SignalResult:
    """Score text structure for AI-like uniformity and polish."""
    words = tokenize(text)
    sentences = split_sentences(text)
    if not words:
        return SignalResult(
            name="stylometric_heuristics",
            score=0.5,
            details={"reason": "empty_text"},
        )

    sentence_lengths = [len(tokenize(sentence)) for sentence in sentences] or [len(words)]
    avg_sentence_len = _mean(sentence_lengths)
    sentence_stddev = math.sqrt(_variance(sentence_lengths))
    type_token_ratio = len(set(words)) / len(words)
    punctuation_density = len(re.findall(r"[,;:!?-]", text)) / max(1, len(words))
    first_person_rate = len(re.findall(r"\b(i|me|my|mine|we|our|us)\b", text.lower())) / len(words)

    uniformity_score = 1.0 - min(sentence_stddev / 12.0, 1.0)
    length_score = min(avg_sentence_len / 24.0, 1.0)
    vocab_smoothness = 1.0 - min(max(type_token_ratio - 0.35, 0.0) / 0.55, 1.0)
    punctuation_smoothness = 1.0 - min(punctuation_density / 0.22, 1.0)
    personal_voice_penalty = min(first_person_rate / 0.08, 1.0)

    score = (
        0.30 * uniformity_score
        + 0.25 * length_score
        + 0.20 * vocab_smoothness
        + 0.15 * punctuation_smoothness
        + 0.10 * (1.0 - personal_voice_penalty)
    )

    return SignalResult(
        name="stylometric_heuristics",
        score=round(_clamp(score), 3),
        details={
            "sentence_count": len(sentences),
            "word_count": len(words),
            "avg_sentence_length": round(avg_sentence_len, 2),
            "sentence_length_stddev": round(sentence_stddev, 2),
            "type_token_ratio": round(type_token_ratio, 3),
            "punctuation_density": round(punctuation_density, 3),
            "first_person_rate": round(first_person_rate, 3),
        },
    )
