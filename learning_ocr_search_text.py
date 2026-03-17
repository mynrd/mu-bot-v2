import os
import json
import time
import cv2
import numpy as np
import pytesseract
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple
from image_helpers import _to_bgr as helpers_to_bgr
from image_helpers import ImageLike


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_ROOT, "config.dat")
_SCORES_PATH = os.path.join(_ROOT, "data", "ocr_scores.json")
_SCORES_DATA_PATH = os.path.join(_ROOT, "data", "ocr_scores_data.json")
_SETTINGS_PATH = os.path.join(_ROOT, "data", "ocr_settings.json")


def _load_config():
    try:
        with open(_CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_batch_size():
    cfg = _load_config()
    return cfg.get("ocr_batch_size", 5)


# ---------------------------------------------------------------------------
# Scores — two-layer learning system
#   ocr_scores_data.json  — append-only raw log of every run
#   ocr_scores.json       — aggregated leaderboard (computed from raw data)
# ---------------------------------------------------------------------------
def _setting_key(setting):
    """Unique string key for a setting (for score tracking)."""
    parts = [setting["name"]]
    for k in sorted(setting):
        if k != "name":
            parts.append(f"{k}={setting[k]}")
    return "|".join(parts)


def _load_scores():
    try:
        with open(_SCORES_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_scores_data():
    try:
        with open(_SCORES_DATA_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return []


def _save_scores_data(data):
    os.makedirs(os.path.dirname(_SCORES_DATA_PATH), exist_ok=True)
    with open(_SCORES_DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _rebuild_scores(data):
    """Recompute ocr_scores.json leaderboard grouped by source."""
    scores = {}  # {source: {key: {wins, fails, total_ms}}}
    for entry in data:
        source = entry.get("source", "")
        key = entry["key"]
        if source not in scores:
            scores[source] = {}
        if key not in scores[source]:
            scores[source][key] = {"wins": 0, "fails": 0, "total_ms": 0.0}
        if entry["found"]:
            scores[source][key]["wins"] += 1
        else:
            scores[source][key]["fails"] += 1
        scores[source][key]["total_ms"] += entry["ms"]

    # Compute final leaderboard grouped by source
    leaderboard = {}
    for source, keys in scores.items():
        leaderboard[source] = {}
        for key, s in keys.items():
            total = s["wins"] + s["fails"]
            leaderboard[source][key] = {
                "wins": s["wins"],
                "fails": s["fails"],
                "avg_ms": s["total_ms"] / total if total > 0 else 0.0,
                "win_rate": s["wins"] / total if total > 0 else 0.0,
            }

    os.makedirs(os.path.dirname(_SCORES_PATH), exist_ok=True)
    with open(_SCORES_PATH, "w") as f:
        json.dump(leaderboard, f, indent=2)
    return leaderboard


def _record_run(source, setting, elapsed, found):
    """Log a run to raw data, then rebuild the leaderboard."""
    data = _load_scores_data()
    data.append({
        "source": source,
        "key": _setting_key(setting),
        "ms": round(elapsed * 1000, 2),
        "found": found,
    })
    _save_scores_data(data)
    _rebuild_scores(data)


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------
def _preprocess(img_bgr, setting):
    """Apply a preprocessing setting to produce a binary OCR-ready image."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    b_ch = cv2.split(img_bgr)[0]
    kernel = np.ones((2, 2), np.uint8)
    name = setting["name"]

    if name == "combined_hsv":
        mask_y = cv2.inRange(hsv, np.array([15, 50, 20]), np.array([50, 255, 255]))
        mask_c = cv2.inRange(hsv, np.array([85, 25, 30]), np.array([115, 255, 255]))
        mask = cv2.bitwise_or(mask_y, mask_c)
        mask = cv2.dilate(mask, kernel, iterations=1)
        return 255 - mask

    if name == "gray_thresh":
        _, th = cv2.threshold(gray, setting["thresh"], 255, cv2.THRESH_BINARY)
        return th

    if name == "saturation":
        _, mask = cv2.threshold(hsv[:, :, 1], 40, 255, cv2.THRESH_BINARY)
        mask = cv2.dilate(mask, kernel, iterations=1)
        return 255 - mask

    if name == "blue_thresh":
        _, th = cv2.threshold(b_ch, setting["thresh"], 255, cv2.THRESH_BINARY)
        return th

    if name == "clahe":
        clahe = cv2.createCLAHE(clipLimit=setting.get("clip", 2.0), tileGridSize=(4, 4))
        enh = clahe.apply(gray)
        _, th = cv2.threshold(enh, setting["thresh"], 255, cv2.THRESH_BINARY)
        return th

    if name == "cyan_hsv":
        mask = cv2.inRange(hsv, np.array([85, 25, 30]), np.array([115, 255, 255]))
        mask = cv2.dilate(mask, kernel, iterations=1)
        return 255 - mask

    if name == "yellow_hsv":
        mask = cv2.inRange(hsv, np.array([15, 50, 20]), np.array([50, 255, 255]))
        mask = cv2.dilate(mask, kernel, iterations=1)
        return 255 - mask

    return gray


# ---------------------------------------------------------------------------
# Settings — loaded from data/ocr_settings.json (add more there)
# ---------------------------------------------------------------------------
_DEFAULT_SETTINGS = [
    {"name": "combined_hsv",  "psm": 7, "scale": 3},
    {"name": "gray_thresh",   "psm": 7, "scale": 3, "thresh": 180},
    {"name": "saturation",    "psm": 7, "scale": 3},
    {"name": "blue_thresh",   "psm": 7, "scale": 3, "thresh": 140},
    {"name": "clahe",         "psm": 7, "scale": 3, "thresh": 180, "clip": 2.0},
    {"name": "gray_thresh",   "psm": 6, "scale": 3, "thresh": 200},
    {"name": "clahe",         "psm": 3, "scale": 3, "thresh": 115, "clip": 2.0},
    {"name": "cyan_hsv",      "psm": 7, "scale": 3},
    {"name": "yellow_hsv",    "psm": 7, "scale": 3},
    {"name": "gray_thresh",   "psm": 6, "scale": 4, "thresh": 210},
    {"name": "gray_thresh",   "psm": 6, "scale": 2, "thresh": 180},
    {"name": "gray_thresh",   "psm": 6, "scale": 1, "thresh": 180},
]


def _load_settings():
    """Load settings from data/ocr_settings.json. Seed file if missing."""
    if not os.path.exists(_SETTINGS_PATH):
        os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
        with open(_SETTINGS_PATH, "w") as f:
            json.dump(_DEFAULT_SETTINGS, f, indent=2)
        return list(_DEFAULT_SETTINGS)
    try:
        with open(_SETTINGS_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return list(_DEFAULT_SETTINGS)


def _sort_settings_by_score(source=""):
    """Return SETTINGS ordered by score for a given source. Filters by source first."""
    all_scores = _load_scores()
    scores = all_scores.get(source, {})

    def _score(setting):
        entry = scores.get(_setting_key(setting))
        if entry is None:
            return (0, 0.0, 999.0)  # no history for this source → lowest priority
        # Primary: wins, Secondary: win_rate, Tertiary: faster is better
        return (entry["wins"], entry.get("win_rate", 0.0), -entry["avg_ms"])

    return sorted(_load_settings(), key=_score, reverse=True)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def _run_setting(img_bgr, setting):
    """Preprocess + OCR for one setting. Returns (setting, text, elapsed)."""
    t0 = time.time()
    ocr_input = _preprocess(img_bgr, setting)
    scale = setting.get("scale", 3)
    psm = setting.get("psm", 7)
    up = cv2.resize(ocr_input, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    text = pytesseract.image_to_string(up, config=f"--psm {psm}").lower().strip()
    elapsed = time.time() - t0
    return (setting, text, elapsed)


def get_text(
    source: str,
    img: ImageLike,
    search: Optional[str] = None,
    region: Optional[Tuple[int, int, int, int]] = None,
    ign: Optional[str] = None,
    show_original: bool = False,
    debug: bool = False,
) -> str:
    img = helpers_to_bgr(img)
    if region is not None:
        x1, y1, x2, y2 = region
        img = img[y1:y2, x1:x2]

    search_lower = search.lower() if search else None
    batch_size = _get_batch_size()
    ordered = _sort_settings_by_score(source)
    all_results = []

    # Process in batches
    for batch_start in range(0, len(ordered), batch_size):
        batch = ordered[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1

        if debug:
            keys = [_setting_key(s) for s in batch]
            print(f"  [batch {batch_num}] {keys}")

        # Race within this batch
        with ThreadPoolExecutor(max_workers=len(batch)) as pool:
            futures = {
                pool.submit(_run_setting, img, s): s
                for s in batch
            }

            winner = None
            for future in as_completed(futures):
                setting, text, elapsed = future.result()
                found = search_lower and search_lower in text
                all_results.append((setting, text, elapsed, found))
                _record_run(source, setting, elapsed, bool(found))
                if debug:
                    print(f"    [{_setting_key(setting)}] -> '{text}' ({elapsed*1000:.0f}ms)")

                if found and winner is None:
                    winner = (setting, text, elapsed)
                    if debug:
                        print(f"  [batch {batch_num}] MATCH via {_setting_key(setting)} — cancelling rest")
                    for f in futures:
                        f.cancel()
                    break

        # Batch produced a winner → return
        if winner is not None:
            return winner[1]

    # No match in any batch — return longest result
    best = max(all_results, key=lambda r: len(r[1]))
    if debug:
        print(f"  [no match] best: {_setting_key(best[0])} -> '{best[1]}'")
    return best[1]
