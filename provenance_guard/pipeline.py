from __future__ import annotations

from uuid import uuid4

from provenance_guard.detectors import llm_signal, stylometric_signal
from provenance_guard.labels import label_for_attribution
from provenance_guard.scoring import classify, combine_scores
from provenance_guard.storage import utc_now


MIN_TEXT_LENGTH = 40


def analyze_submission(text: str, creator_id: str) -> dict:
    text = text.strip()
    creator_id = creator_id.strip()
    if not text:
        raise ValueError("text is required")
    if not creator_id:
        raise ValueError("creator_id is required")
    if len(text) < MIN_TEXT_LENGTH:
        raise ValueError(f"text must be at least {MIN_TEXT_LENGTH} characters")

    llm = llm_signal(text)
    stylometric = stylometric_signal(text)
    ai_probability = combine_scores(llm.score, stylometric.score)
    result = classify(ai_probability)
    label_text = label_for_attribution(result.attribution)

    return {
        "content_id": str(uuid4()),
        "creator_id": creator_id,
        "timestamp": utc_now(),
        "text": text,
        "attribution": result.attribution,
        "confidence": result.confidence,
        "ai_probability": result.ai_probability,
        "label_variant": result.label_variant,
        "label_text": label_text,
        "signals": {
            "llm_classifier": {"score": llm.score, "details": llm.details},
            "stylometric_heuristics": {"score": stylometric.score, "details": stylometric.details},
        },
        "status": "classified",
    }

