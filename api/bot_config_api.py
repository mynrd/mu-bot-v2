"""Bot configuration API routes."""

from __future__ import annotations

import glob
import os
import re

from flask import Blueprint, jsonify, request

config_bp = Blueprint("config", __name__, url_prefix="/api/config")

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


def _list_config_files():
    """Return list of bot_config*.ini filenames in the config directory."""
    pattern = os.path.join(CONFIG_DIR, "bot_config*.ini")
    files = glob.glob(pattern)
    return sorted(os.path.basename(f) for f in files)


def _parse_config(text: str):
    """Parse a bot_config .ini file into a list of entries.

    Each entry is a dict with:
      - type: "comment" | "blank" | "setting"
      - raw: the original line text
      - key/value: only for type=="setting"
    """
    entries = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            entries.append({"type": "blank", "raw": line})
        elif stripped.startswith("#"):
            entries.append({"type": "comment", "raw": line})
        else:
            match = re.match(r"^([A-Z_][A-Z0-9_]*)\s*:\s*(.*)", stripped)
            if match:
                entries.append({
                    "type": "setting",
                    "raw": line,
                    "key": match.group(1),
                    "value": match.group(2),
                })
            else:
                entries.append({"type": "comment", "raw": line})
    return entries


def _rebuild_config(entries, updates: dict):
    """Rebuild config text applying updates to matching keys."""
    lines = []
    for entry in entries:
        if entry["type"] == "setting" and entry["key"] in updates:
            lines.append(f"{entry['key']}: {updates[entry['key']]}")
        else:
            lines.append(entry["raw"])
    return "\n".join(lines) + "\n"


@config_bp.route("/files", methods=["GET"])
def list_files():
    """Return list of available bot_config*.ini files."""
    return jsonify(_list_config_files())


@config_bp.route("/files/<filename>", methods=["GET"])
def get_file(filename: str):
    """Return parsed contents of a config file."""
    if filename not in _list_config_files():
        return jsonify({"error": "File not found"}), 404

    filepath = os.path.join(CONFIG_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    entries = _parse_config(text)
    settings = [
        {"key": e["key"], "value": e["value"]}
        for e in entries
        if e["type"] == "setting"
    ]
    return jsonify({"filename": filename, "settings": settings})


@config_bp.route("/files/<filename>", methods=["PUT"])
def update_file(filename: str):
    """Update settings in a config file.

    Expects JSON body: {"settings": {"KEY": "value", ...}}
    """
    if filename not in _list_config_files():
        return jsonify({"error": "File not found"}), 404

    data = request.get_json()
    if not data or "settings" not in data:
        return jsonify({"error": "Invalid body — expected {\"settings\": {...}}"}), 400

    updates = data["settings"]

    filepath = os.path.join(CONFIG_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    entries = _parse_config(text)
    new_text = _rebuild_config(entries, updates)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_text)

    return jsonify({"message": f"{filename} updated", "updated_keys": list(updates.keys())})
