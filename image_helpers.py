from typing import List, Tuple, Optional, Union
from pathlib import Path
import cv2
import pytesseract
import numpy as np

ImageLike = Union[str, np.ndarray, "Image.Image"]  # type: ignore

try:
    from PIL import Image
except Exception:
    Image = None


def _to_bgr(img_like: ImageLike) -> np.ndarray:
    if isinstance(img_like, str):
        bgr = cv2.imread(img_like)
        if bgr is None:
            raise FileNotFoundError(f"image not found: {img_like}")
        return bgr
    elif isinstance(img_like, np.ndarray):
        return img_like
    elif Image is not None and isinstance(img_like, Image.Image):
        rgb = np.array(img_like.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    else:
        raise TypeError(f"Unsupported image type: {type(img_like)}")


def get_text_gray(
    imgLike: ImageLike,
    region: Optional[Tuple[int, int, int, int]] = (1808, 513, 1911, 546),
    ign: Optional[str] = None,
    compare_text: str = "Manual",
    debug: bool = False,
    max_workers: int = 6,
) -> str:
    img = _to_bgr(imgLike)

    h, w = img.shape[:2]
    if region is None:
        x1, y1, x2, y2 = 0, 0, w, h
    else:
        x1, y1, x2, y2 = region
    crop_img = img[y1:y2, x1:x2]

    if debug:
        safe_ign = ign or "debug"
        temp_cropped_path = f"temp/{safe_ign}_cropped_region_gray_debug.png"
        cv2.imwrite(temp_cropped_path, crop_img)

    gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    _, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, simple_bin = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    variant_items: List[Tuple[str, any]] = [
        ("orig", crop_img),
        ("gray", gray),
        ("enhanced", enhanced),
        ("otsu", otsu),
        ("simple_bin", simple_bin),
    ]

    if debug:
        safe_ign = ign or "debug"
        for name, im in variant_items:
            path = f"temp/{safe_ign}_{name}_region_gray_debug.png"
            cv2.imwrite(path, im)

    psm_list = [6, 11, 7]

    def run_ocr(im, psm):
        try:
            cfg = f"--psm {psm}"
            txt = pytesseract.image_to_string(im, config=cfg) or ""
        except Exception:
            txt = ""
        if not txt:
            return ""
        cleaned = txt.strip()
        cleaned = cleaned.splitlines()[0].strip(" .:-~")
        return cleaned

    futures = []
    seq = 0

    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for _, im in variant_items:
            for psm in psm_list:
                futures.append((seq, ex.submit(run_ocr, im, psm)))
                seq += 1

        results = [""] * seq
        for idx, fut in futures:
            try:
                results[idx] = fut.result()
            except Exception:
                results[idx] = ""

    for text in results:
        if text and compare_text.lower() in text.lower():
            return compare_text

    for text in results:
        if text:
            return text

    return ""


def tesseract_extract_text_from_region_white_fast(
    image_input: ImageLike,
    region: Optional[Tuple[int, int, int, int]] = None,
    *,
    ign: Optional[str] = None,
    show_debug: bool = False,
    single_line: bool = True,
    single_word: bool = False,
    digits_only: bool = False,
    downscale: float = 0.8,
    do_dilate: bool = False,
) -> str:
    img = _to_bgr(image_input)
    h, w = img.shape[:2]
    if region is None:
        x1, y1, x2, y2 = 0, 0, w, h
    else:
        x1, y1, x2, y2 = map(int, region)
    roi = img[y1:y2, x1:x2]

    if 0.4 <= downscale < 1.0:
        new_w = max(8, int(roi.shape[1] * downscale))
        new_h = max(8, int(roi.shape[0] * downscale))
        roi = cv2.resize(roi, (new_w, new_h), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    if do_dilate:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binary = cv2.dilate(binary, kernel, iterations=1)

    if show_debug:
        Path("temp").mkdir(parents=True, exist_ok=True)
        base = ign or "debug"
        cv2.imwrite(f"temp/{base}_bin_fast.png", binary)

    if single_word:
        psm = 8
    elif single_line:
        psm = 7
    else:
        psm = 6

    conf = f"--oem 1 --psm {psm}"
    if digits_only:
        conf += " -c tessedit_char_whitelist=0123456789"

    return pytesseract.image_to_string(binary, config=conf).strip()


def tesseract_extract_text_from_region_white(
    img: ImageLike,
    region: Optional[Tuple[int, int, int, int]] = None,
    ign=None,
    show_debug=False,
) -> str:
    img = _to_bgr(img)

    h, w = img.shape[:2]
    if region is None:
        x1, y1, x2, y2 = 0, 0, w, h
    else:
        x1, y1, x2, y2 = region
    crop_img = img[y1:y2, x1:x2]

    if show_debug:
        temp_cropped_path = "temp/" + ign + "_cropped_region_debug.png"
        cv2.imwrite(temp_cropped_path, crop_img)

    gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    if show_debug:
        temp_gray_path = "temp/" + ign + "_gray_region_debug.png"
        cv2.imwrite(temp_gray_path, gray)

    _, binary_img = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    if show_debug:
        temp_binary_path = "temp/" + ign + "_binary_region_debug.png"
        cv2.imwrite(temp_binary_path, binary_img)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    morphed_img = cv2.dilate(binary_img, kernel, iterations=1)
    if show_debug:
        temp_morphed_path = "temp/" + ign + "_morphed_region_debug.png"
        cv2.imwrite(temp_morphed_path, morphed_img)

    custom_config = "--psm 6"
    text = pytesseract.image_to_string(morphed_img, config=custom_config)
    return text.strip()
