# Provenance Guard Planning

## Architecture

```text
Submission flow
POST /submit
  -> validate JSON {text, creator_id}
  -> LLM classifier signal
       passes raw text, returns AI-likelihood score + rationale/details
  -> stylometric heuristic signal
       passes raw text, returns AI-likelihood score + measurable metrics
  -> confidence scorer
       combines signal scores into ai_probability, attribution, confidence
  -> transparency label generator
       maps attribution band to reader-facing label text
  -> SQLite audit log
       stores decision, signal scores, confidence, status
  -> JSON response
       returns content_id, attribution, confidence, label, signals

Appeal flow
POST /appeal
  -> validate JSON {content_id, creator_reasoning}
  -> content lookup
  -> status update to under_review
  -> SQLite audit log
       stores appeal alongside the original decision details
  -> JSON response
       confirms appeal is queued for human review
```

A submission moves through validation, two independent detection signals, calibrated scoring, label generation, and durable audit logging before the API returns the result. An appeal uses the `content_id` from the submission response, changes that content's status to `under_review`, and records the creator's reasoning in the same audit trail as the original classification.

## Detection Signals

### Signal 1: LLM Classifier

The LLM signal estimates whether the passage reads as AI-generated based on semantic coherence, generic phrasing, and overall style. It returns a score from `0.0` to `1.0`, where `1.0` means high AI likelihood. In production it can call Groq's `llama-3.3-70b-versatile`; for local grading without an API key, the implementation falls back to a deterministic classifier that looks for AI-associated phrases and human voice markers.

Blind spot: an LLM can overreact to polished formal writing or underreact to lightly edited AI output. It is also not proof of authorship, so it should not be the only signal.

### Signal 2: Stylometric Heuristics

The stylometric signal measures sentence-length variance, average sentence length, vocabulary diversity, punctuation density, and first-person voice. It returns a score from `0.0` to `1.0`, where higher values indicate AI-like uniformity and polish. This signal is independent from the LLM because it uses measurable text structure rather than semantic judgment.

Blind spot: some human genres, especially academic prose and short formal statements, naturally look uniform. Some human poems use repetition and simple vocabulary, which can also look machine-like.

### Combination

The system combines the two scores as `0.60 * llm_score + 0.40 * stylometric_score`. If the signals disagree by more than `0.35`, the result is moderated toward `0.50` because disagreement is evidence of uncertainty. The combined value is called `ai_probability`.

## Uncertainty Representation

`ai_probability` represents direction: values closer to `1.0` mean more AI-like, values closer to `0.0` mean more human-like. The user-facing `confidence` represents confidence in the chosen attribution, not always AI likelihood.

Thresholds:

| AI probability | Attribution | Confidence |
| --- | --- | --- |
| `>= 0.70` | `likely_ai` | same as AI probability |
| `0.31` to `0.69` | `uncertain` | highest near `0.50`, meaning uncertainty is high |
| `<= 0.30` | `likely_human` | `1 - ai_probability` |

This intentionally creates a wide uncertain band because a false positive against a human creator is more harmful than a false negative.

## Transparency Label Design

| Variant | Exact text |
| --- | --- |
| High-confidence AI | "Transparency notice: This work shows strong signs of AI generation. We are labeling it as likely AI-generated so readers have context. Creators can appeal this decision if it does not reflect how the work was made." |
| High-confidence human | "Transparency notice: This work shows strong signs of human authorship. No AI-generation label is being applied based on the current analysis." |
| Uncertain | "Transparency notice: Our signals are mixed, so we cannot confidently determine whether this work was human-written or AI-generated. No high-confidence attribution label is being applied." |

## Appeals Workflow

Any creator with a `content_id` can submit an appeal using `POST /appeal`. They provide `content_id` and `creator_reasoning`; the system looks up the original classification, updates the content status to `under_review`, and writes an appeal audit event with the original attribution, original confidence, and creator reasoning. A human reviewer opening the appeal queue would see the text, original signal scores, label, status, and the appeal explanation.

## Anticipated Edge Cases

A polished academic paragraph written by a human may score AI-like because long sentences, low punctuation variation, and formal vocabulary look uniform. A poem with repeated simple lines may also score AI-like because the stylometric signal treats repetition as low vocabulary diversity. Very short text is rejected below 40 characters because the signals are unstable without enough evidence. Lightly edited AI output may remain uncertain because personal phrasing can lower both signal scores.

## API Surface

`POST /submit` accepts JSON with `text` and `creator_id`. It returns `content_id`, `attribution`, `confidence`, `ai_probability`, `label`, `label_variant`, `signals`, and `status`.

`POST /appeal` accepts JSON with `content_id` and `creator_reasoning`. It returns a confirmation message, `content_id`, `status`, and the captured reasoning.

`GET /log?limit=25` returns recent audit events as structured JSON. `GET /health` returns a lightweight health check.

## AI Tool Plan

M3: Use the detection signal section and architecture diagram to ask for a Flask app skeleton, `POST /submit`, the LLM signal function, and initial audit logging. Verify with direct function calls and a curl request before adding the second signal.

M4: Use the detection signal, uncertainty, and architecture sections to ask for the stylometric signal and confidence combiner. Check that scores vary across clearly AI, clearly human, formal-borderline, and edited-AI examples.

M5: Use the label and appeals sections to ask for label mapping, `POST /appeal`, rate limiting, and complete audit records. Verify that all three labels are reachable, an appeal changes status to `under_review`, and rate limiting returns `429` after the configured burst.

