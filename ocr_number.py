from __future__ import annotations

import os
import re
from typing import Optional, Tuple, Union, Iterable, List
from collections import Counter
from image_helpers import ImageLike, Image

import numpy as np
import cv2

try:
    import pytesseract
except Exception as e:
    pytesseract = None
    _IMPORT_ERR = e
else:
    _IMPORT_ERR = None

# Normalize common confusions BEFORE stripping non-digits
CHAR_TO_DIGIT = str.maketrans(
    {
        "I": "1",
        "l": "1",
        "|": "1",
        "¡": "1",
        "¹": "1",
        "‖": "1",
        "O": "0",
        "o": "0",
        "°": "0",
        "D": "0",
        "Q": "0",
        "S": "5",
        "s": "5",
        "$": "5",
        "B": "8",
        "Z": "2",
        "z": "2",
        "T": "7",
        "?": "7",
        "‰": "%",
        "§": "%",
    }
)


def _to_bgr(img_like: ImageLike):
    if isinstance(img_like, str):
        bgr = cv2.imread(img_like)
        if bgr is None:
            raise FileNotFoundError(img_like)
        base, _ = os.path.splitext(os.path.basename(img_like))
        folder = os.path.dirname(img_like) or os.getcwd()
        return bgr, base, folder
    elif isinstance(img_like, np.ndarray):
        return img_like, "frame", os.getcwd()
    elif Image is not None and isinstance(img_like, Image.Image):
        rgb = np.array(img_like.convert("RGB"))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        return bgr, "frame", os.getcwd()
    else:
        raise TypeError(f"Unsupported image type: {type(img_like)}")


def _to_px_region(shape, region: Optional[Tuple[float, float, float, float]]):
    if not region:
        H, W = shape[:2]
        return (0, 0, W, H)
    H, W = shape[:2]

    def conv(v, t):
        return int(v * t) if isinstance(v, float) and 0 <= v <= 1 else int(v)

    x1, y1, x2, y2 = region
    X1 = max(0, conv(x1, W))
    Y1 = max(0, conv(y1, H))
    X2 = min(W, conv(x2, W))
    Y2 = min(H, conv(y2, H))
    if X2 <= X1:
        X2 = min(W, X1 + 1)
    if Y2 <= Y1:
        Y2 = min(H, Y1 + 1)
    return (X1, Y1, X2, Y2)


def _preprocess_for_digits(bgr: np.ndarray) -> Iterable[Tuple[str, np.ndarray]]:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
    blur = cv2.GaussianBlur(clahe, (0, 0), 1.0)
    sharp = cv2.addWeighted(clahe, 1.7, blur, -0.7, 0)
    norm = cv2.normalize(sharp, None, 0, 255, cv2.NORM_MINMAX)

    H = norm.shape[0]
    target_h = 120
    scale = float(np.clip(target_h / max(H, 1), 1.5, 3.2))
    up = cv2.resize(norm, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    up = cv2.bilateralFilter(up, 5, 30, 30)

    _, otsu = cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mean = float(np.mean(otsu))
    base = otsu if mean > 127 else cv2.bitwise_not(otsu)  # black digits on white bg
    inv = cv2.bitwise_not(base)  # white digits on black bg

    k = np.ones((2, 2), np.uint8)
    base_c = cv2.morphologyEx(base, cv2.MORPH_CLOSE, k, iterations=1)
    inv_c = cv2.morphologyEx(inv, cv2.MORPH_CLOSE, k, iterations=1)

    yield "base", base
    yield "inv", inv
    yield "base_c", base_c
    yield "inv_c", inv_c

    # Auto-tightened crops (helps remove UI borders that look like "1")
    for tag, bin_im, pos_is_white in [
        ("tight_base", base, False),
        ("tight_base_c", base_c, False),
        ("tight_inv", inv, True),
        ("tight_inv_c", inv_c, True),
    ]:
        tight = _tight_crop(bin_im, pos_is_white)
        if tight is not None:
            yield tag, tight


def _tight_crop(bin_im: np.ndarray, positive_is_white: bool) -> Optional[np.ndarray]:
    im = bin_im
    if positive_is_white:
        fg = (im > 127).astype(np.uint8) * 255
    else:
        fg = (im < 127).astype(np.uint8) * 255

    k = np.ones((2, 2), np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, k, iterations=1)

    cnts, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    boxes = [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) >= 8]
    if not boxes:
        return None
    x1 = min(x for (x, y, w, h) in boxes)
    y1 = min(y for (x, y, w, h) in boxes)
    x2 = max(x + w for (x, y, w, h) in boxes)
    y2 = max(y + h for (x, y, w, h) in boxes)

    pad = 2
    H, W = im.shape[:2]
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(W, x2 + pad)
    y2 = min(H, y2 + pad)
    if x2 <= x1 or y2 <= y1:
        return None
    return im[y1:y2, x1:x2]


def _tess(im_bin: np.ndarray, psm: int) -> str:
    if pytesseract is None:
        raise RuntimeError(f"pytesseract is not available: {_IMPORT_ERR}")
    cfg = f"--oem 1 --psm {psm} -c tessedit_char_whitelist=0123456789% -c user_defined_dpi=300"
    return pytesseract.image_to_string(im_bin, config=cfg)


def _clean_text(text: str) -> Tuple[str, str]:
    if not text:
        return "", ""
    t_norm = text.translate(CHAR_TO_DIGIT)
    keep_pct = re.sub(r"[^\d%]+", "", t_norm)
    only_digits = re.sub(r"\D+", "", t_norm)
    return keep_pct, only_digits


def extract_number(
    image_input: ImageLike,
    region: Optional[Tuple[float, float, float, float]] = None,
    *,
    show_all_digits: bool = False,
    number_range: Optional[Tuple[int, int]] = (0, 100),
    debug: bool = False,
) -> Optional[int]:
    bgr, _base, _folder = _to_bgr(image_input)
    x1, y1, x2, y2 = _to_px_region(bgr.shape, region)
    roi = bgr[y1:y2, x1:x2].copy()

    candidates: List[Tuple[str, int, str, str, str]] = []
    for label, im_bin in _preprocess_for_digits(roi):
        for psm in (7, 8, 13):
            try:
                raw = _tess(im_bin, psm).strip()
            except Exception as e:
                if debug:
                    print(f"[debug] Tess error {label} psm={psm}: {e}")
                continue
            if not raw:
                continue
            t_digits, only_digits = _clean_text(raw)
            if debug:
                print(f"[debug] {label} psm={psm} raw={raw!r} norm={t_digits!r} digits={only_digits!r}")
            candidates.append((label, psm, raw, t_digits, only_digits))

    if not candidates:
        if debug:
            print("[debug] No OCR candidates produced.")
        return None

    if show_all_digits:
        runs = [c[4] for c in candidates if c[4]]
        if not runs:
            return None

        s_set = set(runs)
        preferred = []
        for s in runs:
            if len(s) > 1 and s[0] == "1" and s[1:] in s_set:
                preferred.append(s[1:])
            else:
                preferred.append(s)

        cnt = Counter(preferred)
        best_str, _ = max(cnt.items(), key=lambda kv: (kv[1], len(kv[0])))
        try:
            return int(best_str)
        except Exception:
            return None

    lo, hi = number_range if number_range is not None else (None, None)
    best_val: Optional[int] = None
    best_score = -1
    pat = re.compile(r"(?<!\d)(\d{1,3})(?!\d)%?$")

    for _label, _psm, _raw, t_digits, only_digits in candidates:
        m = pat.search(t_digits) or pat.search(only_digits)
        if m:
            s = m.group(1)
        else:
            multi = re.findall(r"\d{1,3}", t_digits)
            if not multi:
                continue
            s = multi[0]
        try:
            val = int(s)
        except Exception:
            continue

        in_range = True
        if lo is not None and val < lo:
            in_range = False
        if hi is not None and val > hi:
            in_range = False

        if in_range:
            score = len(s)
            if score > best_score:
                best_score = score
                best_val = val
            continue

        if hi is not None and val > hi and s.startswith("1") and len(s) >= 2:
            try:
                val2 = int(s[1:])
            except Exception:
                val2 = None
            if val2 is not None and (lo is None or val2 >= lo) and (hi is None or val2 <= hi):
                score = len(s) - 1
                if score > best_score:
                    best_score = score
                    best_val = val2

    return best_val
