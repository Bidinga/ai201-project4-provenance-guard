HIGH_CONFIDENCE_AI_LABEL = (
    "Transparency notice: This work shows strong signs of AI generation. "
    "We are labeling it as likely AI-generated so readers have context. "
    "Creators can appeal this decision if it does not reflect how the work was made."
)

HIGH_CONFIDENCE_HUMAN_LABEL = (
    "Transparency notice: This work shows strong signs of human authorship. "
    "No AI-generation label is being applied based on the current analysis."
)

UNCERTAIN_LABEL = (
    "Transparency notice: Our signals are mixed, so we cannot confidently determine "
    "whether this work was human-written or AI-generated. No high-confidence attribution "
    "label is being applied."
)


def label_for_attribution(attribution: str) -> str:
    """Return reader-facing label text for an attribution result."""
    if attribution == "likely_ai":
        return HIGH_CONFIDENCE_AI_LABEL
    if attribution == "likely_human":
        return HIGH_CONFIDENCE_HUMAN_LABEL
    return UNCERTAIN_LABEL

