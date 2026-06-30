import tempfile
import unittest
from pathlib import Path

from provenance_guard.labels import (
    HIGH_CONFIDENCE_AI_LABEL,
    HIGH_CONFIDENCE_HUMAN_LABEL,
    UNCERTAIN_LABEL,
    label_for_attribution,
)
from provenance_guard.pipeline import analyze_submission
from provenance_guard.scoring import classify, combine_scores
from provenance_guard.storage import AuditStore


class ScoringTests(unittest.TestCase):
    def test_combined_scores_map_to_three_label_bands(self):
        self.assertEqual(classify(0.84).attribution, "likely_ai")
        self.assertEqual(classify(0.50).attribution, "uncertain")
        self.assertEqual(classify(0.18).attribution, "likely_human")

    def test_disagreement_moves_score_toward_uncertainty(self):
        raw_weighted = (0.6 * 0.95) + (0.4 * 0.10)
        moderated = combine_scores(0.95, 0.10)
        self.assertLess(moderated, raw_weighted)
        self.assertGreater(moderated, 0.5)


class LabelTests(unittest.TestCase):
    def test_exact_label_variants_are_available(self):
        self.assertEqual(label_for_attribution("likely_ai"), HIGH_CONFIDENCE_AI_LABEL)
        self.assertEqual(label_for_attribution("likely_human"), HIGH_CONFIDENCE_HUMAN_LABEL)
        self.assertEqual(label_for_attribution("uncertain"), UNCERTAIN_LABEL)


class PipelineTests(unittest.TestCase):
    def test_pipeline_returns_structured_multi_signal_response(self):
        text = (
            "Artificial intelligence represents a transformative paradigm shift in modern society. "
            "It is important to note that ethical implications and responsible deployment require "
            "stakeholders across sectors to collaborate carefully."
        )
        result = analyze_submission(text, "creator-1")
        self.assertIn(result["attribution"], {"likely_ai", "likely_human", "uncertain"})
        self.assertIn("llm_classifier", result["signals"])
        self.assertIn("stylometric_heuristics", result["signals"])
        self.assertGreaterEqual(result["confidence"], 0)
        self.assertLessEqual(result["confidence"], 1)


class StorageTests(unittest.TestCase):
    def test_appeal_updates_status_and_audit_log(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AuditStore(Path(directory) / "test.sqlite3")
            record = analyze_submission(
                "I wrote this after missing the last train home, and the details are messy because it was late.",
                "creator-2",
            )
            store.save_submission(record)
            appeal = store.save_appeal(record["content_id"], "This is based on my own experience.")
            content = store.get_content(record["content_id"])
            events = store.recent_events()

            self.assertEqual(appeal["status"], "under_review")
            self.assertEqual(content["status"], "under_review")
            self.assertEqual(events[0]["event_type"], "appeal")
            self.assertIn("appeal_reasoning", events[0])


if __name__ == "__main__":
    unittest.main()
