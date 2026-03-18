import cv2
import numpy as np
import pytesseract
import os
import uuid
from typing import Optional, Tuple
from image_helpers import _to_bgr as helpers_to_bgr
from image_helpers import ImageLike


HSV_S_MAX = 30
HSV_V_MIN = 200
GRAY_THR = 200
UPSCALE = 2
INVERT_FOR_OCR = False


def _save_debug(img, ign: Optional[str], suffix: str, tag: str = "") -> str:
    os.makedirs("temp", exist_ok=True)
    prefix = ign if ign else "debug"
    rand = uuid.uuid4().hex[:8]
    fname = f"{prefix}_get_search_text{('_' + tag) if tag else ''}_{rand}.png"
    fpath = os.path.join("temp", fname)
    try:
        cv2.imwrite(fpath, img)
    except Exception:
        pass
    print(f"[DEBUG] Saved {suffix} image: {fpath}")
    return fpath

def get_search_text(
    source: str,
    img: ImageLike,
    search: Optional[str] = None,
    region: Optional[Tuple[int, int, int, int]] = None,
    ign: Optional[str] = None,
    show_original: bool = False,
    debug: bool = False,
) -> str:
    from learning_ocr_search_text import get_text
    return get_text(source, img, search=search, region=region, ign=ign, show_original=show_original, debug=debug)

def get_text_stats(
    img: ImageLike,
    search: Optional[str] = None,
    region: Optional[Tuple[int, int, int, int]] = None,
    ign: Optional[str] = None,
    show_original: bool = False,
    config="--psm 6",
    debug: bool = False,
) -> str:
    img = helpers_to_bgr(img)
    if region is not None:
        x1, y1, x2, y2 = region
        img = img[y1:y2, x1:x2]

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

    extracted_text = pytesseract.image_to_string(thresh, config=config)

    if debug:
        _save_debug(thresh, ign, "OCR input")
        print(f"[DEBUG] OCR Extracted Text: {extracted_text.strip()}")

    if show_original == False:
        extracted_text = extracted_text.lower().strip()

    if search and search.lower() not in extracted_text and debug:
        out_path = _save_debug(img, ign, "region", tag="notfound")
        print(f"[DEBUG] Search text '{search}' not found in extracted text '{extracted_text}'. Saved region image to {out_path}")

    return extracted_text



def get_search_text_blue(
    img: ImageLike,
    search: Optional[str] = None,
    region: Optional[Tuple[int, int, int, int]] = None,
    ign: Optional[str] = None,
    show_original: bool = False,
    config: str = "--psm 6",
    debug: bool = False,
) -> str:
    img = helpers_to_bgr(img)
    if region is not None:
        x1, y1, x2, y2 = region
        img = img[y1:y2, x1:x2]

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_blue = np.array([90, 40, 40])
    upper_blue = np.array([135, 255, 255])
    mask = cv2.inRange(hsv, lower_blue, upper_blue)

    mask = cv2.dilate(mask, np.ones((2, 2), np.uint8), iterations=1)

    ocr_input = 255 - mask

    extracted_text = pytesseract.image_to_string(ocr_input, config=config)

    if debug:
        _save_debug(ocr_input, ign, "Blue OCR input")
        print(f"[DEBUG] BLUE OCR Extracted Text: {extracted_text.strip()}")

    if not show_original:
        extracted_text = extracted_text.lower().strip()

    if search and search.lower() not in extracted_text and debug:
        out_path = _save_debug(img, ign, "blue_region", tag="blue_notfound")
        print(f"[DEBUG] (blue) Search text '{search}' not found in extracted text '{extracted_text}'. Saved region image to {out_path}")

    return extracted_text
