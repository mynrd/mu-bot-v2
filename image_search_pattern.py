import os
import cv2
import numpy as np
from pathlib import Path
from util import console_log
from typing import Optional, Tuple, Iterable, Union
from image_helpers import ImageLike, _to_bgr


def _ensure_dir(p: str):
    Path(p).mkdir(parents=True, exist_ok=True)


def _px_region(shape_hw, region: Optional[Tuple[float, float, float, float]]):
    H, W = shape_hw
    if region is None:
        return (0, 0, W, H)

    x1, y1, x2, y2 = region

    def conv(v, total):
        if isinstance(v, float) and 0.0 <= v <= 1.0:
            return int(round(v * total))
        return int(v)

    X1 = max(0, conv(x1, W))
    Y1 = max(0, conv(y1, H))
    X2 = min(W, conv(x2, W))
    Y2 = min(H, conv(y2, H))
    if X2 <= X1 or Y2 <= Y1:
        raise ValueError("Invalid region after conversion.")
    return (X1, Y1, X2, Y2)


def _canny(img_gray):
    v = np.median(img_gray)
    lo = int(max(0, 0.66 * v))
    hi = int(min(255, 1.33 * v))
    return cv2.Canny(img_gray, lo, hi)


def get_location_by_template_by_img(
    image_input: ImageLike,
    template_input: ImageLike,
    region: Optional[Tuple[float, float, float, float]] = None,
    scales: Iterable[float] = (0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15),
    threshold: float = 0.88,
    weight_edges: float = 0.4,
    debug: bool = False,
    return_box: bool = False,
) -> Optional[Tuple[int, int] | Tuple[int, int, int, int]]:
    big = _to_bgr(image_input)
    tmpl_color = _to_bgr(template_input)

    H, W = big.shape[:2]
    x1, y1, x2, y2 = _px_region((H, W), region)
    search = big[y1:y2, x1:x2]

    search_gray = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
    search_edge = _canny(search_gray)

    best = None

    tmpl_gray0 = cv2.cvtColor(tmpl_color, cv2.COLOR_BGR2GRAY)
    tmpl_edge0 = _canny(tmpl_gray0)

    for k in scales:
        tw = int(round(tmpl_gray0.shape[1] * k))
        th = int(round(tmpl_gray0.shape[0] * k))
        if tw < 8 or th < 8:
            continue
        if tw > search_gray.shape[1] or th > search_gray.shape[0]:
            continue

        tmpl_gray = cv2.resize(tmpl_gray0, (tw, th), interpolation=cv2.INTER_AREA if k < 1.0 else cv2.INTER_CUBIC)
        tmpl_edge = cv2.resize(tmpl_edge0, (tw, th), interpolation=cv2.INTER_AREA if k < 1.0 else cv2.INTER_CUBIC)

        res_g = cv2.matchTemplate(search_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
        res_e = cv2.matchTemplate(search_edge, tmpl_edge, cv2.TM_CCOEFF_NORMED)

        alpha = float(weight_edges)
        res = (1.0 - alpha) * res_g + alpha * res_e

        minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(res)
        if best is None or maxVal > best[0]:
            bx, by = maxLoc
            best = (maxVal, k, (bx, by, tw, th))

    if best is None:
        if debug:
            console_log("template not found | score: 0.000 | image text: ")
        return None

    score, kbest, (bx, by, bw, bh) = best
    x = bx + x1
    y = by + y1
    cx = x + bw // 2
    cy = y + bh // 2

    if debug:
        status = "FOUND" if score >= threshold else "not found"
        console_log(f"template {status} | score: {score:.3f} | scale: {kbest:.3f} | at: ({x},{y},{bw},{bh})")

        _ensure_dir("temp")
        vis = big.copy()
        color = (0, 255, 0) if score >= threshold else (0, 0, 255)
        cv2.rectangle(vis, (x, y), (x + bw, y + bh), color, 2)
        cv2.circle(vis, (cx, cy), max(4, min(12, (bw + bh) // 40)), color, -1)
        cv2.circle(vis, (cx, cy), max(4, min(12, (bw + bh) // 40)), (255, 255, 255), 1)
        score_text = f"{score:.2f}"
        text_pos = (cx + 10, max(0, cy - 10))
        cv2.putText(vis, score_text, text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        out_path = Path("temp/_tmpl_match_vis.png")
        cv2.imwrite(str(out_path), vis)

    if score < threshold:
        return None
    return (cx, cy, bw, bh) if return_box else (cx, cy)


def get_location_by_template(
    img: ImageLike,
    tmpl_color,
    region: Optional[Tuple[float, float, float, float]] = None,
    scales: Iterable[float] = (0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15),
    threshold: float = 0.88,
    weight_edges: float = 0.4,
    debug: bool = False,
    return_box: bool = False,
) -> Optional[Tuple[int, int] | Tuple[int, int, int, int]]:
    big = _to_bgr(img)
    if big is None:
        raise ValueError("invalid image input")

    if tmpl_color is None:
        raise ValueError("invalid template input")

    H, W = big.shape[:2]
    x1, y1, x2, y2 = _px_region((H, W), region)
    search = big[y1:y2, x1:x2]

    search_gray = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
    search_edge = _canny(search_gray)

    best = None

    tmpl_gray0 = cv2.cvtColor(tmpl_color, cv2.COLOR_BGR2GRAY)
    tmpl_edge0 = _canny(tmpl_gray0)

    for k in scales:
        tw = int(round(tmpl_gray0.shape[1] * k))
        th = int(round(tmpl_gray0.shape[0] * k))
        if tw < 8 or th < 8:
            continue
        if tw > search_gray.shape[1] or th > search_gray.shape[0]:
            continue

        tmpl_gray = cv2.resize(tmpl_gray0, (tw, th), interpolation=cv2.INTER_AREA if k < 1.0 else cv2.INTER_CUBIC)
        tmpl_edge = cv2.resize(tmpl_edge0, (tw, th), interpolation=cv2.INTER_AREA if k < 1.0 else cv2.INTER_CUBIC)

        res_g = cv2.matchTemplate(search_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
        res_e = cv2.matchTemplate(search_edge, tmpl_edge, cv2.TM_CCOEFF_NORMED)

        alpha = float(weight_edges)
        res = (1.0 - alpha) * res_g + alpha * res_e

        minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(res)
        if best is None or maxVal > best[0]:
            bx, by = maxLoc
            best = (maxVal, k, (bx, by, tw, th))

    if best is None and debug:
        console_log("template not found | score: 0.000 | image text: ")
        return None

    score, kbest, (bx, by, bw, bh) = best
    x = bx + x1
    y = by + y1
    cx = x + bw // 2
    cy = y + bh // 2

    if debug:
        status = "FOUND" if score >= threshold else "not found"
        console_log(f"template {status} | score: {score:.3f} | scale: {kbest:.3f} | at: ({x},{y},{bw},{bh})")

    if debug:
        _ensure_dir("temp")
        vis = big.copy()
        color = (0, 255, 0) if score >= threshold else (0, 0, 255)
        cv2.rectangle(vis, (x, y), (x + bw, y + bh), color, 2)
        try:
            dot_radius = max(4, min(12, (bw + bh) // 40))
        except Exception:
            dot_radius = 6
        cv2.circle(vis, (cx, cy), dot_radius, color, -1)
        cv2.circle(vis, (cx, cy), dot_radius, (255, 255, 255), 1)
        try:
            score_text = f"{score:.2f}"
            text_pos = (cx + dot_radius + 4, max(0, cy - dot_radius - 4))
            cv2.putText(vis, score_text, text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        except Exception:
            pass
        try:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = Path(f"temp/_tmpl_match_vis_{timestamp}.png")
        except Exception:
            _ensure_dir("temp")
            out_path = Path("temp/_tmpl_match_vis.png")
        cv2.imwrite(str(out_path), vis)

    if score < threshold:
        return None

    if return_box:
        return (cx, cy, bw, bh)
    return (cx, cy)
