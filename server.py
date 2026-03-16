"""Main server entry point.

Usage:
    python server.py
"""

from __future__ import annotations

import os

from flask import Flask, send_from_directory

from api.map_api import map_bp
from api.bot_config_api import config_bp

app = Flask(__name__, static_folder=None)

PAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages")


@app.route("/")
def index():
    return send_from_directory(PAGES_DIR, "map_mgr.html")


@app.route("/config")
def config_page():
    return send_from_directory(PAGES_DIR, "bot_config.html")


# Register API blueprints
app.register_blueprint(map_bp)
app.register_blueprint(config_bp)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
