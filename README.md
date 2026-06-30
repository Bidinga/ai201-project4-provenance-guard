# Provenance Guard

Provenance Guard is a Flask backend that creative platforms can use to analyze text submissions, return an attribution result with confidence, show a reader-facing transparency label, and handle creator appeals.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Optional Groq support:

```bash
cp .env.example .env
# Add GROQ_API_KEY=your_key_here
```

Without `GROQ_API_KEY`, the LLM classifier uses a deterministic local fallback so the project can still run and be graded.

## Architecture Overview

A submission enters through `POST /submit` with `text` and `creator_id`. The API validates the payload, runs an LLM-style classifier and a stylometric heuristic classifier, combines the two scores into an AI probability and confidence score, maps that result to a transparency label, writes a structured SQLite audit event, and returns the decision with a `content_id`.

Appeals enter through `POST /appeal` with `content_id` and `creator_reasoning`. The API looks up the original decision, updates the content status to `under_review`, writes an appeal event with the original score and creator reasoning, and returns a confirmation.

## Endpoints

```bash
curl -s -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that ethical implications and responsible deployment require stakeholders across sectors to collaborate carefully.", "creator_id": "test-user-1"}' | python -m json.tool
```

```bash
curl -s -X POST http://localhost:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "PASTE-CONTENT-ID-HERE", "creator_reasoning": "I wrote this myself from personal experience. My style may look formal because English is not my first language."}' | python -m json.tool
```

```bash
curl -s http://localhost:5000/log?limit=3 | python -m json.tool
```

## Detection Signals

Signal 1 is an LLM classifier. With `GROQ_API_KEY`, it asks Groq's `llama-3.3-70b-versatile` for a structured AI probability. Without a key, it uses a local fallback that scores generic AI-associated phrasing and human voice markers. This signal captures broad semantic and stylistic judgment, but it can mistake polished human prose for AI.

Signal 2 is stylometric heuristics. It measures sentence-length variance, average sentence length, type-token ratio, punctuation density, and first-person voice. This signal captures structural uniformity, but it can misread formal academic writing or repetitive poetry.

## Confidence Scoring

Both signals produce an AI-likelihood score from `0.0` to `1.0`. The combiner uses `0.60 * llm_score + 0.40 * stylometric_score`; if the two signals disagree strongly, the result moves toward `0.50` to represent uncertainty.

Thresholds:

| AI probability | Attribution | Label variant |
| --- | --- | --- |
| `>= 0.70` | `likely_ai` | High-confidence AI |
| `0.31` to `0.69` | `uncertain` | Uncertain |
| `<= 0.30` | `likely_human` | High-confidence human |

Example calibration from local tests:

| Input type | LLM score | Stylometric score | AI probability | Result |
| --- | ---: | ---: | ---: | --- |
| AI-like policy paragraph | `0.81` | `0.538` | `0.701` | `likely_ai` |
| Informal ramen review | `0.20` | `0.403` | `0.281` | `likely_human` |
| Formal academic paragraph | `0.61` | `0.651` | `0.626` | `uncertain` |
| Lightly edited AI-style paragraph | `0.38` | `0.478` | `0.419` | `uncertain` |

The wide uncertain band is deliberate because labeling a human writer as AI-generated is the most harmful failure mode for this product.

## Transparency Labels

| Variant | Exact displayed text |
| --- | --- |
| High-confidence AI | "Transparency notice: This work shows strong signs of AI generation. We are labeling it as likely AI-generated so readers have context. Creators can appeal this decision if it does not reflect how the work was made." |
| High-confidence human | "Transparency notice: This work shows strong signs of human authorship. No AI-generation label is being applied based on the current analysis." |
| Uncertain | "Transparency notice: Our signals are mixed, so we cannot confidently determine whether this work was human-written or AI-generated. No high-confidence attribution label is being applied." |

## Appeals Workflow

Creators appeal with a `content_id` and their reasoning. The API stores the explanation, keeps the original classification details, and changes the content status to `under_review`. Automated reclassification is intentionally out of scope; the appeal creates a clear handoff point for a human reviewer.

## Rate Limiting

`POST /submit` is limited to `10 per minute;100 per day` per client IP using `Flask-Limiter` with `memory://` storage for local development. Ten per minute is enough for normal writing-platform usage, including a creator testing several drafts, while blocking simple flooding scripts. One hundred per day allows heavy legitimate use without making the public endpoint unlimited.

Rate-limit test command:

```bash
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    -d '{"text": "This is a test submission for rate limit testing purposes only.", "creator_id": "ratelimit-test"}'
done
```

Expected output after a fresh server start:

```text
200
200
200
200
200
200
200
200
200
200
429
429
```

## Audit Log

Audit events are stored in SQLite and exposed through `GET /log`. Each classification records timestamp, content ID, creator ID, attribution, confidence, AI probability, label variant, both signal scores, and status. Each appeal records the appeal reasoning, status change, and original decision details.

See `data/sample_audit_log.json` for three representative structured entries: two classifications and one appeal.

## Known Limitations

Formal human writing can be over-scored as AI because both signals may see long sentences, polished vocabulary, and low variance. Repetitive poetry can also be misread because low vocabulary diversity and repeated structure resemble generated text. The system rejects very short submissions because neither signal has enough evidence to classify them responsibly.

## Spec Reflection

The planning spec helped most with thresholds: deciding the uncertain band before coding kept the implementation from becoming a binary detector disguised as a confidence score. One implementation detail diverged from the original Groq-first plan: I added a deterministic local fallback so the project remains runnable without network access or an API key.

## AI Usage

I directed AI assistance to turn the architecture plan into a Flask route structure, detector modules, scoring helpers, and SQLite audit storage. I revised the generated shape to keep the core pipeline testable without Flask installed.

I also used AI assistance to calibrate the local fallback against four sample inputs. I overrode the first scoring pass by making personal voice markers lower the AI score more strongly, because the initial result put a clearly informal human sample too close to the AI boundary.

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

These tests cover score thresholds, disagreement moderation, exact label variants, multi-signal pipeline output, and appeal audit logging.

For a quick calibration printout, run:

```bash
python scripts/test_signals.py
```
