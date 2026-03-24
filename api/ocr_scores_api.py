"""OCR scores data API routes."""

from __future__ import annotations

import json
import os

from flask import Blueprint, jsonify

ocr_scores_bp = Blueprint("ocr_scores", __name__, url_prefix="/api/ocr-scores")

DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ocr_scores_data.json"
)


def _load_data():
    """Load OCR scores from JSON file."""
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@ocr_scores_bp.route("", methods=["GET"])
def get_scores():
    """Return aggregated OCR scores grouped by source and key."""
    raw = _load_data()

    # Aggregate by (source, key)
    agg = {}
    for r in raw:
        k = (r["source"], r["key"])
        if k not in agg:
            agg[k] = {"total": 0, "found": 0, "ms_sum": 0.0, "ms_min": r["ms"], "ms_max": r["ms"]}
        bucket = agg[k]
        bucket["total"] += 1
        if r.get("found"):
            bucket["found"] += 1
        bucket["ms_sum"] += r["ms"]
        if r["ms"] < bucket["ms_min"]:
            bucket["ms_min"] = r["ms"]
        if r["ms"] > bucket["ms_max"]:
            bucket["ms_max"] = r["ms"]

    result = []
    for (source, key), v in sorted(agg.items()):
        result.append({
            "source": source,
            "key": key,
            "total": v["total"],
            "found": v["found"],
            "rate": round(v["found"] / v["total"] * 100, 1) if v["total"] else 0,
            "avgMs": round(v["ms_sum"] / v["total"], 1) if v["total"] else 0,
            "minMs": round(v["ms_min"], 1),
            "maxMs": round(v["ms_max"], 1),
        })

    return jsonify(result)


@ocr_scores_bp.route("/summary", methods=["GET"])
def get_summary():
    """Return high-level summary stats."""
    raw = _load_data()
    if not raw:
        return jsonify({"totalRecords": 0, "sources": 0, "keys": 0, "overallRate": 0, "avgMs": 0})

    sources = set()
    keys = set()
    found_count = 0
    ms_sum = 0.0
    for r in raw:
        sources.add(r["source"])
        keys.add(r["key"])
        if r.get("found"):
            found_count += 1
        ms_sum += r["ms"]

    return jsonify({
        "totalRecords": len(raw),
        "sources": len(sources),
        "keys": len(keys),
        "overallRate": round(found_count / len(raw) * 100, 1),
        "avgMs": round(ms_sum / len(raw), 1),
    })
