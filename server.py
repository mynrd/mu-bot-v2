"""Main server entry point.

Usage:
    python data/server.py
"""

from __future__ import annotations

import os

from flask import Flask, send_from_directory

from map_api import map_bp

app = Flask(__name__, static_folder=None)

PAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages")


@app.route("/")
def index():
    return send_from_directory(PAGES_DIR, "map_mgr.html")


# Register API blueprints
app.register_blueprint(map_bp)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
