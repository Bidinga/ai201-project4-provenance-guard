"""Independent signal/scoring calibration harness.

Runs the four calibration inputs from the project spec through both detection
signals and the combined scorer, printing each signal score separately so you
can see which signal drives each verdict.

Works without a Groq key (the LLM signal uses its deterministic local fallback,
shown as provider=local_fallback). With GROQ_API_KEY set in .env it uses Groq.

    python scripts/test_signals.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from provenance_guard.detectors import llm_signal, stylometric_signal
from provenance_guard.scoring import classify, combine_scores

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

CASES = {
    "clearly AI": (
        "Artificial intelligence represents a transformative paradigm shift in "
        "modern society. It is important to note that while the benefits of AI are "
        "numerous, it is equally essential to consider the ethical implications. "
        "Furthermore, stakeholders across various sectors must collaborate to "
        "ensure responsible deployment."
    ),
    "clearly human": (
        "ok so i finally tried that new ramen place downtown and honestly? "
        "underwhelming. the broth was fine but they put WAY too much sodium in it "
        "and i was thirsty for like three hours after. my friend got the spicy "
        "version and said it was better. probably won't go back unless someone "
        "drags me there"
    ),
    "borderline formal human": (
        "The relationship between monetary policy and asset price inflation has "
        "been extensively studied in the literature. Central banks face a "
        "fundamental tension between their mandate for price stability and the "
        "unintended consequences of prolonged low interest rates on equity and "
        "real estate valuations."
    ),
    "borderline edited AI": (
        "I've been thinking a lot about remote work lately. There are genuine "
        "tradeoffs - flexibility and no commute on one side, isolation and blurred "
        "work-life boundaries on the other. Studies show productivity varies "
        "widely by individual and role type."
    ),
}


def main():
    for name, text in CASES.items():
        llm = llm_signal(text)
        stylo = stylometric_signal(text)
        ai_probability = combine_scores(llm.score, stylo.score)
        result = classify(ai_probability)
        provider = llm.details.get("provider", "?")
        print(f"\n=== {name} ===")
        print(f"  {'llm_classifier':>22}: {llm.score:.3f}  (provider={provider})")
        print(f"  {'stylometric_heuristics':>22}: {stylo.score:.3f}")
        print(f"  {'COMBINED ai_probability':>22}: {ai_probability:.3f}")
        print(f"  {'attribution':>22}: {result.attribution} "
              f"(confidence={result.confidence:.3f}, variant={result.label_variant})")


if __name__ == "__main__":
    main()
