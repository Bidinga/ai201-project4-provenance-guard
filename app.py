from __future__ import annotations

import os

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

from provenance_guard.pipeline import analyze_submission
from provenance_guard.storage import AuditStore


load_dotenv()


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.getenv("DATABASE_PATH", "instance/provenance_guard.sqlite3"),
        RATELIMIT_STORAGE_URI=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
        SUBMIT_RATE_LIMIT=os.getenv("SUBMIT_RATE_LIMIT", "10 per minute;100 per day"),
    )
    if test_config:
        app.config.update(test_config)

    store = AuditStore(app.config["DATABASE"])
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[],
        storage_uri=app.config["RATELIMIT_STORAGE_URI"],
    )

    @app.get("/")
    def index():
        return (
            "<h1>Provenance Guard</h1>"
            "<p>Multi-signal AI content attribution API. This is a JSON API, not a website.</p>"
            "<ul>"
            "<li><b>POST /submit</b> &mdash; classify text "
            "<code>{text, creator_id}</code> (use curl)</li>"
            "<li><b>POST /appeal</b> &mdash; contest a classification "
            "<code>{content_id, creator_reasoning}</code> (use curl)</li>"
            "<li><a href='/log'><b>GET /log</b></a> &mdash; recent audit-log entries</li>"
            "<li><a href='/health'><b>GET /health</b></a> &mdash; health check</li>"
            "</ul>"
            "<p>See the README for example curl commands.</p>"
        )

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.post("/submit")
    @limiter.limit(lambda: app.config["SUBMIT_RATE_LIMIT"])
    def submit():
        payload = request.get_json(silent=True) or {}
        try:
            record = analyze_submission(
                text=str(payload.get("text", "")),
                creator_id=str(payload.get("creator_id", "")),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        store.save_submission(record)
        return jsonify(
            {
                "content_id": record["content_id"],
                "attribution": record["attribution"],
                "confidence": record["confidence"],
                "ai_probability": record["ai_probability"],
                "label": record["label_text"],
                "label_variant": record["label_variant"],
                "signals": record["signals"],
                "status": record["status"],
            }
        ), 200

    @app.post("/appeal")
    def appeal():
        payload = request.get_json(silent=True) or {}
        content_id = str(payload.get("content_id", "")).strip()
        creator_reasoning = str(payload.get("creator_reasoning", "")).strip()
        if not content_id:
            return jsonify({"error": "content_id is required"}), 400
        if not creator_reasoning:
            return jsonify({"error": "creator_reasoning is required"}), 400

        try:
            appeal_record = store.save_appeal(content_id, creator_reasoning)
        except KeyError:
            return jsonify({"error": "content_id not found"}), 404

        return jsonify(
            {
                "message": "Appeal received and queued for human review.",
                "content_id": content_id,
                "status": appeal_record["status"],
                "appeal_reasoning": appeal_record["appeal_reasoning"],
            }
        ), 200

    @app.get("/log")
    def log():
        limit = request.args.get("limit", "25")
        try:
            parsed_limit = max(1, min(100, int(limit)))
        except ValueError:
            parsed_limit = 25
        return jsonify({"entries": store.recent_events(parsed_limit)})

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
